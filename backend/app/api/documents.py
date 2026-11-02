"""Module 9 – Board Pack & Document Repository."""
import os

from flask import request, send_file
from flask_restx import Namespace, Resource, abort

from ..audit import audit
from ..extensions import db
from ..models import Document, DocumentVersion
from ..notify import meeting_users, notify
from ..security import auth_required, current_user, get_or_404, require_perm
from ..uploads import save_upload, upload_path
from .meetings import can_view, load_visible

ns = Namespace("documents", description="Module 9 – board packs, agenda links, secure viewer, versions, download control")

CLASSES = {"internal", "confidential", "strictly_confidential"}


def load_doc(doc_id):
    d = get_or_404(Document, doc_id, "Document")
    if not can_view(d.meeting, current_user()):
        abort(403, "You are not invited to this meeting.")
    return d


def _form_bool(value, default=True):
    if value is None:
        return default
    return str(value).lower() in ("1", "true", "yes", "on")


def _pick_version(doc):
    v = request.args.get("version")
    if v:
        ver = next((x for x in doc.versions if x.version == int(v)), None)
        if not ver:
            abort(404, "Version not found")
        return ver
    return doc.latest()


@ns.route("")
class DocumentList(Resource):
    @auth_required("document.view")
    def get(self):
        """List board pack documents (?meeting_id=)."""
        user = current_user()
        q = Document.query
        if request.args.get("meeting_id"):
            load_visible(request.args["meeting_id"])
            q = q.filter_by(meeting_id=int(request.args["meeting_id"]))
        return [d.to_dict(viewer=user) for d in q.order_by(Document.created_at.desc()).all()
                if can_view(d.meeting, user)]

    @auth_required("document.upload")
    def post(self):
        """Upload board pack (multipart: file, meeting_id, title, classification, allow_download, agenda_item_id)."""
        form = request.form
        if not form.get("meeting_id"):
            abort(400, "meeting_id is required.")
        meeting = load_visible(form["meeting_id"])
        if meeting.status == "cancelled":
            abort(400, "Cannot upload documents to a cancelled meeting.")
        classification = form.get("classification") or "confidential"
        if classification not in CLASSES:
            abort(400, "Classification must be internal, confidential or strictly_confidential.")
        agenda_id = int(form["agenda_item_id"]) if form.get("agenda_item_id") else None
        if agenda_id and not any(a.id == agenda_id for a in meeting.agenda_items):
            abort(400, "Agenda item does not belong to this meeting.")
        info = save_upload("documents")
        doc = Document(meeting_id=meeting.id, agenda_item_id=agenda_id,
                       title=(form.get("title") or info["filename"]).strip(), description=form.get("description", ""),
                       classification=classification, allow_download=_form_bool(form.get("allow_download")),
                       created_by=current_user().id, current_version=1)
        db.session.add(doc)
        db.session.add(DocumentVersion(document=doc, version=1, filename=info["filename"],
                                       stored_name=info["stored_name"], mime=info["mime"], size=info["size"],
                                       sha256=info["sha256"], note="Initial upload", uploaded_by=current_user().id))
        db.session.commit()
        notify([u for u in meeting_users(meeting) if u.id != current_user().id],
               f"Board pack: {doc.title}", f"A new document was added to '{meeting.title}' for pre-reading.",
               f"/meetings/{meeting.id}?tab=documents", "document")
        audit("document.upload", "document", "document", doc.id, meeting.id, title=doc.title,
              classification=classification)
        return doc.to_dict(viewer=current_user()), 201


@ns.route("/<int:doc_id>")
class DocumentItem(Resource):
    @auth_required("document.view")
    def get(self, doc_id):
        return load_doc(doc_id).to_dict(viewer=current_user())

    @auth_required("document.upload")
    def put(self, doc_id):
        """Edit title, link to agenda item, classification and download rights."""
        doc = load_doc(doc_id)
        data = request.get_json(silent=True) or {}
        if data.get("title"):
            doc.title = data["title"].strip()
        if "description" in data:
            doc.description = data["description"] or ""
        if "classification" in data:
            if data["classification"] not in CLASSES:
                abort(400, "Invalid classification.")
            doc.classification = data["classification"]
        if "allow_download" in data:
            doc.allow_download = bool(data["allow_download"])
        if "agenda_item_id" in data:
            aid = int(data["agenda_item_id"]) if data["agenda_item_id"] else None
            if aid and not any(a.id == aid for a in doc.meeting.agenda_items):
                abort(400, "Agenda item does not belong to this meeting.")
            doc.agenda_item_id = aid
        db.session.commit()
        audit("document.update", "document", "document", doc.id, doc.meeting_id,
              classification=doc.classification, allow_download=doc.allow_download,
              agenda_item_id=doc.agenda_item_id)
        return doc.to_dict(viewer=current_user())

    @auth_required("document.upload")
    def delete(self, doc_id):
        doc = load_doc(doc_id)
        files = [v.stored_name for v in doc.versions]
        mid, title = doc.meeting_id, doc.title
        db.session.delete(doc)
        db.session.commit()
        for f in files:
            try:
                os.remove(upload_path(f))
            except OSError:
                pass
        audit("document.delete", "document", "document", doc_id, mid, title=title)
        return {"message": "Document deleted"}


@ns.route("/<int:doc_id>/versions")
class Versions(Resource):
    @auth_required("document.upload")
    def post(self, doc_id):
        """Upload a new revision (document version history)."""
        doc = load_doc(doc_id)
        info = save_upload("documents")
        doc.current_version += 1
        db.session.add(DocumentVersion(document=doc, version=doc.current_version, filename=info["filename"],
                                       stored_name=info["stored_name"], mime=info["mime"], size=info["size"],
                                       sha256=info["sha256"], note=request.form.get("note", "")[:255],
                                       uploaded_by=current_user().id))
        db.session.commit()
        notify([u for u in meeting_users(doc.meeting) if u.id != current_user().id],
               f"Updated: {doc.title} (v{doc.current_version})", "A new version of a board paper is available.",
               f"/meetings/{doc.meeting_id}?tab=documents", "document", email=False)
        audit("document.new_version", "document", "document", doc.id, doc.meeting_id, version=doc.current_version)
        return doc.to_dict(viewer=current_user()), 201


@ns.route("/<int:doc_id>/view")
class View(Resource):
    @auth_required("document.view")
    def get(self, doc_id):
        """Secure document viewer stream (inline, read-only; watermark is drawn by the viewer)."""
        doc = load_doc(doc_id)
        ver = _pick_version(doc)
        audit("document.view", "document", "document", doc.id, doc.meeting_id, version=ver.version)
        resp = send_file(upload_path(ver.stored_name), mimetype=ver.mime, as_attachment=False)
        resp.headers["Cache-Control"] = "no-store"
        resp.headers["X-Content-Type-Options"] = "nosniff"
        return resp


@ns.route("/<int:doc_id>/download")
class Download(Resource):
    @auth_required("document.view")
    def get(self, doc_id):
        """Download a document – blocked for restricted documents (attempts are flagged as anomalies)."""
        doc = load_doc(doc_id)
        user = current_user()
        require_perm(user, "document.download", "Your role is not allowed to download documents.")
        if not doc.to_dict(viewer=user)["can_download"]:
            abort(403, "Downloading is restricted for this document. Use the secure viewer.")
        ver = _pick_version(doc)
        audit("document.download", "document", "document", doc.id, doc.meeting_id, version=ver.version)
        return send_file(upload_path(ver.stored_name), mimetype=ver.mime, as_attachment=True,
                         download_name=ver.filename)
