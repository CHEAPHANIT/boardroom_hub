"""Module 10 – notification centre, reminders and the simulated e-mail outbox."""
from flask import request
from flask_restx import Namespace, Resource, abort

from ..audit import audit
from ..extensions import db
from ..models import EmailOutbox, Notification, utcnow
from ..notify import send_due_reminders
from ..security import auth_required, current_user, get_or_404, require_perm

ns = Namespace("notifications", description="Module 10 – in-app notification centre, reminders, e-mail outbox")


@ns.route("")
class NotificationList(Resource):
    @auth_required()
    def get(self):
        """Your notifications (?unread=1, ?limit=50) with the unread count."""
        user = current_user()
        q = Notification.query.filter_by(user_id=user.id)
        if request.args.get("unread") == "1":
            q = q.filter(Notification.read_at.is_(None))
        limit = min(int(request.args.get("limit", 50)), 200)
        unread = Notification.query.filter_by(user_id=user.id, read_at=None).count()
        return {"unread": unread,
                "items": [n.to_dict() for n in q.order_by(Notification.created_at.desc()).limit(limit).all()]}


@ns.route("/<int:notification_id>/read")
class MarkRead(Resource):
    @auth_required()
    def post(self, notification_id):
        n = get_or_404(Notification, notification_id, "Notification")
        if n.user_id != current_user().id:
            abort(404, "Notification not found")
        n.read_at = n.read_at or utcnow()
        db.session.commit()
        return n.to_dict()


@ns.route("/read-all")
class MarkAllRead(Resource):
    @auth_required()
    def post(self):
        Notification.query.filter_by(user_id=current_user().id, read_at=None).update({"read_at": utcnow()})
        db.session.commit()
        return {"message": "All notifications marked as read"}


@ns.route("/send-reminders")
class Reminders(Resource):
    @auth_required("meeting.update")
    def post(self):
        """Send due T-24h / T-1h meeting reminders now (also runs automatically every minute)."""
        sent = send_due_reminders()
        audit("notifications.reminders_run", "system", sent=sent)
        return {"sent": sent}


@ns.route("/outbox")
class Outbox(Resource):
    @auth_required()
    def get(self):
        """Simulated e-mail outbox (invitations, reminders, password resets)."""
        user = current_user()
        if not (user.can("user.manage") or user.can("audit.view")):
            require_perm(user, "user.manage")
        q = EmailOutbox.query
        if request.args.get("q"):
            like = f"%{request.args['q']}%"
            q = q.filter(db.or_(EmailOutbox.to_email.ilike(like), EmailOutbox.subject.ilike(like)))
        return [e.to_dict() for e in q.order_by(EmailOutbox.created_at.desc()).limit(200).all()]
