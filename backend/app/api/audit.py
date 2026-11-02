"""Module 7 – Activity Log & Audit Trail."""
import csv
import hashlib
import io

from flask import Response, request
from flask_restx import Namespace, Resource, abort

from ..audit import audit, verify_chain
from ..extensions import db
from ..models import AuditArchive, AuditLog, SecurityAnomaly, utcnow
from ..pdf import make_pdf
from ..security import auth_required, body, current_user, get_or_404, parse_dt

ns = Namespace("audit", description="Module 7 – tamper-evident logs, search, anomalies, archive, signed export")


def _filtered():
    q = AuditLog.query
    a = request.args
    if a.get("q"):
        like = f"%{a['q']}%"
        q = q.filter(db.or_(AuditLog.action.ilike(like), AuditLog.user_email.ilike(like), AuditLog.path.ilike(like),
                            AuditLog.ip.ilike(like)))
    if a.get("user_id"):
        q = q.filter(AuditLog.user_id == int(a["user_id"]))
    if a.get("user"):
        q = q.filter(AuditLog.user_email.ilike(f"%{a['user']}%"))
    if a.get("meeting_id"):
        q = q.filter(AuditLog.meeting_id == int(a["meeting_id"]))
    if a.get("category"):
        q = q.filter(AuditLog.category == a["category"])
    if a.get("action"):
        q = q.filter(AuditLog.action.ilike(f"%{a['action']}%"))
    if a.get("from"):
        q = q.filter(AuditLog.created_at >= parse_dt(a["from"]))
    if a.get("to"):
        q = q.filter(AuditLog.created_at <= parse_dt(a["to"]))
    return q


@ns.route("/logs")
class Logs(Resource):
    @auth_required("audit.view")
    def get(self):
        """Filter & search logs by meeting ID, executive user, event category or date range (paginated)."""
        page = max(1, int(request.args.get("page", 1)))
        per_page = min(100, max(5, int(request.args.get("per_page", 25))))
        q = _filtered()
        total = q.count()
        items = q.order_by(AuditLog.id.desc()).offset((page - 1) * per_page).limit(per_page).all()
        return {"total": total, "page": page, "per_page": per_page, "items": [x.to_dict() for x in items]}


@ns.route("/categories")
class Categories(Resource):
    @auth_required("audit.view")
    def get(self):
        return [c for (c,) in db.session.query(AuditLog.category).distinct().order_by(AuditLog.category)]


@ns.route("/verify")
class Verify(Resource):
    @auth_required("audit.view")
    def get(self):
        """Verify the SHA-256 hash chain (detects any tampering)."""
        result = verify_chain()
        audit("audit.verify", "security", valid=result["valid"], checked=result["checked"])
        return result


@ns.route("/anomalies")
class Anomalies(Resource):
    @auth_required("audit.view")
    def get(self):
        """Flagged security anomalies (unauthorised downloads, wrong room passcodes, brute force)."""
        q = SecurityAnomaly.query
        if request.args.get("status"):
            q = q.filter_by(status=request.args["status"])
        return [a.to_dict() for a in q.order_by(SecurityAnomaly.created_at.desc()).limit(200).all()]


@ns.route("/anomalies/<int:anomaly_id>/acknowledge")
class Acknowledge(Resource):
    @auth_required("audit.view")
    def post(self, anomaly_id):
        a = get_or_404(SecurityAnomaly, anomaly_id, "Anomaly")
        if a.status == "acknowledged":
            abort(400, "Already acknowledged.")
        a.status = "acknowledged"
        a.acknowledged_by = current_user().id
        a.acknowledged_at = utcnow()
        db.session.commit()
        audit("anomaly.acknowledge", "security", "anomaly", a.id, a.meeting_id)
        return a.to_dict()


@ns.route("/archives")
class Archives(Resource):
    @auth_required("audit.view")
    def get(self):
        return [a.to_dict() for a in AuditArchive.query.order_by(AuditArchive.id.desc()).all()]

    @auth_required("audit.archive")
    def post(self):
        """Lock / archive the audit trail: seals all entries since the last archive into a write-once batch."""
        last = AuditArchive.query.order_by(AuditArchive.to_id.desc()).first()
        start = (last.to_id + 1) if last else 1
        logs = AuditLog.query.filter(AuditLog.id >= start).order_by(AuditLog.id).all()
        if not logs:
            abort(400, "There are no new log entries to archive.")
        batch = hashlib.sha256("".join(x.hash for x in logs).encode()).hexdigest()
        arch = AuditArchive(from_id=logs[0].id, to_id=logs[-1].id, entry_count=len(logs), batch_hash=batch,
                            note=(body().get("note") or "")[:255], created_by=current_user().id)
        db.session.add(arch)
        db.session.commit()
        audit("audit.archive", "security", "archive", arch.id, from_id=arch.from_id, to_id=arch.to_id)
        return arch.to_dict(), 201


@ns.route("/archives/<int:archive_id>/verify")
class VerifyArchive(Resource):
    @auth_required("audit.view")
    def get(self, archive_id):
        arch = get_or_404(AuditArchive, archive_id, "Archive")
        logs = AuditLog.query.filter(AuditLog.id >= arch.from_id, AuditLog.id <= arch.to_id).order_by(AuditLog.id)
        current = hashlib.sha256("".join(x.hash for x in logs).encode()).hexdigest()
        return {"archive": arch.to_dict(), "valid": current == arch.batch_hash}


@ns.route("/export")
class Export(Resource):
    @auth_required("audit.export")
    def get(self):
        """Export a signed CSV/PDF audit trail for external regulatory inspection (?format=csv|pdf + filters)."""
        user = current_user()
        logs = _filtered().order_by(AuditLog.id).limit(5000).all()
        fmt = request.args.get("format", "csv")
        cols = ["id", "created_at", "user_email", "category", "action", "entity", "entity_id", "meeting_id",
                "method", "path", "status_code", "ip", "device_fp", "hash"]
        signature = hashlib.sha256("".join(x.hash for x in logs).encode()).hexdigest()
        chain = verify_chain()
        audit("audit.export", "security", format=fmt, entries=len(logs), signature=signature)
        if fmt == "pdf":
            pdf = make_pdf("Audit Trail Export",
                           f"{len(logs)} entries · exported by {user.full_name} · signature {signature[:16]}…",
                           [("kv", [("Entries", str(len(logs))), ("Chain integrity", "VALID" if chain["valid"]
                                                                   else f"BROKEN at #{chain['broken_at']}"),
                                    ("Export signature (SHA-256)", signature)]),
                            ("table", [["#", "Time (UTC)", "User", "Category", "Action", "Status", "IP"]] +
                             [[x.id, x.to_dict()["created_at"], x.user_email or "-", x.category, x.action,
                               x.status_code, x.ip or "-"] for x in logs])],
                           watermark=f"{user.full_name} · {user.email}")
            return Response(pdf, mimetype="application/pdf",
                            headers={"Content-Disposition": "attachment; filename=audit-trail.pdf"})
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(cols)
        for x in logs:
            d = x.to_dict()
            w.writerow([d.get(c, "") for c in cols])
        w.writerow([])
        w.writerow(["# entries", len(logs)])
        w.writerow(["# chain_valid", chain["valid"]])
        w.writerow(["# signature_sha256", signature])
        w.writerow(["# exported_by", user.email])
        return Response(buf.getvalue(), mimetype="text/csv",
                        headers={"Content-Disposition": "attachment; filename=audit-trail.csv"})
