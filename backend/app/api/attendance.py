"""Module 2 – Participant & Attendance Tracking (joins, durations, late/early alerts, attendance sheet)."""
import csv
import io
from datetime import timedelta

from flask import Response, current_app, request
from flask_restx import Namespace, Resource, abort

from ..audit import audit, flag_anomaly, log_event
from ..extensions import db
from ..models import AbsenceRequest, AttendanceLog, Participant, Proxy, iso, utcnow
from ..notify import notify
from ..pdf import make_pdf
from ..security import auth_required, body, client_ip, current_user, get_or_404, require_perm
from .meetings import is_host, load_visible

ns = Namespace("attendance", description="Module 2 – invitee roster, join/leave logging, attendance status, sheets")

STATUSES = {"pending", "present", "excused", "unexcused", "proxy"}


# ------------------------------------------------------------------------- helpers
def quorum_status(meeting):
    voters = [p for p in meeting.participants if p.is_voting]
    present = [p for p in voters if p.attendance_status in ("present", "proxy")]
    eligible = len(voters)
    pct = round(100 * len(present) / eligible, 1) if eligible else 0.0
    return {"eligible": eligible, "present": len(present), "percent": pct,
            "required_percent": meeting.quorum_percent, "met": eligible > 0 and pct >= meeting.quorum_percent}


def _hosts(meeting):
    return [u for u in (meeting.host, meeting.cohost) if u]


def _record_join(p, ip):
    now = utcnow()
    meeting = p.meeting
    p.connected = True
    p.in_waiting_room = False
    p.current_join_at = now
    first = p.first_join_at is None
    if first:
        p.first_join_at = now
    if p.attendance_status in ("pending", "unexcused", "excused"):
        p.attendance_status = "present"
    db.session.add(AttendanceLog(participant=p, event="join", at=now, ip=ip))
    late_after = meeting.scheduled_start + timedelta(minutes=current_app.config["LATE_THRESHOLD_MINUTES"])
    if first and now > late_after and not p.late_flag:
        p.late_flag = True
        mins = int((now - meeting.scheduled_start).total_seconds() // 60)
        notify(_hosts(meeting), f"Late arrival: {p.user.full_name}",
               f"{p.user.full_name} joined '{meeting.title}' {mins} minutes after the start.",
               f"/meetings/{meeting.id}", "attendance_alert", email=False, commit=False)


def _record_leave(p, ip, at=None):
    if not p.connected:
        return
    now = at or utcnow()
    meeting = p.meeting
    if p.current_join_at:
        p.active_seconds = (p.active_seconds or 0) + max(0, int((now - p.current_join_at).total_seconds()))
    p.connected = False
    p.current_join_at = None
    p.last_leave_at = now
    db.session.add(AttendanceLog(participant=p, event="leave", at=now, ip=ip))
    early_before = meeting.scheduled_end - timedelta(minutes=current_app.config["EARLY_THRESHOLD_MINUTES"])
    if meeting.status == "live" and now < early_before and p.is_voting:
        p.early_flag = True
        q = quorum_status(meeting)
        connected_voters = sum(1 for x in meeting.participants if x.is_voting and x.connected)
        notify(_hosts(meeting), f"Early departure: {p.user.full_name}",
               f"{p.user.full_name} left '{meeting.title}' before the end. "
               f"Voting members still connected: {connected_voters}/{q['eligible']}.",
               f"/meetings/{meeting.id}", "attendance_alert", email=False, commit=False)


def finalize_attendance(meeting):
    end = meeting.actual_end or utcnow()
    approved = {a.user_id for a in AbsenceRequest.query.filter_by(meeting_id=meeting.id, status="approved")}
    proxied = {x.principal_id for x in Proxy.query.filter_by(meeting_id=meeting.id, revoked=False)}
    for p in meeting.participants:
        if p.connected:
            _record_leave(p, None, end)
        if p.attendance_status == "pending":
            p.attendance_status = "proxy" if p.user_id in proxied else (
                "excused" if p.user_id in approved else "unexcused")


def _my_participant(meeting, user):
    p = next((x for x in meeting.participants if x.user_id == user.id), None)
    if not p:
        abort(403, "You are not a participant of this meeting.")
    return p


def _roster(meeting):
    return {"meeting_id": meeting.id, "status": meeting.status, "participants": [p.to_dict() for p in
                                                                                 meeting.participants],
            "summary": {
                "total": len(meeting.participants),
                "connected": sum(1 for p in meeting.participants if p.connected),
                "waiting": sum(1 for p in meeting.participants if p.in_waiting_room),
                "by_status": {s: sum(1 for p in meeting.participants if p.attendance_status == s) for s in STATUSES},
                "by_rsvp": {r: sum(1 for p in meeting.participants if p.rsvp == r)
                            for r in ("pending", "accepted", "declined", "tentative")},
                "late": sum(1 for p in meeting.participants if p.late_flag),
                "early": sum(1 for p in meeting.participants if p.early_flag),
            },
            "quorum": quorum_status(meeting)}


# ------------------------------------------------------------------------- endpoints
@ns.route("/<int:meeting_id>/roster")
class Roster(Resource):
    @auth_required("attendance.view")
    def get(self, meeting_id):
        """View invitee roster: real-time connection status, RSVP states and roles, plus quorum."""
        return _roster(load_visible(meeting_id))


@ns.route("/<int:meeting_id>/join")
class Join(Resource):
    @auth_required("meeting.view")
    def post(self, meeting_id):
        """Join the live virtual boardroom (checks passcode, room lock, waiting room)."""
        m = load_visible(meeting_id)
        user = current_user()
        p = _my_participant(m, user)
        host = is_host(m, user)
        if m.status != "live":
            abort(400, "The meeting is not live yet. The host must start it first.")
        if m.room_locked and not host:
            abort(423, "The host has locked the room.")
        if m.passcode and not host and str(body().get("passcode", "")).strip() != m.passcode:
            log = log_event("room.wrong_passcode", "security", "meeting", m.id, m.id, status_code=403,
                            details={"email": user.email})
            flag_anomaly(log, "unauthorized_room_access",
                         f"{user.email} entered a wrong passcode for '{m.title}'", "medium")
            abort(403, "Wrong meeting passcode.")
        if m.waiting_room and not host and not p.connected and p.first_join_at is None:
            p.in_waiting_room = True
            db.session.commit()
            notify(_hosts(m), f"Waiting room: {user.full_name}", f"{user.full_name} is waiting to be admitted.",
                   f"/meetings/{m.id}", "waiting_room", email=False)
            audit("attendance.waiting", "attendance", "participant", p.id, m.id)
            return {"waiting": True, "message": "You are in the waiting room. The host will admit you."}
        _record_join(p, client_ip())
        db.session.commit()
        audit("attendance.join", "attendance", "participant", p.id, m.id)
        return {"waiting": False, "room_url": m.room_url, "room_name": m.room_name,
                "watermark": f"{user.full_name} · {user.email}" if m.watermark else None,
                "participant": p.to_dict()}


@ns.route("/<int:meeting_id>/admit/<int:participant_id>")
class Admit(Resource):
    @auth_required("meeting.view")
    def post(self, meeting_id, participant_id):
        """Host admits a participant from the waiting room."""
        m = load_visible(meeting_id)
        if not is_host(m, current_user()):
            abort(403, "Only the host can admit participants.")
        p = get_or_404(Participant, participant_id, "Participant")
        if p.meeting_id != m.id or not p.in_waiting_room:
            abort(400, "This participant is not in the waiting room.")
        _record_join(p, None)
        db.session.commit()
        notify(p.user, f"Admitted to {m.title}", "The host admitted you. Open the meeting page to enter the room.",
               f"/meetings/{m.id}", "live", email=False)
        audit("attendance.admitted", "attendance", "participant", p.id, m.id, user=p.user.email)
        return p.to_dict()


@ns.route("/<int:meeting_id>/leave")
class Leave(Resource):
    @auth_required("meeting.view")
    def post(self, meeting_id):
        """Leave the virtual boardroom (records exit timestamp and net active minutes)."""
        m = load_visible(meeting_id)
        p = _my_participant(m, current_user())
        p.in_waiting_room = False
        _record_leave(p, client_ip())
        db.session.commit()
        audit("attendance.leave", "attendance", "participant", p.id, m.id)
        return p.to_dict()


@ns.route("/<int:meeting_id>/participants/<int:participant_id>/status")
class UpdateStatus(Resource):
    @auth_required("attendance.manage")
    def put(self, meeting_id, participant_id):
        """Update attendance status: present, excused, unexcused, or represented by proxy."""
        m = load_visible(meeting_id)
        p = get_or_404(Participant, participant_id, "Participant")
        if p.meeting_id != m.id:
            abort(404, "Participant not found")
        status = body().get("attendance_status")
        if status not in STATUSES:
            abort(400, f"Status must be one of: {', '.join(sorted(STATUSES))}.")
        if status == "proxy" and not Proxy.query.filter_by(meeting_id=m.id, principal_id=p.user_id,
                                                         revoked=False).first():
            abort(400, "Assign a voting proxy first (Absence & Proxy module).")
        old = p.attendance_status
        p.attendance_status = status
        db.session.commit()
        audit("attendance.status_updated", "attendance", "participant", p.id, m.id, user=p.user.email,
              old=old, new=status)
        return p.to_dict()


@ns.route("/<int:meeting_id>/logs")
class Logs(Resource):
    @auth_required("attendance.view")
    def get(self, meeting_id):
        """Auto-logged join/exit timestamps for every participant."""
        m = load_visible(meeting_id)
        out = []
        for p in m.participants:
            for log in p.logs:
                out.append({"participant_id": p.id, "user": p.user.brief(), **log.to_dict()})
        return sorted(out, key=lambda r: r["at"] or "")


@ns.route("/<int:meeting_id>/alerts")
class Alerts(Resource):
    @auth_required("attendance.view")
    def get(self, meeting_id):
        """Late arrivals and early departures (quorum-sensitive alerts)."""
        m = load_visible(meeting_id)
        return [{"participant_id": p.id, "user": p.user.brief(), "late": p.late_flag, "early": p.early_flag,
                 "first_join_at": iso(p.first_join_at), "last_leave_at": iso(p.last_leave_at),
                 "is_voting": p.is_voting}
                for p in m.participants if p.late_flag or p.early_flag]


@ns.route("/<int:meeting_id>/sheet")
class Sheet(Resource):
    @auth_required("attendance.view")
    def get(self, meeting_id):
        """Generate the digital attendance sheet (?format=pdf|csv)."""
        m = load_visible(meeting_id)
        user = current_user()
        require_perm(user, "export.data")
        fmt = request.args.get("format", "pdf")
        rows = [["Name", "Title", "Meeting role", "Voting", "RSVP", "Status", "First join (UTC)",
                 "Last leave (UTC)", "Active min", "Late", "Early"]]
        for p in sorted(m.participants, key=lambda x: x.user.full_name):
            rows.append([p.user.full_name, p.user.title, p.meeting_role, "Yes" if p.is_voting else "No", p.rsvp,
                         p.attendance_status, iso(p.first_join_at) or "-", iso(p.last_leave_at) or "-",
                         p.live_active_minutes(), "Yes" if p.late_flag else "", "Yes" if p.early_flag else ""])
        audit("attendance.sheet_exported", "attendance", "meeting", m.id, m.id, format=fmt)
        if fmt == "csv":
            buf = io.StringIO()
            csv.writer(buf).writerows(rows)
            return Response(buf.getvalue(), mimetype="text/csv",
                            headers={"Content-Disposition": f"attachment; filename=attendance-{m.id}.csv"})
        q = quorum_status(m)
        proxies = Proxy.query.filter_by(meeting_id=m.id, revoked=False).all()
        pdf = make_pdf(
            "Digital Attendance Sheet", f"{m.title} · {m.scheduled_start.strftime('%d %B %Y %H:%M')} UTC",
            [("kv", [("Meeting", m.title), ("Classification", m.classification.title()),
                     ("Status", m.status.title()), ("Quorum", f"{q['present']}/{q['eligible']} voting members "
                                                             f"({q['percent']}%) – required {q['required_percent']}%"
                                                             f" – {'MET' if q['met'] else 'NOT MET'}")]),
             ("h", "Attendance"),
             ("table", [["Name", "Role", "Voting", "Status", "First join", "Last leave", "Active min"]]
              + [[r[0], r[2], r[3], r[5], r[6], r[7], r[8]] for r in rows[1:]]),
             ("h", "Proxies"),
             ("table", [["Absent member", "Represented by"]] + [[x.principal.full_name, x.proxy.full_name]
                                                                 for x in proxies] if proxies else []),
             ("sig", ["Company Secretary", "Board Chair"])],
            watermark=f"{user.full_name} · {user.email}")
        return Response(pdf, mimetype="application/pdf",
                        headers={"Content-Disposition": f"attachment; filename=attendance-{m.id}.pdf"})
