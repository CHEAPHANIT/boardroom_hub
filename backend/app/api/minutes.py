"""Module 4 – Structured Meeting Minutes (MOM) & Notes."""
import difflib
import hashlib
import json

from flask import Response
from flask_restx import Namespace, Resource, abort, fields

from ..audit import audit
from ..extensions import db
from ..models import Minutes, MinutesVersion, Proxy, Resolution, utcnow
from ..notify import meeting_users, notify
from ..pdf import make_pdf
from ..security import auth_required, body, current_user, require_perm
from .attendance import quorum_status
from .meetings import load_visible

ns = Namespace("minutes", description="Module 4 – collaborative notes, version control, publish, seal, PDF export")

minutes_model = ns.model("MinutesIn", {
    "general_notes": fields.String(example="Meeting opened at 09:02 by the Chair."),
    "items": fields.List(fields.Raw, example=[{"agenda_item_id": 1, "notes": "Revenue up 12% YoY."}]),
    "change_note": fields.String(example="Added finance discussion"),
})


def get_minutes(meeting, create=False):
    m = Minutes.query.filter_by(meeting_id=meeting.id).first()
    if m is None and create:
        m = Minutes(meeting_id=meeting.id, status="draft", current_version=0)
        db.session.add(m)
        db.session.flush()
    return m


def _payload(meeting, minutes):
    if minutes is None:
        return {"meeting_id": meeting.id, "status": "none", "current_version": 0, "editable": True,
                "content": None, "agenda": [a.to_dict() for a in meeting.agenda_items]}
    d = minutes.to_dict()
    d["agenda"] = [a.to_dict() for a in meeting.agenda_items]
    d["seal_valid"] = (minutes.seal_hash == seal_hash(minutes)) if minutes.status == "sealed" else None
    return d


def seal_hash(minutes):
    latest = minutes.latest()
    material = {
        "meeting_id": minutes.meeting_id,
        "version": minutes.current_version,
        "general_notes": latest.general_notes if latest else "",
        "items": latest.items if latest else [],
        "agenda": [(a.id, a.title, a.decision, a.advisory, a.finding) for a in minutes.meeting.agenda_items],
        "sealed_by": minutes.sealed_by,
        "sealed_at": minutes.sealed_at.isoformat() if minutes.sealed_at else None,
    }
    return hashlib.sha256(json.dumps(material, sort_keys=True).encode()).hexdigest()


def _require_draft(minutes):
    if minutes and minutes.status != "draft":
        abort(423, f"Minutes are {minutes.status} and can no longer be edited.")


@ns.route("/<int:meeting_id>")
class MinutesItem(Resource):
    @auth_required("minutes.view")
    def get(self, meeting_id):
        """Get the latest minutes with agenda summary."""
        meeting = load_visible(meeting_id)
        return _payload(meeting, get_minutes(meeting))

    @ns.expect(minutes_model)
    @auth_required("minutes.edit")
    def put(self, meeting_id):
        """Create / save note draft – every save becomes a new version."""
        meeting = load_visible(meeting_id)
        if meeting.status == "cancelled":
            abort(400, "Minutes cannot be written for a cancelled meeting.")
        minutes = get_minutes(meeting, create=True)
        _require_draft(minutes)
        data = body()
        titles = {a.id: a.title for a in meeting.agenda_items}
        items = []
        for raw in data.get("items") or []:
            aid = int(raw.get("agenda_item_id") or 0)
            if aid not in titles:
                abort(400, f"Agenda item {aid} does not belong to this meeting.")
            items.append({"agenda_item_id": aid, "title": titles[aid], "notes": raw.get("notes") or ""})
        general = data.get("general_notes") or ""
        latest = minutes.latest()
        if latest and latest.general_notes == general and (latest.items or []) == items:
            db.session.commit()
            return _payload(meeting, minutes)
        minutes.current_version += 1
        db.session.add(MinutesVersion(minutes=minutes, version=minutes.current_version, general_notes=general,
                                      items=items, change_note=(data.get("change_note") or "")[:255],
                                      author_id=current_user().id))
        db.session.commit()
        audit("minutes.save_version", "minutes", "minutes", minutes.id, meeting.id, version=minutes.current_version)
        return _payload(meeting, minutes)


@ns.route("/<int:meeting_id>/versions")
class Versions(Resource):
    @auth_required("minutes.view")
    def get(self, meeting_id):
        """Version history of the minutes (who changed what, when)."""
        meeting = load_visible(meeting_id)
        minutes = get_minutes(meeting)
        if not minutes:
            return []
        return [{"version": v.version, "author": v.author.brief() if v.author else None,
                 "created_at": v.to_dict()["created_at"], "change_note": v.change_note,
                 "characters": len(v.as_text())} for v in reversed(minutes.versions)]


@ns.route("/<int:meeting_id>/versions/<int:version>")
class VersionItem(Resource):
    @auth_required("minutes.view")
    def get(self, meeting_id, version):
        meeting = load_visible(meeting_id)
        minutes = get_minutes(meeting)
        v = next((x for x in (minutes.versions if minutes else []) if x.version == version), None)
        if not v:
            abort(404, "Version not found")
        return v.to_dict()


@ns.route("/<int:meeting_id>/diff/<int:v_from>/<int:v_to>")
class Diff(Resource):
    @auth_required("minutes.view")
    def get(self, meeting_id, v_from, v_to):
        """Compare two versions (contributor differences across draft stages)."""
        meeting = load_visible(meeting_id)
        minutes = get_minutes(meeting)
        versions = {v.version: v for v in (minutes.versions if minutes else [])}
        if v_from not in versions or v_to not in versions:
            abort(404, "Version not found")
        a, b = versions[v_from], versions[v_to]
        lines = []
        for line in difflib.unified_diff(a.as_text().splitlines(), b.as_text().splitlines(), lineterm="", n=2):
            if line.startswith(("---", "+++")):
                continue
            kind = "add" if line.startswith("+") else "remove" if line.startswith("-") else \
                "hunk" if line.startswith("@@") else "same"
            lines.append({"kind": kind, "text": line[1:] if kind in ("add", "remove", "same") else line})
        return {"from": a.to_dict(), "to": b.to_dict(), "lines": lines}


@ns.route("/<int:meeting_id>/agenda/<int:item_id>")
class AgendaSummary(Resource):
    @auth_required("minutes.edit")
    def put(self, meeting_id, item_id):
        """Update agenda summary: key decisions, strategic advisories and committee findings."""
        meeting = load_visible(meeting_id)
        _require_draft(get_minutes(meeting))
        item = next((a for a in meeting.agenda_items if a.id == item_id), None)
        if not item:
            abort(404, "Agenda item not found")
        data = body()
        for f in ("decision", "advisory", "finding"):
            if f in data:
                setattr(item, f, data[f] or "")
        db.session.commit()
        audit("minutes.agenda_summary_updated", "minutes", "agenda_item", item.id, meeting.id)
        return item.to_dict()


@ns.route("/<int:meeting_id>/publish")
class Publish(Resource):
    @auth_required("minutes.publish")
    def post(self, meeting_id):
        """Publish final MOM: freezes the draft into an immutable governance record."""
        meeting = load_visible(meeting_id)
        minutes = get_minutes(meeting)
        if not minutes or not minutes.versions:
            abort(400, "Write and save the minutes before publishing.")
        _require_draft(minutes)
        if meeting.status != "ended":
            abort(400, "Minutes can be published only after the meeting has ended.")
        minutes.status = "published"
        minutes.published_at = utcnow()
        minutes.published_by = current_user().id
        db.session.commit()
        notify(meeting_users(meeting), f"Minutes published: {meeting.title}",
               "The final minutes are available. The Board Chair will now approve and seal them.",
               f"/meetings/{meeting.id}?tab=minutes", "minutes")
        audit("minutes.publish", "minutes", "minutes", minutes.id, meeting.id, version=minutes.current_version)
        return _payload(meeting, minutes)


@ns.route("/<int:meeting_id>/seal")
class Seal(Resource):
    @auth_required("minutes.seal")
    def post(self, meeting_id):
        """Lock note from edits: digital seal upon approval by the Board Chair."""
        meeting = load_visible(meeting_id)
        minutes = get_minutes(meeting)
        if not minutes or minutes.status != "published":
            abort(400, "Only published minutes can be sealed.")
        minutes.status = "sealed"
        minutes.sealed_at = utcnow()
        minutes.sealed_by = current_user().id
        minutes.seal_hash = seal_hash(minutes)
        db.session.commit()
        notify(meeting_users(meeting), f"Minutes sealed: {meeting.title}",
               "The Board Chair approved and digitally sealed the minutes.",
               f"/meetings/{meeting.id}?tab=minutes", "minutes")
        audit("minutes.seal", "minutes", "minutes", minutes.id, meeting.id, seal_hash=minutes.seal_hash)
        return _payload(meeting, minutes)


@ns.route("/<int:meeting_id>/pdf")
class MinutesPdf(Resource):
    @auth_required("minutes.view")
    def get(self, meeting_id):
        """Export MOM to PDF with signatures and watermark."""
        meeting = load_visible(meeting_id)
        user = current_user()
        require_perm(user, "export.data", "Exporting requires the export.data permission.")
        minutes = get_minutes(meeting)
        if not minutes or not minutes.versions:
            abort(400, "There are no minutes to export yet.")
        latest = minutes.latest()
        q = quorum_status(meeting)
        present = [p for p in meeting.participants if p.attendance_status == "present"]
        absent = [p for p in meeting.participants if p.attendance_status in ("excused", "unexcused")]
        proxies = Proxy.query.filter_by(meeting_id=meeting.id, revoked=False).all()
        notes = {it["agenda_item_id"]: it.get("notes", "") for it in latest.items or []}
        blocks = [
            ("kv", [("Meeting", meeting.title), ("Date", meeting.scheduled_start.strftime("%d %B %Y, %H:%M UTC")),
                    ("Classification", meeting.classification.title()),
                    ("Chair / Host", meeting.host.full_name if meeting.host else "-"),
                    ("Status", f"{minutes.status.upper()} – version {minutes.current_version}"),
                    ("Quorum", f"{q['present']}/{q['eligible']} voting members ({q['percent']}%) – "
                               f"{'met' if q['met'] else 'not met'}")]),
            ("h", "Attendance"),
            ("p", "Present: " + (", ".join(p.user.full_name for p in present) or "-")),
            ("p", "Absent: " + (", ".join(f"{p.user.full_name} ({p.attendance_status})" for p in absent) or "-")),
            ("p", "Proxies: " + (", ".join(f"{x.principal.full_name} → {x.proxy.full_name}" for x in proxies)
                                 or "-")),
            ("h", "General notes"), ("p", latest.general_notes or "-"),
        ]
        for a in meeting.agenda_items:
            blocks.append(("h", f"{a.position}. {a.title}"))
            blocks.append(("p", notes.get(a.id) or "No notes recorded."))
            summary = [(k, v) for k, v in (("Decision", a.decision), ("Strategic advisory", a.advisory),
                                           ("Committee finding", a.finding)) if v]
            if summary:
                blocks.append(("kv", summary))
        resolutions = Resolution.query.filter_by(meeting_id=meeting.id).all()
        if resolutions:
            blocks.append(("h", "Resolutions"))
            blocks.append(("table", [["Number", "Resolution", "Outcome"]] +
                           [[r.number, r.title, r.outcome.upper()] for r in resolutions]))
        if minutes.status == "sealed":
            blocks.append(("p", f"Digitally sealed by {minutes.sealer.full_name} on "
                                f"{minutes.sealed_at.strftime('%d %B %Y %H:%M UTC')}. Seal SHA-256: {minutes.seal_hash}"))
        blocks.append(("sig", [f"Company Secretary\n{minutes.publisher.full_name if minutes.publisher else ''}",
                               f"Board Chair\n{minutes.sealer.full_name if minutes.sealer else ''}"]))
        pdf = make_pdf("Minutes of Meeting", meeting.title, blocks,
                       watermark=f"{user.full_name} · {user.email}" if meeting.watermark else None)
        audit("minutes.export_pdf", "minutes", "minutes", minutes.id, meeting.id)
        return Response(pdf, mimetype="application/pdf",
                        headers={"Content-Disposition": f"attachment; filename=minutes-{meeting.id}.pdf"})
