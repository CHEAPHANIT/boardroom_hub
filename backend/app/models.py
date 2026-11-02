"""SQLAlchemy models for the Enterprise Governance & Boardroom Meeting Hub (SQLite)."""
import json
from datetime import datetime, timezone

from .extensions import db


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def iso(dt):
    return dt.isoformat(timespec="seconds") + "Z" if dt else None


class JSONText(db.TypeDecorator):
    """Stores Python lists/dicts as JSON text (portable for SQLite)."""

    impl = db.Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return None if value is None else json.dumps(value)

    def process_result_value(self, value, dialect):
        return None if value is None else json.loads(value)


# ---------------------------------------------------------------- Module 6 / 8
class Role(db.Model):
    __tablename__ = "roles"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), unique=True, nullable=False)
    description = db.Column(db.String(255), default="")
    permissions = db.Column(JSONText, default=list)
    is_system = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=utcnow)

    users = db.relationship("User", back_populates="role")

    def to_dict(self, with_count=False):
        d = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "permissions": sorted(self.permissions or []),
            "is_system": self.is_system,
        }
        if with_count:
            d["user_count"] = len(self.users)
        return d


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(120), nullable=False)
    title = db.Column(db.String(120), default="")
    organization = db.Column(db.String(120), default="")
    timezone = db.Column(db.String(60), default="Asia/Bangkok")
    password_hash = db.Column(db.String(255))
    role_id = db.Column(db.Integer, db.ForeignKey("roles.id"))
    status = db.Column(db.String(20), default="active")  # invited | active | disabled
    vote_weight = db.Column(db.Integer, default=1)
    failed_logins = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime)
    mfa_enabled = db.Column(db.Boolean, default=False)
    mfa_secret = db.Column(db.String(64))
    notify_email = db.Column(db.Boolean, default=True)
    notify_inapp = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=utcnow)
    last_login_at = db.Column(db.DateTime)

    role = db.relationship("Role", back_populates="users")

    @property
    def permissions(self):
        return set(self.role.permissions or []) if self.role else set()

    def can(self, perm):
        return perm in self.permissions

    def brief(self):
        return {"id": self.id, "full_name": self.full_name, "email": self.email,
                "title": self.title, "role": self.role.name if self.role else None}

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "full_name": self.full_name,
            "title": self.title,
            "organization": self.organization,
            "timezone": self.timezone,
            "role": self.role.to_dict() if self.role else None,
            "role_id": self.role_id,
            "status": self.status,
            "vote_weight": self.vote_weight,
            "mfa_enabled": self.mfa_enabled,
            "notify_email": self.notify_email,
            "notify_inapp": self.notify_inapp,
            "locked": bool(self.locked_until and self.locked_until > utcnow()),
            "created_at": iso(self.created_at),
            "last_login_at": iso(self.last_login_at),
        }


class AuthToken(db.Model):
    """One-time tokens: account invitations, password resets and refresh tokens."""

    __tablename__ = "auth_tokens"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    kind = db.Column(db.String(20), nullable=False)  # invite | reset | refresh
    token_hash = db.Column(db.String(64), unique=True, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=utcnow)

    user = db.relationship("User")


# ---------------------------------------------------------------- Module 1
class Meeting(db.Model):
    __tablename__ = "meetings"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    classification = db.Column(db.String(40), default="board")  # board | committee | advisory | extraordinary | agm
    description = db.Column(db.Text, default="")
    scheduled_start = db.Column(db.DateTime, nullable=False, index=True)
    duration_minutes = db.Column(db.Integer, default=60)
    status = db.Column(db.String(20), default="scheduled")  # scheduled | live | ended | cancelled
    room_name = db.Column(db.String(120))
    room_url = db.Column(db.String(255))
    passcode = db.Column(db.String(20))
    waiting_room = db.Column(db.Boolean, default=True)
    watermark = db.Column(db.Boolean, default=True)
    room_locked = db.Column(db.Boolean, default=False)
    quorum_percent = db.Column(db.Integer, default=50)
    host_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    cohost_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    series_id = db.Column(db.String(36), index=True)
    recurrence = db.Column(db.String(20), default="none")  # none | biweekly | monthly | quarterly
    actual_start = db.Column(db.DateTime)
    actual_end = db.Column(db.DateTime)
    cancel_reason = db.Column(db.String(255))
    reminder_24h_sent = db.Column(db.Boolean, default=False)
    reminder_1h_sent = db.Column(db.Boolean, default=False)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    host = db.relationship("User", foreign_keys=[host_id])
    cohost = db.relationship("User", foreign_keys=[cohost_id])
    agenda_items = db.relationship("AgendaItem", back_populates="meeting", order_by="AgendaItem.position",
                                   cascade="all, delete-orphan")
    participants = db.relationship("Participant", back_populates="meeting", cascade="all, delete-orphan")

    @property
    def scheduled_end(self):
        from datetime import timedelta
        return self.scheduled_start + timedelta(minutes=self.duration_minutes or 0)

    def to_dict(self, detail=False, viewer=None):
        d = {
            "id": self.id,
            "title": self.title,
            "classification": self.classification,
            "description": self.description,
            "scheduled_start": iso(self.scheduled_start),
            "scheduled_end": iso(self.scheduled_end),
            "duration_minutes": self.duration_minutes,
            "status": self.status,
            "host": self.host.brief() if self.host else None,
            "cohost": self.cohost.brief() if self.cohost else None,
            "recurrence": self.recurrence,
            "series_id": self.series_id,
            "quorum_percent": self.quorum_percent,
            "participant_count": len(self.participants),
            "actual_start": iso(self.actual_start),
            "actual_end": iso(self.actual_end),
            "cancel_reason": self.cancel_reason,
        }
        if detail:
            is_host = viewer is not None and (viewer.id in (self.host_id, self.cohost_id) or viewer.can("meeting.host"))
            d.update({
                "agenda_items": [a.to_dict() for a in self.agenda_items],
                "room_name": self.room_name,
                "room_url": self.room_url if self.status == "live" or is_host else None,
                "passcode": self.passcode if is_host else None,
                "has_passcode": bool(self.passcode),
                "waiting_room": self.waiting_room,
                "watermark": self.watermark,
                "room_locked": self.room_locked,
                "is_host": is_host,
                "created_at": iso(self.created_at),
                "updated_at": iso(self.updated_at),
            })
        return d


class AgendaItem(db.Model):
    __tablename__ = "agenda_items"
    id = db.Column(db.Integer, primary_key=True)
    meeting_id = db.Column(db.Integer, db.ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False)
    position = db.Column(db.Integer, default=1)
    title = db.Column(db.String(200), nullable=False)
    presenter = db.Column(db.String(120), default="")
    duration_minutes = db.Column(db.Integer, default=10)
    # Module 4 – agenda summary annotations
    decision = db.Column(db.Text, default="")
    advisory = db.Column(db.Text, default="")
    finding = db.Column(db.Text, default="")

    meeting = db.relationship("Meeting", back_populates="agenda_items")

    def to_dict(self):
        return {"id": self.id, "position": self.position, "title": self.title, "presenter": self.presenter,
                "duration_minutes": self.duration_minutes, "decision": self.decision,
                "advisory": self.advisory, "finding": self.finding}


# ---------------------------------------------------------------- Module 2
class Participant(db.Model):
    __tablename__ = "participants"
    __table_args__ = (db.UniqueConstraint("meeting_id", "user_id", name="uq_participant"),)
    id = db.Column(db.Integer, primary_key=True)
    meeting_id = db.Column(db.Integer, db.ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    meeting_role = db.Column(db.String(30), default="director")  # chair | director | secretary | counsel | observer | auditor
    is_voting = db.Column(db.Boolean, default=True)
    rsvp = db.Column(db.String(20), default="pending")  # pending | accepted | declined | tentative
    attendance_status = db.Column(db.String(20), default="pending")  # pending | present | excused | unexcused | proxy
    connected = db.Column(db.Boolean, default=False)
    in_waiting_room = db.Column(db.Boolean, default=False)
    first_join_at = db.Column(db.DateTime)
    last_leave_at = db.Column(db.DateTime)
    active_seconds = db.Column(db.Integer, default=0)
    current_join_at = db.Column(db.DateTime)
    late_flag = db.Column(db.Boolean, default=False)
    early_flag = db.Column(db.Boolean, default=False)
    added_at = db.Column(db.DateTime, default=utcnow)

    meeting = db.relationship("Meeting", back_populates="participants")
    user = db.relationship("User")
    logs = db.relationship("AttendanceLog", back_populates="participant", cascade="all, delete-orphan",
                           order_by="AttendanceLog.at")

    def live_active_minutes(self):
        secs = self.active_seconds or 0
        if self.connected and self.current_join_at:
            secs += int((utcnow() - self.current_join_at).total_seconds())
        return round(secs / 60, 1)

    def to_dict(self):
        return {
            "id": self.id,
            "meeting_id": self.meeting_id,
            "user": self.user.brief(),
            "meeting_role": self.meeting_role,
            "is_voting": self.is_voting,
            "rsvp": self.rsvp,
            "attendance_status": self.attendance_status,
            "connected": self.connected,
            "in_waiting_room": self.in_waiting_room,
            "first_join_at": iso(self.first_join_at),
            "last_leave_at": iso(self.last_leave_at),
            "active_minutes": self.live_active_minutes(),
            "late_flag": self.late_flag,
            "early_flag": self.early_flag,
        }


class AttendanceLog(db.Model):
    __tablename__ = "attendance_logs"
    id = db.Column(db.Integer, primary_key=True)
    participant_id = db.Column(db.Integer, db.ForeignKey("participants.id", ondelete="CASCADE"), nullable=False)
    event = db.Column(db.String(10), nullable=False)  # join | leave
    at = db.Column(db.DateTime, default=utcnow)
    ip = db.Column(db.String(64))

    participant = db.relationship("Participant", back_populates="logs")

    def to_dict(self):
        return {"id": self.id, "event": self.event, "at": iso(self.at), "ip": self.ip}


# ---------------------------------------------------------------- Module 3
class AbsenceRequest(db.Model):
    __tablename__ = "absence_requests"
    id = db.Column(db.Integer, primary_key=True)
    meeting_id = db.Column(db.Integer, db.ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    reason_code = db.Column(db.String(30), nullable=False)  # medical | conflict | travel | personal | other
    reason_text = db.Column(db.Text, default="")
    status = db.Column(db.String(20), default="pending")  # pending | approved | rejected
    reviewed_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    reviewed_at = db.Column(db.DateTime)
    review_comment = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=utcnow)

    meeting = db.relationship("Meeting")
    user = db.relationship("User", foreign_keys=[user_id])
    reviewer = db.relationship("User", foreign_keys=[reviewed_by])
    documents = db.relationship("AbsenceDocument", back_populates="absence", cascade="all, delete-orphan")

    def to_dict(self):
        proxy = Proxy.query.filter_by(meeting_id=self.meeting_id, principal_id=self.user_id, revoked=False).first()
        return {
            "id": self.id,
            "meeting": {"id": self.meeting.id, "title": self.meeting.title,
                        "scheduled_start": iso(self.meeting.scheduled_start)},
            "user": self.user.brief(),
            "reason_code": self.reason_code,
            "reason_text": self.reason_text,
            "status": self.status,
            "reviewer": self.reviewer.brief() if self.reviewer else None,
            "reviewed_at": iso(self.reviewed_at),
            "review_comment": self.review_comment,
            "created_at": iso(self.created_at),
            "documents": [doc.to_dict() for doc in self.documents],
            "proxy": proxy.to_dict() if proxy else None,
        }


class AbsenceDocument(db.Model):
    __tablename__ = "absence_documents"
    id = db.Column(db.Integer, primary_key=True)
    absence_id = db.Column(db.Integer, db.ForeignKey("absence_requests.id", ondelete="CASCADE"), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    stored_name = db.Column(db.String(255), nullable=False)
    mime = db.Column(db.String(120))
    size = db.Column(db.Integer)
    uploaded_at = db.Column(db.DateTime, default=utcnow)

    absence = db.relationship("AbsenceRequest", back_populates="documents")

    def to_dict(self):
        return {"id": self.id, "filename": self.filename, "mime": self.mime, "size": self.size,
                "uploaded_at": iso(self.uploaded_at)}


class Proxy(db.Model):
    __tablename__ = "proxies"
    id = db.Column(db.Integer, primary_key=True)
    meeting_id = db.Column(db.Integer, db.ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False)
    principal_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)  # absent director
    proxy_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)  # attending member
    absence_id = db.Column(db.Integer, db.ForeignKey("absence_requests.id"))
    assigned_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    revoked = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=utcnow)

    meeting = db.relationship("Meeting")
    principal = db.relationship("User", foreign_keys=[principal_id])
    proxy = db.relationship("User", foreign_keys=[proxy_id])
    assigner = db.relationship("User", foreign_keys=[assigned_by])

    def to_dict(self):
        return {"id": self.id, "meeting_id": self.meeting_id, "principal": self.principal.brief(),
                "proxy": self.proxy.brief(), "assigned_by": self.assigner.brief() if self.assigner else None,
                "revoked": self.revoked, "created_at": iso(self.created_at)}


# ---------------------------------------------------------------- Module 4
class Minutes(db.Model):
    __tablename__ = "minutes"
    id = db.Column(db.Integer, primary_key=True)
    meeting_id = db.Column(db.Integer, db.ForeignKey("meetings.id", ondelete="CASCADE"), unique=True, nullable=False)
    status = db.Column(db.String(20), default="draft")  # draft | published | sealed
    current_version = db.Column(db.Integer, default=0)
    published_at = db.Column(db.DateTime)
    published_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    sealed_at = db.Column(db.DateTime)
    sealed_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    seal_hash = db.Column(db.String(64))

    meeting = db.relationship("Meeting")
    publisher = db.relationship("User", foreign_keys=[published_by])
    sealer = db.relationship("User", foreign_keys=[sealed_by])
    versions = db.relationship("MinutesVersion", back_populates="minutes", order_by="MinutesVersion.version",
                               cascade="all, delete-orphan")

    def latest(self):
        return self.versions[-1] if self.versions else None

    def to_dict(self):
        latest = self.latest()
        return {
            "id": self.id,
            "meeting_id": self.meeting_id,
            "status": self.status,
            "current_version": self.current_version,
            "published_at": iso(self.published_at),
            "published_by": self.publisher.brief() if self.publisher else None,
            "sealed_at": iso(self.sealed_at),
            "sealed_by": self.sealer.brief() if self.sealer else None,
            "seal_hash": self.seal_hash,
            "content": latest.to_dict() if latest else None,
            "editable": self.status == "draft",
        }


class MinutesVersion(db.Model):
    __tablename__ = "minutes_versions"
    id = db.Column(db.Integer, primary_key=True)
    minutes_id = db.Column(db.Integer, db.ForeignKey("minutes.id", ondelete="CASCADE"), nullable=False)
    version = db.Column(db.Integer, nullable=False)
    general_notes = db.Column(db.Text, default="")
    items = db.Column(JSONText, default=list)  # [{agenda_item_id, title, notes}]
    change_note = db.Column(db.String(255), default="")
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=utcnow)

    minutes = db.relationship("Minutes", back_populates="versions")
    author = db.relationship("User")

    def to_dict(self):
        return {"id": self.id, "version": self.version, "general_notes": self.general_notes,
                "items": self.items or [], "change_note": self.change_note,
                "author": self.author.brief() if self.author else None, "created_at": iso(self.created_at)}

    def as_text(self):
        lines = ["GENERAL NOTES", self.general_notes or "", ""]
        for it in self.items or []:
            lines += [f"AGENDA: {it.get('title', '')}", it.get("notes", "") or "", ""]
        return "\n".join(lines)


# ---------------------------------------------------------------- Module 5
class Ballot(db.Model):
    __tablename__ = "ballots"
    id = db.Column(db.Integer, primary_key=True)
    meeting_id = db.Column(db.Integer, db.ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False)
    agenda_item_id = db.Column(db.Integer, db.ForeignKey("agenda_items.id"))
    motion = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, default="")
    rule = db.Column(db.String(20), default="simple")  # simple | two_thirds | three_quarters | unanimous
    anonymous = db.Column(db.Boolean, default=False)
    weighted = db.Column(db.Boolean, default=False)
    options = db.Column(JSONText, default=lambda: ["For", "Against", "Abstain"])
    status = db.Column(db.String(20), default="draft")  # draft | open | closed
    opened_at = db.Column(db.DateTime)
    closes_at = db.Column(db.DateTime)
    closed_at = db.Column(db.DateTime)
    result = db.Column(JSONText)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=utcnow)

    meeting = db.relationship("Meeting")
    agenda_item = db.relationship("AgendaItem")
    votes = db.relationship("Vote", back_populates="ballot", cascade="all, delete-orphan")
    creator = db.relationship("User")

    RULE_LABELS = {"simple": "Simple majority (> 50%)", "two_thirds": "Supermajority (≥ 2/3)",
                   "three_quarters": "Supermajority (≥ 3/4)", "unanimous": "Unanimous"}

    def to_dict(self, viewer=None):
        resolution = Resolution.query.filter_by(ballot_id=self.id).first()
        d = {
            "id": self.id,
            "meeting_id": self.meeting_id,
            "meeting_title": self.meeting.title,
            "agenda_item": self.agenda_item.to_dict() if self.agenda_item else None,
            "motion": self.motion,
            "description": self.description,
            "rule": self.rule,
            "rule_label": self.RULE_LABELS.get(self.rule, self.rule),
            "anonymous": self.anonymous,
            "weighted": self.weighted,
            "options": self.options,
            "status": self.status,
            "opened_at": iso(self.opened_at),
            "closes_at": iso(self.closes_at),
            "closed_at": iso(self.closed_at),
            "votes_cast": len(self.votes),
            "result": self.result,
            "resolution": resolution.to_dict() if resolution else None,
            "created_at": iso(self.created_at),
        }
        if viewer is not None:
            mine = [v for v in self.votes if v.voter_id == viewer.id]
            d["my_votes"] = [{"on_behalf_of": v.principal.brief(), "choice": v.choice} for v in mine]
        return d


class Vote(db.Model):
    __tablename__ = "votes"
    __table_args__ = (db.UniqueConstraint("ballot_id", "principal_id", name="uq_one_vote_per_member"),)
    id = db.Column(db.Integer, primary_key=True)
    ballot_id = db.Column(db.Integer, db.ForeignKey("ballots.id", ondelete="CASCADE"), nullable=False)
    voter_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)       # who pressed the button
    principal_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)   # whose vote it is
    choice = db.Column(db.String(60), nullable=False)
    weight = db.Column(db.Integer, default=1)
    receipt = db.Column(db.String(64))
    cast_at = db.Column(db.DateTime, default=utcnow)

    ballot = db.relationship("Ballot", back_populates="votes")
    voter = db.relationship("User", foreign_keys=[voter_id])
    principal = db.relationship("User", foreign_keys=[principal_id])


class Resolution(db.Model):
    __tablename__ = "resolutions"
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String(30), unique=True, nullable=False)
    ballot_id = db.Column(db.Integer, db.ForeignKey("ballots.id"), unique=True, nullable=False)
    meeting_id = db.Column(db.Integer, db.ForeignKey("meetings.id"), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    text = db.Column(db.Text, default="")
    outcome = db.Column(db.String(20), nullable=False)  # passed | failed
    tallies = db.Column(JSONText)
    quorum_met = db.Column(db.Boolean, default=True)
    certified_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    certified_at = db.Column(db.DateTime, default=utcnow)
    cert_hash = db.Column(db.String(64))

    meeting = db.relationship("Meeting")
    certifier = db.relationship("User")

    def to_dict(self):
        return {"id": self.id, "number": self.number, "ballot_id": self.ballot_id,
                "meeting": {"id": self.meeting.id, "title": self.meeting.title},
                "title": self.title, "text": self.text, "outcome": self.outcome, "tallies": self.tallies,
                "quorum_met": self.quorum_met, "certified_by": self.certifier.brief() if self.certifier else None,
                "certified_at": iso(self.certified_at), "cert_hash": self.cert_hash}


# ---------------------------------------------------------------- Module 7
class AuditLog(db.Model):
    """Write-once, hash-chained audit trail. UPDATE/DELETE are blocked by SQLite triggers."""

    __tablename__ = "audit_logs"
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=utcnow, index=True)
    user_id = db.Column(db.Integer, index=True)
    user_email = db.Column(db.String(120))
    action = db.Column(db.String(80), nullable=False, index=True)
    category = db.Column(db.String(30), default="system", index=True)
    entity = db.Column(db.String(40))
    entity_id = db.Column(db.Integer)
    meeting_id = db.Column(db.Integer, index=True)
    method = db.Column(db.String(10))
    path = db.Column(db.String(255))
    status_code = db.Column(db.Integer)
    ip = db.Column(db.String(64))
    user_agent = db.Column(db.String(255))
    device_fp = db.Column(db.String(64))
    details = db.Column(JSONText)
    prev_hash = db.Column(db.String(64))
    hash = db.Column(db.String(64), nullable=False)

    def to_dict(self):
        return {"id": self.id, "created_at": iso(self.created_at), "user_id": self.user_id,
                "user_email": self.user_email, "action": self.action, "category": self.category,
                "entity": self.entity, "entity_id": self.entity_id, "meeting_id": self.meeting_id,
                "method": self.method, "path": self.path, "status_code": self.status_code, "ip": self.ip,
                "user_agent": self.user_agent, "device_fp": self.device_fp, "details": self.details,
                "prev_hash": self.prev_hash, "hash": self.hash}


class AuditArchive(db.Model):
    __tablename__ = "audit_archives"
    id = db.Column(db.Integer, primary_key=True)
    from_id = db.Column(db.Integer, nullable=False)
    to_id = db.Column(db.Integer, nullable=False)
    entry_count = db.Column(db.Integer, nullable=False)
    batch_hash = db.Column(db.String(64), nullable=False)
    note = db.Column(db.String(255), default="")
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=utcnow)

    creator = db.relationship("User")

    def to_dict(self):
        return {"id": self.id, "from_id": self.from_id, "to_id": self.to_id, "entry_count": self.entry_count,
                "batch_hash": self.batch_hash, "note": self.note,
                "created_by": self.creator.brief() if self.creator else None, "created_at": iso(self.created_at)}


class SecurityAnomaly(db.Model):
    __tablename__ = "security_anomalies"
    id = db.Column(db.Integer, primary_key=True)
    log_id = db.Column(db.Integer, db.ForeignKey("audit_logs.id"))
    kind = db.Column(db.String(60), nullable=False)
    severity = db.Column(db.String(10), default="medium")  # low | medium | high
    description = db.Column(db.String(255), default="")
    user_id = db.Column(db.Integer)
    user_email = db.Column(db.String(120))
    meeting_id = db.Column(db.Integer)
    status = db.Column(db.String(20), default="open")  # open | acknowledged
    acknowledged_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    acknowledged_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=utcnow)

    def to_dict(self):
        return {"id": self.id, "log_id": self.log_id, "kind": self.kind, "severity": self.severity,
                "description": self.description, "user_id": self.user_id, "user_email": self.user_email,
                "meeting_id": self.meeting_id, "status": self.status,
                "acknowledged_at": iso(self.acknowledged_at), "created_at": iso(self.created_at)}


# ---------------------------------------------------------------- Module 9
class Document(db.Model):
    __tablename__ = "documents"
    id = db.Column(db.Integer, primary_key=True)
    meeting_id = db.Column(db.Integer, db.ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False)
    agenda_item_id = db.Column(db.Integer, db.ForeignKey("agenda_items.id", ondelete="SET NULL"))
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    classification = db.Column(db.String(30), default="confidential")  # internal | confidential | strictly_confidential
    allow_download = db.Column(db.Boolean, default=True)
    current_version = db.Column(db.Integer, default=1)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=utcnow)

    meeting = db.relationship("Meeting")
    agenda_item = db.relationship("AgendaItem")
    creator = db.relationship("User")
    versions = db.relationship("DocumentVersion", back_populates="document", order_by="DocumentVersion.version",
                               cascade="all, delete-orphan")

    def latest(self):
        return self.versions[-1] if self.versions else None

    def to_dict(self, viewer=None):
        latest = self.latest()
        can_download = False
        if viewer is not None:
            can_download = viewer.can("document.download") and (
                self.allow_download and self.classification != "strictly_confidential"
                or viewer.can("document.upload"))
        return {"id": self.id, "meeting_id": self.meeting_id,
                "agenda_item": {"id": self.agenda_item.id, "title": self.agenda_item.title} if self.agenda_item else None,
                "title": self.title, "description": self.description, "classification": self.classification,
                "allow_download": self.allow_download, "current_version": self.current_version,
                "latest": latest.to_dict() if latest else None,
                "versions": [v.to_dict() for v in reversed(self.versions)],
                "created_by": self.creator.brief() if self.creator else None,
                "created_at": iso(self.created_at), "can_download": can_download}


class DocumentVersion(db.Model):
    __tablename__ = "document_versions"
    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    version = db.Column(db.Integer, nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    stored_name = db.Column(db.String(255), nullable=False)
    mime = db.Column(db.String(120))
    size = db.Column(db.Integer)
    sha256 = db.Column(db.String(64))
    note = db.Column(db.String(255), default="")
    uploaded_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    uploaded_at = db.Column(db.DateTime, default=utcnow)

    document = db.relationship("Document", back_populates="versions")
    uploader = db.relationship("User")

    def to_dict(self):
        return {"id": self.id, "version": self.version, "filename": self.filename, "mime": self.mime,
                "size": self.size, "sha256": self.sha256, "note": self.note,
                "uploaded_by": self.uploader.brief() if self.uploader else None,
                "uploaded_at": iso(self.uploaded_at)}


# ---------------------------------------------------------------- Module 10
class Notification(db.Model):
    __tablename__ = "notifications"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    kind = db.Column(db.String(40), default="info")
    title = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, default="")
    link = db.Column(db.String(255))
    read_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=utcnow)

    def to_dict(self):
        return {"id": self.id, "kind": self.kind, "title": self.title, "body": self.body, "link": self.link,
                "read": self.read_at is not None, "created_at": iso(self.created_at)}


class EmailOutbox(db.Model):
    """Simulated e-mail delivery (no SMTP server needed for the demo)."""

    __tablename__ = "email_outbox"
    id = db.Column(db.Integer, primary_key=True)
    to_email = db.Column(db.String(120), nullable=False)
    subject = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, default="")
    kind = db.Column(db.String(40), default="general")
    created_at = db.Column(db.DateTime, default=utcnow)

    def to_dict(self):
        return {"id": self.id, "to_email": self.to_email, "subject": self.subject, "body": self.body,
                "kind": self.kind, "created_at": iso(self.created_at)}
