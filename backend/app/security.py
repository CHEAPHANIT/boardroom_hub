"""JWT authentication, RBAC permissions and request helpers."""
import hashlib
import secrets
from datetime import datetime
from functools import wraps

import jwt
from flask import current_app, g, request
from flask_restx import abort

from .extensions import db
from .models import User, utcnow

_now = utcnow

# --------------------------------------------------------------------------- permissions
PERMISSIONS = {
    "meeting.view": ("Meetings", "View meetings you are invited to"),
    "meeting.view_all": ("Meetings", "View every meeting in the organisation"),
    "meeting.create": ("Meetings", "Create meetings and recurring schedules"),
    "meeting.update": ("Meetings", "Edit meetings, agenda and participants"),
    "meeting.cancel": ("Meetings", "Cancel meetings"),
    "meeting.host": ("Meetings", "Start/end sessions and configure room security"),
    "attendance.view": ("Attendance", "View invitee roster and attendance"),
    "attendance.manage": ("Attendance", "Update attendance status"),
    "absence.submit": ("Absence & Proxy", "Submit absence requests"),
    "absence.approve": ("Absence & Proxy", "Approve or reject absence requests"),
    "proxy.assign": ("Absence & Proxy", "Assign voting proxies"),
    "minutes.view": ("Minutes", "Read meeting minutes"),
    "minutes.edit": ("Minutes", "Write and edit draft minutes"),
    "minutes.publish": ("Minutes", "Publish final minutes"),
    "minutes.seal": ("Minutes", "Approve and digitally seal minutes"),
    "vote.cast": ("Voting", "Cast votes on ballots"),
    "vote.manage": ("Voting", "Create, launch and close ballots"),
    "resolution.record": ("Voting", "Record certified legal resolutions"),
    "document.view": ("Documents", "View board pack documents"),
    "document.upload": ("Documents", "Upload and manage board pack documents"),
    "document.download": ("Documents", "Download documents (where allowed)"),
    "export.data": ("Reports", "Export PDF/CSV files"),
    "report.view": ("Reports", "View dashboard and governance reports"),
    "user.manage": ("Administration", "Invite, edit and deactivate users"),
    "role.manage": ("Administration", "Create roles and set permissions"),
    "audit.view": ("Audit", "View audit trail and security anomalies"),
    "audit.export": ("Audit", "Export signed audit logs"),
    "audit.archive": ("Audit", "Lock / archive audit trail batches"),
}

ALL = list(PERMISSIONS)
DIRECTOR = ["meeting.view", "attendance.view", "absence.submit", "minutes.view", "vote.cast",
            "document.view", "document.download", "report.view"]

DEFAULT_ROLES = {
    "Administrator": ("Full system administration", ALL),
    "Board Chair": ("Chairs the board, seals minutes and certifies resolutions",
                    [p for p in ALL if p not in ("role.manage", "audit.archive")]),
    "Company Secretary": ("Organises meetings, records minutes and manages members", [
        "meeting.view", "meeting.view_all", "meeting.create", "meeting.update", "meeting.cancel", "meeting.host",
        "attendance.view", "attendance.manage", "absence.approve", "proxy.assign", "minutes.view",
        "minutes.edit", "minutes.publish", "vote.manage", "document.view", "document.upload",
        "document.download", "export.data", "report.view", "user.manage", "audit.view"]),
    "Independent Director": ("Non-executive board member with voting rights", DIRECTOR),
    "Executive Director": ("Executive board member with voting rights", DIRECTOR),
    "Legal Counsel": ("External legal adviser (non-voting)", [
        "meeting.view", "attendance.view", "absence.submit", "minutes.view", "document.view",
        "document.download"]),
    "Auditor": ("Compliance auditor with read-only access and audit trail", [
        "meeting.view", "meeting.view_all", "attendance.view", "minutes.view", "document.view",
        "export.data", "report.view", "audit.view", "audit.export"]),
    "Observer": ("Corporate observer (read-only, non-voting)", ["meeting.view", "minutes.view", "document.view"]),
}


# --------------------------------------------------------------------------- tokens
def hash_token(raw):
    return hashlib.sha256(raw.encode()).hexdigest()


def new_raw_token():
    return secrets.token_urlsafe(32)


def make_access_token(user):
    now = _now()
    payload = {"sub": str(user.id), "role": user.role.name if user.role else None, "type": "access",
               "iat": now, "exp": now + current_app.config["ACCESS_TOKEN_TTL"]}
    return jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm="HS256")


def make_mfa_token(user):
    now = _now()
    from datetime import timedelta
    payload = {"sub": str(user.id), "type": "mfa", "iat": now, "exp": now + timedelta(minutes=5)}
    return jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm="HS256")


def decode_token(token, expected_type="access"):
    try:
        payload = jwt.decode(token, current_app.config["SECRET_KEY"], algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        abort(401, "Session expired. Please sign in again.")
    except jwt.InvalidTokenError:
        abort(401, "Invalid authentication token.")
    if payload.get("type") != expected_type:
        abort(401, "Wrong token type.")
    return payload


def load_user_from_request(optional=False):
    header = request.headers.get("Authorization", "")
    token = header[7:] if header.startswith("Bearer ") else request.args.get("token")
    if not token:
        if optional:
            return None
        abort(401, "Authentication required.")
    payload = decode_token(token)
    user = db.session.get(User, int(payload["sub"]))
    if not user or user.status != "active":
        abort(401, "Account is not active.")
    g.current_user = user
    return user


def current_user():
    return getattr(g, "current_user", None)


def auth_required(*perms):
    """Require a valid JWT and (optionally) every permission listed."""

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = load_user_from_request()
            missing = [p for p in perms if not user.can(p)]
            if missing:
                g.audit_denied = {"missing": missing}
                abort(403, f"Permission denied: requires {', '.join(missing)}")
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def require_perm(user, perm, message=None):
    if not user.can(perm):
        g.audit_denied = {"missing": [perm]}
        abort(403, message or f"Permission denied: requires {perm}")


# --------------------------------------------------------------------------- request helpers
def body():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def need(data, *fields):
    missing = [f for f in fields if data.get(f) in (None, "", [])]
    if missing:
        abort(400, f"Missing required field(s): {', '.join(missing)}")


def parse_dt(value, field="date"):
    """Parse an ISO date-time (with or without timezone) into naive UTC."""
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        text = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
    except ValueError:
        abort(400, f"Invalid {field}: use ISO format, e.g. 2026-11-20T09:00:00+07:00")
    if dt.tzinfo is not None:
        from datetime import timezone
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def get_or_404(model, ident, name=None):
    obj = db.session.get(model, int(ident))
    if obj is None:
        abort(404, f"{name or model.__name__} not found")
    return obj


def client_ip():
    fwd = request.headers.get("X-Forwarded-For", "")
    return fwd.split(",")[0].strip() if fwd else (request.remote_addr or "")


def is_locked(user):
    return bool(user.locked_until and user.locked_until > utcnow())
