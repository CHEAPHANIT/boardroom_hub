"""Module 6 – Roles & Permissions Management (RBAC)."""
from flask_restx import Namespace, Resource, abort, fields

from ..audit import audit
from ..extensions import db
from ..models import Role
from ..security import PERMISSIONS, auth_required, body, current_user, get_or_404, need, require_perm

ns = Namespace("roles", description="Module 6 – custom roles, permissions and the access control matrix")

role_model = ns.model("Role", {
    "name": fields.String(required=True, example="Audit Committee Member"),
    "description": fields.String(example="Reviews audit reports"),
    "permissions": fields.List(fields.String, example=["meeting.view", "minutes.view", "vote.cast"]),
})


def _clean_perms(perms):
    perms = perms or []
    unknown = [p for p in perms if p not in PERMISSIONS]
    if unknown:
        abort(400, f"Unknown permission(s): {', '.join(unknown)}")
    return sorted(set(perms))


@ns.route("")
class RoleList(Resource):
    @auth_required()
    def get(self):
        """List roles with user counts."""
        me = current_user()
        if not (me.can("role.manage") or me.can("user.manage")):
            require_perm(me, "role.manage")
        return [r.to_dict(with_count=True) for r in Role.query.order_by(Role.id).all()]

    @ns.expect(role_model)
    @auth_required("role.manage")
    def post(self):
        """Create a custom role (e.g. Board Chair, Independent Director, Secretary, Auditor, Observer)."""
        data = body()
        need(data, "name")
        name = data["name"].strip()
        if Role.query.filter(db.func.lower(Role.name) == name.lower()).first():
            abort(409, "A role with this name already exists.")
        role = Role(name=name, description=data.get("description", ""),
                    permissions=_clean_perms(data.get("permissions")))
        db.session.add(role)
        db.session.commit()
        audit("role.create", "rbac", "role", role.id, name=name, permissions=role.permissions)
        return role.to_dict(with_count=True), 201


@ns.route("/<int:role_id>")
class RoleItem(Resource):
    @auth_required("role.manage")
    def get(self, role_id):
        return get_or_404(Role, role_id, "Role").to_dict(with_count=True)

    @ns.expect(role_model)
    @auth_required("role.manage")
    def put(self, role_id):
        """Assign role permissions (read, write, vote, sign, export rights) / rename a custom role."""
        role = get_or_404(Role, role_id, "Role")
        data = body()
        before = list(role.permissions or [])
        if "name" in data and data["name"] and data["name"].strip() != role.name:
            if role.is_system:
                abort(400, "Built-in roles cannot be renamed.")
            if Role.query.filter(db.func.lower(Role.name) == data["name"].strip().lower()).first():
                abort(409, "A role with this name already exists.")
            role.name = data["name"].strip()
        if "description" in data:
            role.description = data["description"] or ""
        if "permissions" in data:
            perms = _clean_perms(data["permissions"])
            if role.name == "Administrator" and "role.manage" not in perms:
                abort(400, "The Administrator role must keep the role.manage permission.")
            role.permissions = perms
        db.session.commit()
        audit("role.update", "rbac", "role", role.id, added=sorted(set(role.permissions) - set(before)),
              removed=sorted(set(before) - set(role.permissions)))
        return role.to_dict(with_count=True)

    @auth_required("role.manage")
    def delete(self, role_id):
        """Delete a custom role that has no users."""
        role = get_or_404(Role, role_id, "Role")
        if role.is_system:
            abort(400, "Built-in roles cannot be deleted.")
        if role.users:
            abort(400, "Move the users to another role before deleting this role.")
        db.session.delete(role)
        db.session.commit()
        audit("role.delete", "rbac", "role", role_id, name=role.name)
        return {"message": "Role deleted"}


@ns.route("/matrix")
class Matrix(Resource):
    @auth_required()
    def get(self):
        """Access control matrix: every role against every system feature."""
        me = current_user()
        if not (me.can("role.manage") or me.can("audit.view")):
            require_perm(me, "role.manage")
        roles = Role.query.order_by(Role.id).all()
        return {
            "roles": [{"id": r.id, "name": r.name, "is_system": r.is_system} for r in roles],
            "permissions": [
                {"code": code, "group": grp, "label": label,
                 "granted": {str(r.id): code in (r.permissions or []) for r in roles}}
                for code, (grp, label) in PERMISSIONS.items()
            ],
        }
