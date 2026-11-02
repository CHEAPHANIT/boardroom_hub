from flask import Blueprint
from flask_restx import Api, Resource

blueprint = Blueprint("api", __name__, url_prefix="/api")

authorizations = {
    "Bearer": {"type": "apiKey", "in": "header", "name": "Authorization",
               "description": "Type: **Bearer &lt;access_token&gt;** (get it from POST /api/auth/login)"}
}

api = Api(
    blueprint,
    version="1.0",
    title="Enterprise Governance & Boardroom Meeting Hub API",
    description="Flask RESTful API (OpenAPI / Swagger) for meetings, attendance, absence & proxy, minutes, "
                "voting & resolutions, RBAC, audit trail, authentication, board packs and notifications.",
    doc="/docs",
    authorizations=authorizations,
    security="Bearer",
)

from .auth import ns as auth_ns  # noqa: E402
from .users import ns as users_ns  # noqa: E402
from .roles import ns as roles_ns  # noqa: E402
from .meetings import ns as meetings_ns  # noqa: E402
from .attendance import ns as attendance_ns  # noqa: E402
from .absences import ns as absences_ns  # noqa: E402
from .minutes import ns as minutes_ns  # noqa: E402
from .voting import ns as voting_ns  # noqa: E402
from .documents import ns as documents_ns  # noqa: E402
from .notifications import ns as notifications_ns  # noqa: E402
from .dashboard import ns as dashboard_ns  # noqa: E402
from .audit import ns as audit_ns  # noqa: E402

for _ns, _path in [
    (auth_ns, "/auth"), (users_ns, "/users"), (roles_ns, "/roles"), (meetings_ns, "/meetings"),
    (attendance_ns, "/attendance"), (absences_ns, "/absences"), (minutes_ns, "/minutes"),
    (voting_ns, "/voting"), (documents_ns, "/documents"), (notifications_ns, "/notifications"),
    (dashboard_ns, "/dashboard"), (audit_ns, "/audit"),
]:
    api.add_namespace(_ns, path=_path)


@api.route("/health")
class Health(Resource):
    def get(self):
        """Health check"""
        return {"status": "ok"}
