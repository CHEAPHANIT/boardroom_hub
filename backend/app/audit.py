"""Module 7 – tamper-evident, hash-chained audit trail."""
import hashlib
import json

from flask import g, request
from sqlalchemy import text

from .extensions import db
from .models import AuditLog, SecurityAnomaly, utcnow

GENESIS = "0" * 64

TRIGGERS = [
    """CREATE TRIGGER IF NOT EXISTS audit_logs_no_update BEFORE UPDATE ON audit_logs
       BEGIN SELECT RAISE(ABORT, 'audit_logs is write-once: updates are not allowed'); END;""",
    """CREATE TRIGGER IF NOT EXISTS audit_logs_no_delete BEFORE DELETE ON audit_logs
       BEGIN SELECT RAISE(ABORT, 'audit_logs is write-once: deletes are not allowed'); END;""",
]


def install_triggers():
    for sql in TRIGGERS:
        db.session.execute(text(sql))
    db.session.commit()


def _fields(log):
    return {
        "created_at": log.created_at.isoformat(timespec="microseconds"),
        "user_id": log.user_id, "user_email": log.user_email, "action": log.action, "category": log.category,
        "entity": log.entity, "entity_id": log.entity_id, "meeting_id": log.meeting_id, "method": log.method,
        "path": log.path, "status_code": log.status_code, "ip": log.ip, "device_fp": log.device_fp,
        "details": log.details,
    }


def compute_hash(prev_hash, log):
    payload = json.dumps(_fields(log), sort_keys=True, default=str)
    return hashlib.sha256((prev_hash + payload).encode()).hexdigest()


def _request_meta():
    try:
        fwd = request.headers.get("X-Forwarded-For", "")
        ip = fwd.split(",")[0].strip() if fwd else request.remote_addr
        return {"method": request.method, "path": request.path[:255], "ip": ip,
                "user_agent": (request.headers.get("User-Agent") or "")[:255],
                "device_fp": (request.headers.get("X-Device-Fingerprint") or "")[:64]}
    except RuntimeError:  # outside a request (seed script)
        return {"method": None, "path": None, "ip": None, "user_agent": None, "device_fp": None}


def log_event(action, category="system", entity=None, entity_id=None, meeting_id=None, details=None,
              status_code=200, user=None):
    """Append one entry to the chain and commit it."""
    if user is None:
        user = getattr(g, "current_user", None) if _has_g() else None
    prev = db.session.query(AuditLog.hash).order_by(AuditLog.id.desc()).first()
    log = AuditLog(created_at=utcnow(), user_id=user.id if user else None,
                   user_email=user.email if user else (details or {}).get("email"),
                   action=action, category=category, entity=entity, entity_id=entity_id, meeting_id=meeting_id,
                   status_code=status_code, details=details or {}, **_request_meta())
    log.prev_hash = prev[0] if prev else GENESIS
    log.hash = compute_hash(log.prev_hash, log)
    db.session.add(log)
    db.session.commit()
    return log


def flag_anomaly(log, kind, description, severity="medium"):
    a = SecurityAnomaly(log_id=log.id if log else None, kind=kind, description=description, severity=severity,
                        user_id=log.user_id if log else None, user_email=log.user_email if log else None,
                        meeting_id=log.meeting_id if log else None)
    db.session.add(a)
    db.session.commit()
    return a


def audit(action, category, entity=None, entity_id=None, meeting_id=None, **details):
    """Called inside an endpoint: the after_request hook writes it once the response is known."""
    g.audit_ctx = {"action": action, "category": category, "entity": entity, "entity_id": entity_id,
                   "meeting_id": meeting_id, "details": details}


def _has_g():
    try:
        g.get("x")
        return True
    except RuntimeError:
        return False


def verify_chain():
    prev = GENESIS
    count = 0
    for log in AuditLog.query.order_by(AuditLog.id).yield_per(500):
        if log.prev_hash != prev or compute_hash(prev, log) != log.hash:
            return {"valid": False, "checked": count, "broken_at": log.id}
        prev = log.hash
        count += 1
    return {"valid": True, "checked": count, "broken_at": None, "head": prev}


SENSITIVE_DENIED = ("/download", "/join", "/documents", "/export", "/audit")


def register_hooks(app):
    @app.after_request
    def _write_audit(response):
        if not request.path.startswith("/api/") or request.method == "OPTIONS":
            return response
        try:
            ctx = g.pop("audit_ctx", None)
            denied = g.pop("audit_denied", None)
            if response.status_code == 403:
                log = log_event("access.denied", "security", details={"path": request.path, **(denied or {})},
                                status_code=403)
                if any(s in request.path for s in SENSITIVE_DENIED):
                    flag_anomaly(log, "unauthorized_access",
                                 f"Blocked attempt to access {request.path}", "high")
            elif ctx and response.status_code < 400:
                log_event(ctx["action"], ctx["category"], ctx["entity"], ctx["entity_id"], ctx["meeting_id"],
                          ctx["details"], response.status_code)
            elif ctx and ctx.get("details", {}).get("log_failure"):
                ctx["details"].pop("log_failure", None)
                log_event(ctx["action"], ctx["category"], ctx["entity"], ctx["entity_id"], ctx["meeting_id"],
                          ctx["details"], response.status_code)
            elif request.method in ("POST", "PUT", "PATCH", "DELETE") and response.status_code < 400 \
                    and getattr(g, "current_user", None):
                log_event(f"{request.method.lower()} {request.endpoint or request.path}", "system",
                          details={"path": request.path}, status_code=response.status_code)
        except Exception as exc:  # never break the response because of logging
            db.session.rollback()
            app.logger.warning("audit write failed: %s", exc)
        return response
