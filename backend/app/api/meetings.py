"""Module 1 – Meeting Lifecycle & Virtual Boardroom (+ participant management and ICS export)."""
import calendar
import secrets
import uuid
from datetime import timedelta

from flask import Response, current_app, request
from flask_restx import Namespace, Resource, abort, fields

from ..audit import audit
from ..extensions import db
from ..models import AgendaItem, Meeting, Participant, User, utcnow
from ..notify import build_ics, fmt, meeting_users, notify
from ..security import auth_required, body, current_user, get_or_404, need, parse_dt, require_perm

ns = Namespace("meetings", description="Module 1 – meeting lifecycle, virtual boardroom, recurring schedules")

agenda_model = ns.model("AgendaItemIn", {"title": fields.String(required=True), "presenter": fields.String(),
                                         "duration_minutes": fields.Integer(example=15)})
participant_model = ns.model("ParticipantIn", {"user_id": fields.Integer(required=True),
                                               "meeting_role": fields.String(example="director"),
                                               "is_voting": fields.Boolean(example=True)})
meeting_model = ns.model("MeetingIn", {
    "title": fields.String(required=True, example="Q4 Board Meeting"),
    "classification": fields.String(example="board", enum=["board", "committee", "advisory", "extraordinary", "agm"]),
    "description": fields.String(example="Quarterly results and 2027 budget"),
    "scheduled_start": fields.String(required=True, example="2026-11-20T09:00:00+07:00"),
    "duration_minutes": fields.Integer(example=90),
    "quorum_percent": fields.Integer(example=50),
    "cohost_id": fields.Integer(),
    "recurrence": fields.String(example="none", enum=["none", "biweekly", "monthly", "quarterly"]),
    "occurrences": fields.Integer(example=4),
    "passcode": fields.String(example="482913"),
    "waiting_room": fields.Boolean(example=True),
    "watermark": fields.Boolean(example=True),
    "agenda_items": fields.List(fields.Nested(agenda_model)),
    "participants": fields.List(fields.Nested(participant_model)),
})

CLASSIFICATIONS = {"board", "committee", "advisory", "extraordinary", "agm"}
MEETING_ROLES = {"chair", "director", "secretary", "counsel", "observer", "auditor"}
RECURRENCE = {"none": None, "biweekly": ("days", 14), "monthly": ("months", 1), "quarterly": ("months", 3)}


# ------------------------------------------------------------------------- helpers
def is_participant(meeting, user):
    return any(p.user_id == user.id for p in meeting.participants)


def can_view(meeting, user):
    return user.can("meeting.view_all") or is_participant(meeting, user) or \
        user.id in (meeting.host_id, meeting.cohost_id)


def load_visible(meeting_id):
    user = current_user()
    m = get_or_404(Meeting, meeting_id, "Meeting")
    if not can_view(m, user):
        abort(403, "You are not invited to this meeting.")
    return m


def is_host(meeting, user):
    return user.id in (meeting.host_id, meeting.cohost_id) or user.can("meeting.host")


def require_host(meeting, user):
    if not is_host(meeting, user):
        abort(403, "Only the host, co-host or a user with meeting.host can do this.")


def add_months(dt, months):
    month = dt.month - 1 + months
    year = dt.year + month // 12
    month = month % 12 + 1
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


def _apply_agenda(meeting, items):
    keep = {}
    for idx, raw in enumerate(items or [], start=1):
        if not (raw.get("title") or "").strip():
            continue
        item = None
        if raw.get("id"):
            item = next((a for a in meeting.agenda_items if a.id == raw["id"]), None)
        if item is None:
            item = AgendaItem(meeting=meeting)
            db.session.add(item)
        item.position = idx
        item.title = raw["title"].strip()
        item.presenter = raw.get("presenter", "") or ""
        item.duration_minutes = int(raw.get("duration_minutes") or 10)
        keep[id(item)] = item
    for a in list(meeting.agenda_items):
        if id(a) not in keep:
            meeting.agenda_items.remove(a)


def _add_participants(meeting, items):
    added = []
    existing = {p.user_id for p in meeting.participants}
    for raw in items or []:
        uid = int(raw.get("user_id") or 0)
        if not uid or uid in existing:
            continue
        user = db.session.get(User, uid)
        if not user or user.status == "disabled":
            abort(400, f"User {uid} cannot be invited.")
        role = raw.get("meeting_role") or "director"
        if role not in MEETING_ROLES:
            abort(400, f"Invalid meeting role '{role}'.")
        voting = raw.get("is_voting")
        if voting is None:
            voting = role in ("chair", "director") and user.can("vote.cast")
        p = Participant(meeting=meeting, user=user, meeting_role=role, is_voting=bool(voting))
        db.session.add(p)
        existing.add(uid)
        added.append(p)
    return added


def _fill(meeting, data):
    if "title" in data:
        if not (data["title"] or "").strip():
            abort(400, "Title is required.")
        meeting.title = data["title"].strip()
    if "classification" in data:
        if data["classification"] not in CLASSIFICATIONS:
            abort(400, "Invalid board classification.")
        meeting.classification = data["classification"]
    if "description" in data:
        meeting.description = data["description"] or ""
    if "scheduled_start" in data:
        meeting.scheduled_start = parse_dt(data["scheduled_start"], "scheduled_start")
    if "duration_minutes" in data:
        d = int(data["duration_minutes"] or 0)
        if d < 5 or d > 24 * 60:
            abort(400, "Duration must be between 5 minutes and 24 hours.")
        meeting.duration_minutes = d
    if "quorum_percent" in data:
        q = int(data["quorum_percent"] or 0)
        if q < 1 or q > 100:
            abort(400, "Quorum must be between 1 and 100 percent.")
        meeting.quorum_percent = q
    if "cohost_id" in data:
        meeting.cohost_id = int(data["cohost_id"]) if data["cohost_id"] else None
    for f in ("waiting_room", "watermark"):
        if f in data:
            setattr(meeting, f, bool(data[f]))
    if "passcode" in data:
        pc = (data["passcode"] or "").strip()
        if pc and (not pc.isalnum() or len(pc) < 4 or len(pc) > 12):
            abort(400, "Passcode must be 4–12 letters or digits.")
        meeting.passcode = pc or None


# ------------------------------------------------------------------------- endpoints
@ns.route("")
class MeetingList(Resource):
    @auth_required("meeting.view")
    def get(self):
        """List meetings you can see (filters: status, classification, q, from, to)."""
        user = current_user()
        q = Meeting.query
        if not user.can("meeting.view_all"):
            q = q.outerjoin(Participant).filter(db.or_(Participant.user_id == user.id, Meeting.host_id == user.id,
                                                       Meeting.cohost_id == user.id)).distinct()
        if request.args.get("status"):
            q = q.filter(Meeting.status.in_(request.args["status"].split(",")))
        if request.args.get("classification"):
            q = q.filter(Meeting.classification == request.args["classification"])
        if request.args.get("q"):
            q = q.filter(Meeting.title.ilike(f"%{request.args['q']}%"))
        if request.args.get("from"):
            q = q.filter(Meeting.scheduled_start >= parse_dt(request.args["from"]))
        if request.args.get("to"):
            q = q.filter(Meeting.scheduled_start <= parse_dt(request.args["to"]))
        order = Meeting.scheduled_start.desc() if request.args.get("order") == "desc" else Meeting.scheduled_start
        return [m.to_dict() for m in q.order_by(order).all()]

    @ns.expect(meeting_model)
    @auth_required("meeting.create")
    def post(self):
        """Create meeting: agenda, classification, date, duration (optionally a recurring board schedule)."""
        user = current_user()
        data = body()
        need(data, "title", "scheduled_start")
        recurrence = data.get("recurrence") or "none"
        if recurrence not in RECURRENCE:
            abort(400, "Recurrence must be none, biweekly, monthly or quarterly.")
        occurrences = int(data.get("occurrences") or 1) if recurrence != "none" else 1
        if occurrences < 1 or occurrences > 24:
            abort(400, "Occurrences must be between 1 and 24.")
        first_start = parse_dt(data["scheduled_start"], "scheduled_start")
        if first_start < utcnow() - timedelta(minutes=5):
            abort(400, "The meeting must be scheduled in the future.")
        series_id = str(uuid.uuid4()) if occurrences > 1 else None
        created = []
        for i in range(occurrences):
            m = Meeting(host_id=user.id, created_by=user.id, recurrence=recurrence, series_id=series_id,
                        room_name=f"BoardroomHub-{secrets.token_hex(6)}")
            _fill(m, data)
            if not data.get("passcode"):
                m.passcode = f"{secrets.randbelow(10 ** 6):06d}"
            if recurrence != "none" and i:
                unit, step = RECURRENCE[recurrence]
                m.scheduled_start = first_start + timedelta(days=step * i) if unit == "days" \
                    else add_months(first_start, step * i)
            if occurrences > 1:
                m.title = f"{data['title'].strip()} ({m.scheduled_start.strftime('%b %Y')})" \
                    if recurrence != "biweekly" else f"{data['title'].strip()} #{i + 1}"
            db.session.add(m)
            _apply_agenda(m, data.get("agenda_items"))
            people = list(data.get("participants") or [])
            if not any(int(p.get("user_id") or 0) == user.id for p in people):
                role = "chair" if user.role and user.role.name == "Board Chair" else "secretary"
                people.insert(0, {"user_id": user.id, "meeting_role": role,
                                  "is_voting": role == "chair" and user.can("vote.cast")})
            _add_participants(m, people)
            created.append(m)
        db.session.commit()
        for m in created[:1]:
            notify([u for u in meeting_users(m) if u.id != user.id], f"Meeting invitation: {m.title}",
                   f"You are invited to '{m.title}' on {fmt(m.scheduled_start)}"
                   + (f" (recurring {recurrence}, {occurrences} sessions)" if occurrences > 1 else "") + ".",
                   f"/meetings/{m.id}", "invitation")
        audit("meeting.create", "meeting", "meeting", created[0].id, created[0].id,
              title=created[0].title, occurrences=occurrences, recurrence=recurrence)
        result = created[0].to_dict(detail=True, viewer=user)
        result["series_meeting_ids"] = [m.id for m in created]
        return result, 201


@ns.route("/calendar.ics")
class MyCalendar(Resource):
    @auth_required("meeting.view")
    def get(self):
        """Calendar integration: all your upcoming meetings as an ICS file (Outlook / Google Calendar)."""
        user = current_user()
        q = Meeting.query.filter(Meeting.scheduled_start >= utcnow() - timedelta(days=30))
        meetings = [m for m in q.order_by(Meeting.scheduled_start).all() if can_view(m, user)]
        audit("calendar.export", "meeting", details_count=len(meetings))
        return Response(build_ics(meetings), mimetype="text/calendar",
                        headers={"Content-Disposition": "attachment; filename=boardroom-meetings.ics"})


@ns.route("/<int:meeting_id>")
class MeetingItem(Resource):
    @auth_required("meeting.view")
    def get(self, meeting_id):
        """Meeting details (room passcode only visible to hosts)."""
        m = load_visible(meeting_id)
        user = current_user()
        d = m.to_dict(detail=True, viewer=user)
        me = next((p for p in m.participants if p.user_id == user.id), None)
        d["my_participation"] = me.to_dict() if me else None
        d["series"] = [{"id": s.id, "title": s.title, "scheduled_start": s.to_dict()["scheduled_start"],
                        "status": s.status}
                       for s in Meeting.query.filter_by(series_id=m.series_id).order_by(Meeting.scheduled_start)
                       ] if m.series_id else []
        return d

    @ns.expect(meeting_model)
    @auth_required("meeting.update")
    def put(self, meeting_id):
        """Update meeting schedule / details / agenda (sends reschedule notices)."""
        m = load_visible(meeting_id)
        if m.status in ("cancelled", "ended"):
            abort(400, f"A {m.status} meeting cannot be edited.")
        data = body()
        old_start, old_duration = m.scheduled_start, m.duration_minutes
        _fill(m, data)
        if "agenda_items" in data:
            _apply_agenda(m, data["agenda_items"])
        rescheduled = m.scheduled_start != old_start or m.duration_minutes != old_duration
        if rescheduled:
            if m.status != "scheduled":
                abort(400, "A live meeting cannot be rescheduled.")
            m.reminder_24h_sent = m.reminder_1h_sent = False
        db.session.commit()
        if rescheduled:
            notify(meeting_users(m), f"Rescheduled: {m.title}",
                   f"New time: {fmt(m.scheduled_start)} ({m.duration_minutes} min). Previously {fmt(old_start)}.",
                   f"/meetings/{m.id}", "reschedule")
        audit("meeting.update", "meeting", "meeting", m.id, m.id, rescheduled=rescheduled)
        return m.to_dict(detail=True, viewer=current_user())


@ns.route("/<int:meeting_id>/cancel")
class CancelMeeting(Resource):
    @auth_required("meeting.cancel")
    def post(self, meeting_id):
        """Cancel meeting and broadcast an automated alert to all participants."""
        m = load_visible(meeting_id)
        if m.status != "scheduled":
            abort(400, "Only scheduled meetings can be cancelled.")
        m.status = "cancelled"
        m.cancel_reason = (body().get("reason") or "").strip() or "No reason given"
        db.session.commit()
        notify(meeting_users(m), f"Cancelled: {m.title}",
               f"The meeting on {fmt(m.scheduled_start)} has been cancelled. Reason: {m.cancel_reason}",
               f"/meetings/{m.id}", "cancellation")
        audit("meeting.cancel", "meeting", "meeting", m.id, m.id, reason=m.cancel_reason)
        return m.to_dict(detail=True, viewer=current_user())


@ns.route("/<int:meeting_id>/start")
class StartMeeting(Resource):
    @auth_required("meeting.view")
    def post(self, meeting_id):
        """Start the session: opens the live video bridge for participants."""
        m = load_visible(meeting_id)
        user = current_user()
        require_host(m, user)
        if m.status != "scheduled":
            abort(400, f"Meeting is already {m.status}.")
        if m.scheduled_start - utcnow() > timedelta(hours=1):
            abort(400, "A meeting can be started at most 1 hour before its scheduled time.")
        m.status = "live"
        m.actual_start = utcnow()
        m.room_url = f"{current_app.config['VIDEO_BASE_URL']}/{m.room_name}"
        db.session.commit()
        notify(meeting_users(m), f"Live now: {m.title}", "The virtual boardroom is open. Join from the meeting page.",
               f"/meetings/{m.id}", "live", email=False)
        audit("meeting.start", "meeting", "meeting", m.id, m.id)
        return m.to_dict(detail=True, viewer=user)


@ns.route("/<int:meeting_id>/end")
class EndMeeting(Resource):
    @auth_required("meeting.view")
    def post(self, meeting_id):
        """End the session: disconnects everyone and finalises attendance."""
        from .attendance import finalize_attendance
        m = load_visible(meeting_id)
        require_host(m, current_user())
        if m.status != "live":
            abort(400, "Only a live meeting can be ended.")
        m.status = "ended"
        m.actual_end = utcnow()
        finalize_attendance(m)
        db.session.commit()
        audit("meeting.end", "meeting", "meeting", m.id, m.id)
        return m.to_dict(detail=True, viewer=current_user())


@ns.route("/<int:meeting_id>/security")
class RoomSecurity(Resource):
    @auth_required("meeting.view")
    def put(self, meeting_id):
        """Configure room security: waiting room, passcode, watermark, room lock, co-host."""
        m = load_visible(meeting_id)
        require_host(m, current_user())
        data = body()
        _fill(m, {k: v for k, v in data.items() if k in ("passcode", "waiting_room", "watermark", "cohost_id")})
        if "room_locked" in data:
            m.room_locked = bool(data["room_locked"])
        db.session.commit()
        audit("meeting.security_updated", "meeting", "meeting", m.id, m.id,
              waiting_room=m.waiting_room, watermark=m.watermark, room_locked=m.room_locked,
              passcode_set=bool(m.passcode))
        return m.to_dict(detail=True, viewer=current_user())


@ns.route("/<int:meeting_id>/participants")
class Participants(Resource):
    @auth_required("meeting.view")
    def get(self, meeting_id):
        m = load_visible(meeting_id)
        return [p.to_dict() for p in m.participants]

    @auth_required("meeting.update")
    def post(self, meeting_id):
        """Add participants: board directors, external legal counsel, corporate observers."""
        m = load_visible(meeting_id)
        if m.status in ("cancelled", "ended"):
            abort(400, f"Cannot add participants to a {m.status} meeting.")
        data = body()
        items = data.get("participants") or [
            {"user_id": uid, "meeting_role": data.get("meeting_role"), "is_voting": data.get("is_voting")}
            for uid in data.get("user_ids", [])]
        if not items:
            abort(400, "Choose at least one person.")
        added = _add_participants(m, items)
        db.session.commit()
        notify([p.user for p in added], f"Meeting invitation: {m.title}",
               f"You are invited to '{m.title}' on {fmt(m.scheduled_start)}.", f"/meetings/{m.id}", "invitation")
        audit("meeting.participants_added", "attendance", "meeting", m.id, m.id,
              users=[p.user.email for p in added])
        return [p.to_dict() for p in m.participants], 201


@ns.route("/<int:meeting_id>/participants/<int:participant_id>")
class ParticipantItem(Resource):
    @auth_required("meeting.update")
    def put(self, meeting_id, participant_id):
        m = load_visible(meeting_id)
        p = get_or_404(Participant, participant_id, "Participant")
        if p.meeting_id != m.id:
            abort(404, "Participant not found")
        data = body()
        if "meeting_role" in data:
            if data["meeting_role"] not in MEETING_ROLES:
                abort(400, "Invalid meeting role.")
            p.meeting_role = data["meeting_role"]
        if "is_voting" in data:
            p.is_voting = bool(data["is_voting"])
        db.session.commit()
        audit("meeting.participant_updated", "attendance", "participant", p.id, m.id)
        return p.to_dict()

    @auth_required("meeting.update")
    def delete(self, meeting_id, participant_id):
        m = load_visible(meeting_id)
        p = get_or_404(Participant, participant_id, "Participant")
        if p.meeting_id != m.id:
            abort(404, "Participant not found")
        if p.user_id == m.host_id:
            abort(400, "The host cannot be removed.")
        if m.status != "scheduled":
            abort(400, "Participants can only be removed before the meeting starts.")
        email = p.user.email
        db.session.delete(p)
        db.session.commit()
        audit("meeting.participant_removed", "attendance", "meeting", m.id, m.id, user=email)
        return {"message": "Participant removed"}


@ns.route("/<int:meeting_id>/rsvp")
class Rsvp(Resource):
    @auth_required("meeting.view")
    def post(self, meeting_id):
        """Reply to the invitation: accepted, declined or tentative."""
        m = load_visible(meeting_id)
        user = current_user()
        p = next((x for x in m.participants if x.user_id == user.id), None)
        if not p:
            abort(403, "You are not a participant of this meeting.")
        value = body().get("rsvp")
        if value not in ("accepted", "declined", "tentative"):
            abort(400, "RSVP must be accepted, declined or tentative.")
        p.rsvp = value
        db.session.commit()
        audit("meeting.rsvp", "attendance", "participant", p.id, m.id, rsvp=value)
        return p.to_dict()


@ns.route("/<int:meeting_id>/ics")
class MeetingIcs(Resource):
    @auth_required("meeting.view")
    def get(self, meeting_id):
        """Calendar integration: one meeting as an ICS file."""
        m = load_visible(meeting_id)
        return Response(build_ics([m]), mimetype="text/calendar",
                        headers={"Content-Disposition": f"attachment; filename=meeting-{m.id}.ics"})


@ns.route("/<int:meeting_id>/remind")
class RemindNow(Resource):
    @auth_required("meeting.update")
    def post(self, meeting_id):
        """Send a reminder to every participant now."""
        m = load_visible(meeting_id)
        if m.status != "scheduled":
            abort(400, "Reminders can only be sent for scheduled meetings.")
        notify(meeting_users(m), f"Reminder: {m.title}", f"Your meeting is scheduled for {fmt(m.scheduled_start)}.",
               f"/meetings/{m.id}", "reminder")
        audit("meeting.reminder_sent", "meeting", "meeting", m.id, m.id)
        return {"message": f"Reminder sent to {len(m.participants)} participants"}


def require_meeting_perm(perm):
    require_perm(current_user(), perm)
