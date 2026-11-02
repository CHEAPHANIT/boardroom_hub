"""Module 8 invitations + Module 6 user ↔ role mapping."""
from datetime import timedelta

from flask import current_app
from flask_restx import Namespace, Resource, abort, fields

from ..audit import audit
from ..extensions import db
from ..models import AuthToken, Role, User, utcnow
from ..notify import send_email
from ..security import auth_required, body, current_user, get_or_404, hash_token, need, new_raw_token

ns = Namespace("users", description="Module 6/8 – executive accounts, invitations, role assignment, revocation")

invite_model = ns.model("Invite", {
    "email": fields.String(required=True, example="new.director@boardroom.local"),
    "full_name": fields.String(required=True, example="Sokha Chan"),
    "title": fields.String(example="Independent Director"),
    "organization": fields.String(example="Axiv Holdings"),
    "role_id": fields.Integer(required=True),
    "vote_weight": fields.Integer(example=1),
})


def _admin_count():
    return User.query.join(Role).filter(Role.name == "Administrator", User.status == "active").count()


def _send_invite(user):
    raw = new_raw_token()
    db.session.add(AuthToken(user_id=user.id, kind="invite", token_hash=hash_token(raw),
                             expires_at=utcnow() + timedelta(days=7)))
    db.session.commit()
    link = f"{current_app.config['FRONTEND_URL']}/activate?token={raw}"
    send_email(user.email, "[Boardroom Hub] You are invited to the Boardroom Hub",
               f"Dear {user.full_name},\n\nYou have been invited as {user.role.name if user.role else 'member'}.\n"
               f"Activate your account within 7 days:\n{link}\n", "invitation")
    return link


@ns.route("")
class UserList(Resource):
    @auth_required("user.manage")
    def get(self):
        """List all executive accounts (filters: q, role_id, status)."""
        from flask import request
        q = User.query
        if request.args.get("q"):
            like = f"%{request.args['q']}%"
            q = q.filter(db.or_(User.full_name.ilike(like), User.email.ilike(like), User.title.ilike(like)))
        if request.args.get("role_id"):
            q = q.filter(User.role_id == int(request.args["role_id"]))
        if request.args.get("status"):
            q = q.filter(User.status == request.args["status"])
        return [u.to_dict() for u in q.order_by(User.full_name).all()]


@ns.route("/directory")
class Directory(Resource):
    @auth_required()
    def get(self):
        """Active members (for participant and proxy pickers)."""
        return [dict(u.brief(), vote_weight=u.vote_weight) for u in
                User.query.filter_by(status="active").order_by(User.full_name).all()]


@ns.route("/invite")
class Invite(Resource):
    @ns.expect(invite_model)
    @auth_required("user.manage")
    def post(self):
        """Invite & register an executive account (activation link sent by e-mail)."""
        data = body()
        need(data, "email", "full_name", "role_id")
        email = data["email"].strip().lower()
        if User.query.filter(db.func.lower(User.email) == email).first():
            abort(409, "A user with this e-mail already exists.")
        role = get_or_404(Role, data["role_id"], "Role")
        if role.name == "Administrator" and not current_user().can("role.manage"):
            abort(403, "Only administrators can invite another administrator.")
        user = User(email=email, full_name=data["full_name"].strip(), title=data.get("title", ""),
                    organization=data.get("organization", ""), role=role, status="invited",
                    vote_weight=int(data.get("vote_weight") or 1))
        db.session.add(user)
        db.session.commit()
        link = _send_invite(user)
        audit("user.invite", "rbac", "user", user.id, email=email, role=role.name)
        result = user.to_dict()
        if current_app.config.get("DEMO_MODE", True):
            result["dev_invite_link"] = link
        return result, 201


@ns.route("/<int:user_id>")
class UserItem(Resource):
    @auth_required("user.manage")
    def get(self, user_id):
        return get_or_404(User, user_id, "User").to_dict()

    @auth_required("user.manage")
    def put(self, user_id):
        """Edit an executive profile (name, title, organisation, vote weight)."""
        user = get_or_404(User, user_id, "User")
        data = body()
        for f in ("full_name", "title", "organization", "timezone"):
            if f in data and data[f] is not None:
                setattr(user, f, str(data[f]).strip())
        if "vote_weight" in data:
            w = int(data["vote_weight"] or 1)
            if w < 1 or w > 100:
                abort(400, "Vote weight must be between 1 and 100.")
            user.vote_weight = w
        db.session.commit()
        audit("user.update", "rbac", "user", user.id)
        return user.to_dict()


@ns.route("/<int:user_id>/role")
class AssignRole(Resource):
    @auth_required("user.manage")
    def post(self, user_id):
        """Assign user to role."""
        user = get_or_404(User, user_id, "User")
        role = get_or_404(Role, body().get("role_id") or 0, "Role")
        me = current_user()
        if role.name == "Administrator" and not me.can("role.manage"):
            abort(403, "Only administrators can grant the Administrator role.")
        if user.role and user.role.name == "Administrator" and role.name != "Administrator" and _admin_count() <= 1:
            abort(400, "You cannot remove the last active Administrator.")
        old = user.role.name if user.role else None
        user.role = role
        db.session.commit()
        audit("user.role_assigned", "rbac", "user", user.id, old_role=old, new_role=role.name)
        return user.to_dict()


@ns.route("/<int:user_id>/deactivate")
class Deactivate(Resource):
    @auth_required("user.manage")
    def post(self, user_id):
        """Revoke access (e.g. after a board transition)."""
        user = get_or_404(User, user_id, "User")
        if user.id == current_user().id:
            abort(400, "You cannot deactivate your own account.")
        if user.role and user.role.name == "Administrator" and _admin_count() <= 1:
            abort(400, "You cannot deactivate the last active Administrator.")
        user.status = "disabled"
        AuthToken.query.filter_by(user_id=user.id, kind="refresh", used_at=None).update({"used_at": utcnow()})
        db.session.commit()
        audit("user.access_revoked", "rbac", "user", user.id, email=user.email)
        return user.to_dict()


@ns.route("/<int:user_id>/reactivate")
class Reactivate(Resource):
    @auth_required("user.manage")
    def post(self, user_id):
        user = get_or_404(User, user_id, "User")
        if not user.password_hash:
            abort(400, "This user has not activated the invitation yet. Resend the invite instead.")
        user.status = "active"
        db.session.commit()
        audit("user.access_restored", "rbac", "user", user.id)
        return user.to_dict()


@ns.route("/<int:user_id>/unlock")
class Unlock(Resource):
    @auth_required("user.manage")
    def post(self, user_id):
        user = get_or_404(User, user_id, "User")
        user.failed_logins = 0
        user.locked_until = None
        db.session.commit()
        audit("user.unlocked", "rbac", "user", user.id)
        return user.to_dict()


@ns.route("/<int:user_id>/resend-invite")
class ResendInvite(Resource):
    @auth_required("user.manage")
    def post(self, user_id):
        user = get_or_404(User, user_id, "User")
        if user.status != "invited":
            abort(400, "This account is already activated.")
        link = _send_invite(user)
        audit("user.invite_resent", "rbac", "user", user.id)
        result = {"message": "Invitation sent"}
        if current_app.config.get("DEMO_MODE", True):
            result["dev_invite_link"] = link
        return result
