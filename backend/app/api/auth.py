"""Module 8 – User Authentication & Account Security."""
import base64
import io
import re
from datetime import timedelta

import pyotp
import qrcode
import qrcode.image.svg
from flask import current_app, g
from flask_restx import Namespace, Resource, abort, fields
from werkzeug.security import check_password_hash, generate_password_hash

from ..audit import audit, flag_anomaly, log_event
from ..extensions import db
from ..models import AuthToken, User, utcnow
from ..notify import send_email
from ..security import (PERMISSIONS, auth_required, body, current_user, decode_token, hash_token, is_locked,
                        make_access_token, make_mfa_token, need, new_raw_token)

ns = Namespace("auth", description="Module 8 – login (JWT), MFA, invitations, password reset, profile")

login_model = ns.model("Login", {"email": fields.String(required=True, example="chair@boardroom.local"),
                                 "password": fields.String(required=True, example="Password123!")})
mfa_model = ns.model("MfaVerify", {"mfa_token": fields.String(required=True), "code": fields.String(required=True)})
activate_model = ns.model("Activate", {"token": fields.String(required=True), "password": fields.String(required=True)})
reset_model = ns.model("ResetPassword", {"token": fields.String(required=True),
                                         "new_password": fields.String(required=True)})


def validate_password(pw):
    if not pw or len(pw) < 8 or not re.search(r"[A-Za-z]", pw) or not re.search(r"\d", pw):
        abort(400, "Password must be at least 8 characters and contain letters and numbers.")


def issue_tokens(user):
    raw = new_raw_token()
    db.session.add(AuthToken(user_id=user.id, kind="refresh", token_hash=hash_token(raw),
                             expires_at=utcnow() + current_app.config["REFRESH_TOKEN_TTL"]))
    user.last_login_at = utcnow()
    user.failed_logins = 0
    user.locked_until = None
    db.session.commit()
    return {"access_token": make_access_token(user), "refresh_token": raw, "token_type": "Bearer",
            "expires_in": int(current_app.config["ACCESS_TOKEN_TTL"].total_seconds()), "user": me_payload(user)}


def me_payload(user):
    d = user.to_dict()
    d["permissions"] = sorted(user.permissions)
    return d


def find_token(raw, kind):
    tok = AuthToken.query.filter_by(token_hash=hash_token(raw or ""), kind=kind).first()
    if not tok or tok.used_at or tok.expires_at < utcnow():
        abort(400, "This link is invalid or has expired.")
    return tok


@ns.route("/login")
class Login(Resource):
    @ns.expect(login_model)
    @ns.doc(security=None)
    def post(self):
        """Sign in with e-mail and password (returns JWT, or an MFA challenge)."""
        data = body()
        need(data, "email", "password")
        email = data["email"].strip().lower()
        user = User.query.filter(db.func.lower(User.email) == email).first()
        if user and is_locked(user):
            log_event("auth.login_blocked", "auth", "user", user.id, details={"email": email}, status_code=423)
            abort(423, f"Account locked after too many failed attempts. Try again after "
                       f"{user.locked_until.strftime('%H:%M')} UTC or reset your password.")
        if not user or not user.password_hash or not check_password_hash(user.password_hash, data["password"]):
            if user:
                user.failed_logins = (user.failed_logins or 0) + 1
                if user.failed_logins >= current_app.config["MAX_FAILED_LOGINS"]:
                    user.locked_until = utcnow() + timedelta(minutes=current_app.config["LOCKOUT_MINUTES"])
                db.session.commit()
            log = log_event("auth.login_failed", "auth", "user", user.id if user else None,
                            details={"email": email, "attempts": user.failed_logins if user else None},
                            status_code=401)
            if user and user.locked_until and user.failed_logins >= current_app.config["MAX_FAILED_LOGINS"]:
                flag_anomaly(log, "brute_force", f"Account {email} locked after repeated failed logins", "high")
            abort(401, "Incorrect e-mail or password.")
        if user.status != "active":
            abort(403, "This account is not active. Please use your invitation link or contact the Secretary.")
        if user.mfa_enabled:
            return {"mfa_required": True, "mfa_token": make_mfa_token(user)}
        g.current_user = user
        audit("auth.login", "auth", "user", user.id)
        return issue_tokens(user)


@ns.route("/mfa/verify")
class MfaVerify(Resource):
    @ns.expect(mfa_model)
    @ns.doc(security=None)
    def post(self):
        """Second step of login: verify the 6-digit authenticator code."""
        data = body()
        need(data, "mfa_token", "code")
        payload = decode_token(data["mfa_token"], "mfa")
        user = db.session.get(User, int(payload["sub"]))
        if not user or not pyotp.TOTP(user.mfa_secret or "").verify(str(data["code"]).strip(), valid_window=1):
            log_event("auth.mfa_failed", "auth", "user", user.id if user else None, status_code=401,
                      details={"email": user.email if user else None})
            abort(401, "Invalid authentication code.")
        g.current_user = user
        audit("auth.login", "auth", "user", user.id, mfa=True)
        return issue_tokens(user)


@ns.route("/refresh")
class Refresh(Resource):
    @ns.doc(security=None)
    def post(self):
        """Exchange a refresh token for a new access token (refresh token rotates)."""
        data = body()
        need(data, "refresh_token")
        tok = find_token(data["refresh_token"], "refresh")
        if tok.user.status != "active":
            abort(401, "Account is not active.")
        tok.used_at = utcnow()
        db.session.commit()
        return issue_tokens(tok.user)


@ns.route("/logout")
class Logout(Resource):
    @auth_required()
    def post(self):
        """Sign out and revoke the refresh token."""
        data = body()
        if data.get("refresh_token"):
            tok = AuthToken.query.filter_by(token_hash=hash_token(data["refresh_token"]), kind="refresh").first()
            if tok and not tok.used_at:
                tok.used_at = utcnow()
                db.session.commit()
        audit("auth.logout", "auth", "user", current_user().id)
        return {"message": "Signed out"}


@ns.route("/me")
class Me(Resource):
    @auth_required()
    def get(self):
        """Current user profile and permissions."""
        return me_payload(current_user())

    @auth_required()
    def put(self):
        """Manage executive profile (name, title, organisation, time zone, notification preferences)."""
        user = current_user()
        data = body()
        for f in ("full_name", "title", "organization", "timezone"):
            if f in data and data[f] is not None:
                setattr(user, f, str(data[f]).strip())
        for f in ("notify_email", "notify_inapp"):
            if f in data:
                setattr(user, f, bool(data[f]))
        if not user.full_name:
            abort(400, "Full name is required.")
        db.session.commit()
        audit("profile.update", "auth", "user", user.id)
        return me_payload(user)


@ns.route("/change-password")
class ChangePassword(Resource):
    @auth_required()
    def post(self):
        """Change your password."""
        user = current_user()
        data = body()
        need(data, "current_password", "new_password")
        if not check_password_hash(user.password_hash or "", data["current_password"]):
            abort(400, "Current password is incorrect.")
        validate_password(data["new_password"])
        user.password_hash = generate_password_hash(data["new_password"])
        db.session.commit()
        audit("auth.password_changed", "auth", "user", user.id)
        return {"message": "Password updated"}


@ns.route("/mfa/setup")
class MfaSetup(Resource):
    @auth_required()
    def post(self):
        """Generate a new TOTP secret and QR code (scan with Google/Microsoft Authenticator)."""
        user = current_user()
        user.mfa_secret = pyotp.random_base32()
        db.session.commit()
        uri = pyotp.TOTP(user.mfa_secret).provisioning_uri(name=user.email, issuer_name="Boardroom Hub")
        img = qrcode.make(uri, image_factory=qrcode.image.svg.SvgPathImage)
        buf = io.BytesIO()
        img.save(buf)
        qr = "data:image/svg+xml;base64," + base64.b64encode(buf.getvalue()).decode()
        return {"secret": user.mfa_secret, "otpauth_uri": uri, "qr": qr}


@ns.route("/mfa/enable")
class MfaEnable(Resource):
    @auth_required()
    def post(self):
        """Confirm the authenticator code to switch MFA on."""
        user = current_user()
        code = str(body().get("code", "")).strip()
        if not user.mfa_secret or not pyotp.TOTP(user.mfa_secret).verify(code, valid_window=1):
            abort(400, "That code is not valid. Check the time on your phone and try again.")
        user.mfa_enabled = True
        db.session.commit()
        audit("auth.mfa_enabled", "auth", "user", user.id)
        return me_payload(user)


@ns.route("/mfa/disable")
class MfaDisable(Resource):
    @auth_required()
    def post(self):
        """Turn MFA off (requires your password)."""
        user = current_user()
        if not check_password_hash(user.password_hash or "", body().get("password", "")):
            abort(400, "Password is incorrect.")
        user.mfa_enabled = False
        user.mfa_secret = None
        db.session.commit()
        audit("auth.mfa_disabled", "auth", "user", user.id)
        return me_payload(user)


@ns.route("/forgot-password")
class ForgotPassword(Resource):
    @ns.doc(security=None)
    def post(self):
        """Request a password-reset link (sent to the e-mail outbox)."""
        data = body()
        need(data, "email")
        user = User.query.filter(db.func.lower(User.email) == data["email"].strip().lower()).first()
        result = {"message": "If the e-mail exists, a reset link has been sent."}
        if user and user.status == "active":
            raw = new_raw_token()
            db.session.add(AuthToken(user_id=user.id, kind="reset", token_hash=hash_token(raw),
                                     expires_at=utcnow() + timedelta(hours=1)))
            db.session.commit()
            link = f"{current_app.config['FRONTEND_URL']}/reset-password?token={raw}"
            send_email(user.email, "[Boardroom Hub] Reset your password",
                       f"Dear {user.full_name},\n\nUse this link within 1 hour to set a new password:\n{link}\n",
                       "password_reset")
            log_event("auth.reset_requested", "auth", "user", user.id, details={"email": user.email}, user=user)
            if current_app.config.get("DEMO_MODE", True):
                result["dev_reset_link"] = link  # shown only in demo mode (no SMTP server)
        return result


@ns.route("/reset-password")
class ResetPassword(Resource):
    @ns.expect(reset_model)
    @ns.doc(security=None)
    def post(self):
        """Set a new password with the reset token; also unlocks the account."""
        data = body()
        need(data, "token", "new_password")
        tok = find_token(data["token"], "reset")
        validate_password(data["new_password"])
        tok.user.password_hash = generate_password_hash(data["new_password"])
        tok.user.failed_logins = 0
        tok.user.locked_until = None
        tok.used_at = utcnow()
        db.session.commit()
        log_event("auth.password_reset", "auth", "user", tok.user.id, user=tok.user)
        return {"message": "Password has been reset. You can now sign in."}


@ns.route("/invite/<string:token>")
class InviteInfo(Resource):
    @ns.doc(security=None)
    def get(self, token):
        """Check an invitation link and show who it is for."""
        tok = find_token(token, "invite")
        u = tok.user
        return {"email": u.email, "full_name": u.full_name, "role": u.role.name if u.role else None,
                "title": u.title}


@ns.route("/activate")
class Activate(Resource):
    @ns.expect(activate_model)
    @ns.doc(security=None)
    def post(self):
        """Activate an invited account and set its password."""
        data = body()
        need(data, "token", "password")
        tok = find_token(data["token"], "invite")
        validate_password(data["password"])
        user = tok.user
        user.password_hash = generate_password_hash(data["password"])
        if data.get("full_name"):
            user.full_name = data["full_name"].strip()
        user.status = "active"
        tok.used_at = utcnow()
        db.session.commit()
        log_event("auth.account_activated", "auth", "user", user.id, user=user)
        return issue_tokens(user)


@ns.route("/permissions")
class PermissionCatalogue(Resource):
    @auth_required()
    def get(self):
        """All permission codes the system understands."""
        return [{"code": k, "group": v[0], "label": v[1]} for k, v in PERMISSIONS.items()]
