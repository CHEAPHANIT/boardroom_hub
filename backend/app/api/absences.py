"""Module 3 – Absence & Proxy Approval Workflow."""
import os

from flask import request, send_file
from flask_restx import Namespace, Resource, abort, fields

from ..audit import audit
from ..extensions import db
from ..models import AbsenceDocument, AbsenceRequest, Meeting, Participant, Proxy, User, utcnow
from ..notify import fmt, notify
from ..security import auth_required, body, current_user, get_or_404, need, require_perm
from ..uploads import save_upload, upload_path
from .meetings import load_visible

ns = Namespace("absences", description="Module 3 – absence requests, approvals, supporting docs and voting proxies")

REASONS = {"medical": "Medical", "conflict": "Official conflict", "travel": "Travel", "personal": "Personal",
           "other": "Other"}

absence_model = ns.model("AbsenceIn", {
    "meeting_id": fields.Integer(required=True),
    "reason_code": fields.String(required=True, enum=list(REASONS)),
    "reason_text": fields.String(example="Overseas investor roadshow"),
})
proxy_model = ns.model("ProxyIn", {"meeting_id": fields.Integer(required=True),
                                   "principal_id": fields.Integer(required=True),
                                   "proxy_id": fields.Integer(required=True)})


def approvers(meeting):
    people = {p.user for p in meeting.participants if p.user.can("absence.approve")}
    for u in (meeting.host, meeting.cohost):
        if u and u.can("absence.approve"):
            people.add(u)
    return list(people)


def _can_review(user):
    return user.can("absence.approve")


@ns.route("/reasons")
class Reasons(Resource):
    @auth_required()
    def get(self):
        return [{"code": k, "label": v} for k, v in REASONS.items()]


@ns.route("")
class AbsenceList(Resource):
    @auth_required()
    def get(self):
        """List absence requests (?scope=mine|pending|all, ?meeting_id=)."""
        user = current_user()
        scope = request.args.get("scope", "mine")
        q = AbsenceRequest.query
        if scope in ("pending", "all"):
            if not (_can_review(user) or user.can("audit.view")):
                require_perm(user, "absence.approve")
            if scope == "pending":
                q = q.filter_by(status="pending")
        else:
            q = q.filter_by(user_id=user.id)
        if request.args.get("meeting_id"):
            q = q.filter_by(meeting_id=int(request.args["meeting_id"]))
        return [a.to_dict() for a in q.order_by(AbsenceRequest.created_at.desc()).all()]

    @ns.expect(absence_model)
    @auth_required("absence.submit")
    def post(self):
        """Submit an absence request (formal apology with reason code)."""
        user = current_user()
        data = body()
        need(data, "meeting_id", "reason_code")
        if data["reason_code"] not in REASONS:
            abort(400, "Invalid reason code.")
        m = load_visible(data["meeting_id"])
        if not any(p.user_id == user.id for p in m.participants):
            abort(403, "You are not a participant of this meeting.")
        if m.status not in ("scheduled", "live"):
            abort(400, f"You cannot request absence for a {m.status} meeting.")
        existing = AbsenceRequest.query.filter(AbsenceRequest.meeting_id == m.id, AbsenceRequest.user_id == user.id,
                                               AbsenceRequest.status != "rejected").first()
        if existing:
            abort(409, "You already have an absence request for this meeting.")
        a = AbsenceRequest(meeting_id=m.id, user_id=user.id, reason_code=data["reason_code"],
                           reason_text=(data.get("reason_text") or "").strip())
        db.session.add(a)
        db.session.commit()
        notify(approvers(m), f"Absence request: {user.full_name}",
               f"{user.full_name} requests absence from '{m.title}' ({REASONS[a.reason_code]}).",
               "/absences", "absence")
        audit("absence.submit", "absence", "absence", a.id, m.id, reason=a.reason_code)
        return a.to_dict(), 201


@ns.route("/<int:absence_id>")
class AbsenceItem(Resource):
    @auth_required()
    def get(self, absence_id):
        a = get_or_404(AbsenceRequest, absence_id, "Absence request")
        user = current_user()
        if a.user_id != user.id and not (_can_review(user) or user.can("audit.view")):
            abort(403, "You cannot view this request.")
        return a.to_dict()

    @auth_required()
    def delete(self, absence_id):
        """Withdraw your own pending request."""
        a = get_or_404(AbsenceRequest, absence_id, "Absence request")
        if a.user_id != current_user().id or a.status != "pending":
            abort(400, "Only your own pending request can be withdrawn.")
        mid = a.meeting_id
        for d in a.documents:
            try:
                os.remove(upload_path(d.stored_name))
            except OSError:
                pass
        db.session.delete(a)
        db.session.commit()
        audit("absence.withdraw", "absence", "absence", absence_id, mid)
        return {"message": "Request withdrawn"}


@ns.route("/<int:absence_id>/documents")
class AbsenceDocs(Resource):
    @auth_required("absence.submit")
    def post(self, absence_id):
        """Upload supporting docs (medical, official conflict, travel documentation)."""
        a = get_or_404(AbsenceRequest, absence_id, "Absence request")
        if a.user_id != current_user().id:
            abort(403, "You can only attach files to your own request.")
        if a.status != "pending":
            abort(400, "Files can only be added while the request is pending.")
        info = save_upload("absence")
        doc = AbsenceDocument(absence=a, filename=info["filename"], stored_name=info["stored_name"],
                              mime=info["mime"], size=info["size"])
        db.session.add(doc)
        db.session.commit()
        audit("absence.document_uploaded", "absence", "absence", a.id, a.meeting_id, file=info["filename"])
        return a.to_dict(), 201


@ns.route("/documents/<int:doc_id>/download")
class AbsenceDocDownload(Resource):
    @auth_required()
    def get(self, doc_id):
        doc = get_or_404(AbsenceDocument, doc_id, "Document")
        user = current_user()
        if doc.absence.user_id != user.id and not _can_review(user):
            abort(403, "You cannot download this file.")
        audit("absence.document_downloaded", "document", "absence_document", doc.id, doc.absence.meeting_id)
        return send_file(upload_path(doc.stored_name), mimetype=doc.mime, as_attachment=True,
                         download_name=doc.filename)


def _decide(absence_id, approve):
    a = get_or_404(AbsenceRequest, absence_id, "Absence request")
    user = current_user()
    if a.status != "pending":
        abort(400, f"This request is already {a.status}.")
    if a.user_id == user.id:
        abort(400, "You cannot approve your own absence request.")
    a.status = "approved" if approve else "rejected"
    a.reviewed_by = user.id
    a.reviewed_at = utcnow()
    a.review_comment = (body().get("comment") or "").strip()
    p = Participant.query.filter_by(meeting_id=a.meeting_id, user_id=a.user_id).first()
    if p and approve and p.attendance_status in ("pending", "unexcused"):
        p.attendance_status = "excused"
    db.session.commit()
    notify(a.user, f"Absence {a.status}: {a.meeting.title}",
           f"Your absence request was {a.status} by {user.full_name}."
           + (f" Comment: {a.review_comment}" if a.review_comment else ""), "/absences", "absence")
    audit(f"absence.{a.status}", "absence", "absence", a.id, a.meeting_id, user=a.user.email)
    return a.to_dict()


@ns.route("/<int:absence_id>/approve")
class Approve(Resource):
    @auth_required("absence.approve")
    def post(self, absence_id):
        """Approve a submitted absence justification."""
        return _decide(absence_id, True)


@ns.route("/<int:absence_id>/reject")
class Reject(Resource):
    @auth_required("absence.approve")
    def post(self, absence_id):
        """Reject a submitted absence justification."""
        return _decide(absence_id, False)


@ns.route("/proxies")
class ProxyList(Resource):
    @auth_required()
    def get(self):
        """Proxy authorisations (?meeting_id=)."""
        user = current_user()
        q = Proxy.query
        if request.args.get("meeting_id"):
            load_visible(request.args["meeting_id"])
            q = q.filter_by(meeting_id=int(request.args["meeting_id"]))
        elif not (user.can("proxy.assign") or user.can("audit.view")):
            q = q.filter(db.or_(Proxy.principal_id == user.id, Proxy.proxy_id == user.id))
        return [p.to_dict() for p in q.order_by(Proxy.created_at.desc()).all()]

    @ns.expect(proxy_model)
    @auth_required("proxy.assign")
    def post(self):
        """Assign board voting proxy: delegate an absent director's vote to an attending member."""
        data = body()
        need(data, "meeting_id", "principal_id", "proxy_id")
        m = get_or_404(Meeting, data["meeting_id"], "Meeting")
        principal_id, proxy_id = int(data["principal_id"]), int(data["proxy_id"])
        if principal_id == proxy_id:
            abort(400, "A member cannot be their own proxy.")
        if m.status not in ("scheduled", "live"):
            abort(400, f"Proxies cannot be assigned for a {m.status} meeting.")
        parts = {p.user_id: p for p in m.participants}
        principal, holder = parts.get(principal_id), parts.get(proxy_id)
        if not principal or not principal.is_voting:
            abort(400, "The absent member must be a voting participant of this meeting.")
        if not holder or not holder.is_voting:
            abort(400, "The proxy must be a voting participant who attends the meeting.")
        absence = AbsenceRequest.query.filter_by(meeting_id=m.id, user_id=principal_id, status="approved").first()
        if not absence:
            abort(400, "The member needs an approved absence request before a proxy can be assigned.")
        if AbsenceRequest.query.filter(AbsenceRequest.meeting_id == m.id, AbsenceRequest.user_id == proxy_id,
                                       AbsenceRequest.status != "rejected").first():
            abort(400, "The proxy holder is also absent from this meeting.")
        if Proxy.query.filter_by(meeting_id=m.id, principal_id=proxy_id, revoked=False).first():
            abort(400, "The proxy holder has delegated their own vote.")
        if Proxy.query.filter_by(meeting_id=m.id, principal_id=principal_id, revoked=False).first():
            abort(409, "This member already has an active proxy. Revoke it first.")
        px = Proxy(meeting_id=m.id, principal_id=principal_id, proxy_id=proxy_id, absence_id=absence.id,
                   assigned_by=current_user().id)
        principal.attendance_status = "proxy"
        db.session.add(px)
        db.session.commit()
        notify([principal.user, holder.user], f"Proxy assigned: {m.title}",
               f"{holder.user.full_name} will vote on behalf of {principal.user.full_name} at '{m.title}' "
               f"({fmt(m.scheduled_start)}).", f"/meetings/{m.id}", "proxy")
        audit("proxy.assign", "absence", "proxy", px.id, m.id, principal=principal.user.email,
              proxy=holder.user.email)
        return px.to_dict(), 201


@ns.route("/proxies/<int:proxy_id>")
class ProxyItem(Resource):
    @auth_required("proxy.assign")
    def delete(self, proxy_id):
        """Revoke a proxy authorisation."""
        px = get_or_404(Proxy, proxy_id, "Proxy")
        if px.revoked:
            abort(400, "Proxy is already revoked.")
        px.revoked = True
        p = Participant.query.filter_by(meeting_id=px.meeting_id, user_id=px.principal_id).first()
        if p and p.attendance_status == "proxy":
            p.attendance_status = "excused"
        db.session.commit()
        audit("proxy.revoke", "absence", "proxy", px.id, px.meeting_id)
        return px.to_dict()


@ns.route("/logs")
class AbsenceLogs(Resource):
    @auth_required()
    def get(self):
        """Historical attendance waivers and proxy authorisations."""
        user = current_user()
        full = _can_review(user) or user.can("audit.view")
        q = AbsenceRequest.query.filter(AbsenceRequest.status != "pending")
        pq = Proxy.query
        if not full:
            q = q.filter_by(user_id=user.id)
            pq = pq.filter(db.or_(Proxy.principal_id == user.id, Proxy.proxy_id == user.id))
        return {"absences": [a.to_dict() for a in q.order_by(AbsenceRequest.reviewed_at.desc()).all()],
                "proxies": [p.to_dict() for p in pq.order_by(Proxy.created_at.desc()).all()]}


__all__ = ["ns", "User"]
