"""Module 10 – executive governance dashboard and governance reports."""
import csv
import io
from collections import Counter
from datetime import timedelta

from flask import Response, request
from flask_restx import Namespace, Resource, abort

from ..audit import audit
from ..models import (AbsenceRequest, Ballot, Meeting, Minutes, Notification, Participant, Proxy, Resolution,
                      SecurityAnomaly, Vote, iso, utcnow)
from ..pdf import make_pdf
from ..security import auth_required, current_user, parse_dt, require_perm
from .attendance import quorum_status
from .meetings import add_months, can_view

ns = Namespace("dashboard", description="Module 10 – executive governance dashboard and reports")


def _visible_meetings(user, start=None, end=None):
    q = Meeting.query
    if start:
        q = q.filter(Meeting.scheduled_start >= start)
    if end:
        q = q.filter(Meeting.scheduled_start <= end)
    return [m for m in q.order_by(Meeting.scheduled_start).all() if can_view(m, user)]


def _attendance_rate(meetings):
    parts = [p for m in meetings if m.status == "ended" for p in m.participants]
    if not parts:
        return None
    attended = sum(1 for p in parts if p.attendance_status in ("present", "proxy"))
    return round(100 * attended / len(parts), 1)


@ns.route("")
class Dashboard(Resource):
    @auth_required("meeting.view")
    def get(self):
        """KPIs: upcoming meetings, attendance rate, quorum breaches, open resolutions, pending actions."""
        user = current_user()
        now = utcnow()
        all_visible = _visible_meetings(user)
        recent = [m for m in all_visible if m.scheduled_start >= now - timedelta(days=180)]
        ended = [m for m in recent if m.status == "ended"]
        breaches = [m for m in ended if not quorum_status(m)["met"]]
        upcoming = [m for m in all_visible if m.status in ("scheduled", "live") and m.scheduled_end >= now][:6]
        live = [m for m in all_visible if m.status == "live"]
        open_ballots = [b for b in Ballot.query.filter_by(status="open").all() if can_view(b.meeting, user)]
        my_pending_votes = []
        for b in open_ballots:
            mine = next((p for p in b.meeting.participants if p.user_id == user.id and p.is_voting), None)
            if mine and user.can("vote.cast") and not any(v.principal_id == user.id for v in b.votes):
                my_pending_votes.append({"ballot_id": b.id, "motion": b.motion, "meeting_id": b.meeting_id,
                                         "meeting_title": b.meeting.title})
        year_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        resolutions = [r for r in Resolution.query.filter(Resolution.certified_at >= year_start).all()
                       if can_view(r.meeting, user)]
        months = []
        for i in range(5, -1, -1):
            first = add_months(now.replace(day=1, hour=0, minute=0, second=0, microsecond=0), -i)
            label = first.strftime("%b %Y")
            ms = [m for m in all_visible if m.scheduled_start.strftime("%b %Y") == label]
            months.append({"month": label, "meetings": len([m for m in ms if m.status != "cancelled"]),
                           "attendance_rate": _attendance_rate(ms)})
        status_counts = Counter(p.attendance_status for m in ended for p in m.participants)
        data = {
            "generated_at": iso(now),
            "kpis": {
                "upcoming_meetings": len([m for m in all_visible if m.status == "scheduled" and m.scheduled_start >= now]),
                "live_meetings": len(live),
                "attendance_rate": _attendance_rate(ended),
                "quorum_breaches": len(breaches),
                "open_ballots": len(open_ballots),
                "resolutions_this_year": len(resolutions),
                "resolutions_passed": sum(1 for r in resolutions if r.outcome == "passed"),
                "unread_notifications": Notification.query.filter_by(user_id=user.id, read_at=None).count(),
            },
            "upcoming": [m.to_dict() for m in upcoming],
            "live": [m.to_dict() for m in live],
            "my_pending_votes": my_pending_votes,
            "quorum_breaches": [{"id": m.id, "title": m.title, "scheduled_start": iso(m.scheduled_start),
                                 **quorum_status(m)} for m in breaches],
            "meetings_by_month": months,
            "attendance_breakdown": {s: status_counts.get(s, 0) for s in
                                     ("present", "proxy", "excused", "unexcused")},
            "recent_resolutions": [r.to_dict() for r in sorted(resolutions, key=lambda r: r.certified_at,
                                                               reverse=True)[:5]],
        }
        if user.can("absence.approve"):
            data["pending_absences"] = AbsenceRequest.query.filter_by(status="pending").count()
        if user.can("minutes.seal"):
            data["minutes_awaiting_seal"] = [{"meeting_id": x.meeting_id, "title": x.meeting.title}
                                             for x in Minutes.query.filter_by(status="published").all()]
        if user.can("audit.view"):
            data["open_anomalies"] = SecurityAnomaly.query.filter_by(status="open").count()
        return data


# ----------------------------------------------------------------------------- reports
def _range():
    now = utcnow()
    start = parse_dt(request.args.get("from")) or (now - timedelta(days=90))
    end = parse_dt(request.args.get("to")) or (now + timedelta(days=1))
    if end < start:
        abort(400, "'to' must be after 'from'.")
    return start, end


def attendance_report(user, start, end):
    meetings = [m for m in _visible_meetings(user, start, end) if m.status == "ended"]
    per_member = {}
    for m in meetings:
        for p in m.participants:
            r = per_member.setdefault(p.user_id, {"member": p.user.full_name, "role": p.user.role.name
                                                  if p.user.role else "", "invited": 0, "present": 0, "proxy": 0,
                                                  "excused": 0, "unexcused": 0, "late": 0, "early": 0})
            r["invited"] += 1
            if p.attendance_status in r:
                r[p.attendance_status] += 1
            r["late"] += int(p.late_flag)
            r["early"] += int(p.early_flag)
    rows = sorted(per_member.values(), key=lambda r: r["member"])
    for r in rows:
        r["attendance_rate"] = round(100 * (r["present"] + r["proxy"]) / r["invited"], 1) if r["invited"] else 0
    return {"meetings": len(meetings), "attendance_rate": _attendance_rate(meetings), "rows": rows}


def voting_report(user, start, end):
    ballots = [b for b in Ballot.query.filter(Ballot.status == "closed", Ballot.closed_at >= start,
                                              Ballot.closed_at <= end).all() if can_view(b.meeting, user)]
    rows = []
    for b in ballots:
        res = Resolution.query.filter_by(ballot_id=b.id).first()
        rows.append({"meeting": b.meeting.title, "motion": b.motion, "rule": b.result["rule_label"],
                     "votes": b.result["total_votes"], "support_percent": b.result.get("support_percent"),
                     "outcome": b.result["outcome_label"], "resolution": res.number if res else "",
                     "closed_at": iso(b.closed_at)})
    return {"ballots": len(rows), "passed": sum(1 for b in ballots if b.result.get("passed")), "rows": rows}


def compliance_report(user, start, end):
    meetings = [m for m in _visible_meetings(user, start, end) if m.status == "ended"]
    rows = []
    for m in meetings:
        q = quorum_status(m)
        mins = Minutes.query.filter_by(meeting_id=m.id).first()
        rows.append({"meeting": m.title, "date": iso(m.scheduled_start), "quorum": f"{q['percent']}%",
                     "quorum_met": "Yes" if q["met"] else "NO",
                     "minutes": mins.status if mins else "missing",
                     "sealed_hours": round((mins.sealed_at - m.actual_end).total_seconds() / 3600, 1)
                     if mins and mins.sealed_at and m.actual_end else "",
                     "proxies": Proxy.query.filter_by(meeting_id=m.id, revoked=False).count(),
                     "resolutions": Resolution.query.filter_by(meeting_id=m.id).count()})
    anomalies = SecurityAnomaly.query.filter(SecurityAnomaly.created_at >= start,
                                             SecurityAnomaly.created_at <= end).count()
    return {"meetings": len(rows), "quorum_breaches": sum(1 for r in rows if r["quorum_met"] == "NO"),
            "minutes_sealed": sum(1 for r in rows if r["minutes"] == "sealed"),
            "security_anomalies": anomalies, "rows": rows}


REPORTS = {
    "attendance": ("Attendance Report", attendance_report,
                   ["member", "role", "invited", "present", "proxy", "excused", "unexcused", "late", "early",
                    "attendance_rate"]),
    "voting": ("Voting & Resolutions Report", voting_report,
               ["meeting", "motion", "rule", "votes", "support_percent", "outcome", "resolution", "closed_at"]),
    "compliance": ("Governance Compliance Report", compliance_report,
                   ["meeting", "date", "quorum", "quorum_met", "minutes", "sealed_hours", "proxies", "resolutions"]),
}


@ns.route("/reports/<string:kind>")
class Report(Resource):
    @auth_required("report.view")
    def get(self, kind):
        """Generate governance reports: attendance | voting | compliance (?from, ?to, ?format=json|pdf|csv)."""
        if kind not in REPORTS:
            abort(404, "Unknown report. Use attendance, voting or compliance.")
        user = current_user()
        title, fn, cols = REPORTS[kind]
        start, end = _range()
        data = fn(user, start, end)
        data.update({"title": title, "from": iso(start), "to": iso(end), "columns": cols})
        fmt = request.args.get("format", "json")
        if fmt == "json":
            return data
        require_perm(user, "export.data")
        audit("report.export", "system", details_kind=kind, format=fmt)
        if fmt == "csv":
            buf = io.StringIO()
            w = csv.writer(buf)
            w.writerow(cols)
            for r in data["rows"]:
                w.writerow([r.get(c, "") for c in cols])
            return Response(buf.getvalue(), mimetype="text/csv",
                            headers={"Content-Disposition": f"attachment; filename={kind}-report.csv"})
        summary = [(k.replace("_", " ").title(), str(v)) for k, v in data.items()
                   if k not in ("rows", "columns", "title", "from", "to")]
        pdf = make_pdf(title, f"{start.strftime('%d %b %Y')} – {end.strftime('%d %b %Y')}",
                       [("kv", summary), ("h", "Details"),
                        ("table", [[c.replace("_", " ").title() for c in cols]] +
                         [[r.get(c, "") for c in cols] for r in data["rows"]])],
                       watermark=f"{user.full_name} · {user.email}")
        return Response(pdf, mimetype="application/pdf",
                        headers={"Content-Disposition": f"attachment; filename={kind}-report.pdf"})


__all__ = ["ns", "Participant", "Vote"]
