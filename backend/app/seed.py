"""Database initialisation and realistic demo data (all passwords: Password123!)."""
import hashlib
import os
import secrets
import uuid
from datetime import timedelta

import click
from flask import current_app
from werkzeug.security import generate_password_hash

from .extensions import db
from .models import (AbsenceRequest, AgendaItem, AttendanceLog, AuthToken, Ballot, Document, DocumentVersion,
                     Meeting, Minutes, MinutesVersion, Notification, Participant, Proxy, Resolution, Role, User,
                     Vote, utcnow)
from .security import DEFAULT_ROLES, hash_token

DEMO_PASSWORD = "Password123!"

PEOPLE = [
    ("admin@boardroom.local", "System Administrator", "IT Governance Lead", "Administrator", 1),
    ("chair@boardroom.local", "Dr. Sophea Lim", "Board Chair", "Board Chair", 2),
    ("secretary@boardroom.local", "Dara Kim", "Company Secretary", "Company Secretary", 1),
    ("vannak@boardroom.local", "Vannak Chea", "Independent Director", "Independent Director", 1),
    ("sreymom@boardroom.local", "Sreymom Heng", "Independent Director", "Independent Director", 1),
    ("rithy@boardroom.local", "Rithy Sok", "Chief Executive Officer", "Executive Director", 1),
    ("malis@boardroom.local", "Malis Pich", "Chief Financial Officer", "Executive Director", 1),
    ("counsel@boardroom.local", "Bopha Nuon", "External Legal Counsel", "Legal Counsel", 1),
    ("auditor@boardroom.local", "Kosal Ly", "Internal Auditor", "Auditor", 1),
    ("observer@boardroom.local", "Narin Tep", "Corporate Observer", "Observer", 1),
]


def ensure_roles():
    for name, (desc, perms) in DEFAULT_ROLES.items():
        role = Role.query.filter_by(name=name).first()
        if not role:
            db.session.add(Role(name=name, description=desc, permissions=sorted(perms), is_system=True))
    db.session.commit()


def _pdf_bytes(title, lines):
    from .pdf import make_pdf
    return make_pdf(title, "Board pack – sample document", [("p", line) for line in lines])


def _store_doc(meeting, title, lines, author, classification="confidential", allow_download=True, agenda=None):
    data = _pdf_bytes(title, lines)
    folder = os.path.join(current_app.config["UPLOAD_FOLDER"], "documents")
    os.makedirs(folder, exist_ok=True)
    stored = f"{uuid.uuid4().hex}.pdf"
    with open(os.path.join(folder, stored), "wb") as f:
        f.write(data)
    doc = Document(meeting=meeting, title=title, classification=classification, allow_download=allow_download,
                   created_by=author.id, agenda_item=agenda, current_version=1)
    db.session.add(doc)
    db.session.add(DocumentVersion(document=doc, version=1, filename=title.lower().replace(" ", "-") + ".pdf",
                                   stored_name=f"documents/{stored}", mime="application/pdf", size=len(data),
                                   sha256=hashlib.sha256(data).hexdigest(), note="Initial upload",
                                   uploaded_by=author.id))
    return doc


def _meeting(title, start, host, cls="board", duration=90, status="scheduled", quorum=50, desc="", agenda=()):
    m = Meeting(title=title, classification=cls, scheduled_start=start, duration_minutes=duration, status=status,
                quorum_percent=quorum, host_id=host.id, created_by=host.id, description=desc,
                room_name=f"BoardroomHub-{secrets.token_hex(6)}", passcode=f"{secrets.randbelow(10 ** 6):06d}")
    db.session.add(m)
    for i, (t, presenter, mins) in enumerate(agenda, start=1):
        db.session.add(AgendaItem(meeting=m, position=i, title=t, presenter=presenter, duration_minutes=mins))
    return m


def _invite(m, user, role, voting=None):
    voting = (role in ("chair", "director") and user.can("vote.cast")) if voting is None else voting
    p = Participant(meeting=m, user=user, meeting_role=role, is_voting=voting, rsvp="accepted")
    db.session.add(p)
    return p


def _attend(p, join, leave, late=False, early=False):
    p.attendance_status = "present"
    p.first_join_at = join
    p.last_leave_at = leave
    p.active_seconds = int((leave - join).total_seconds()) if leave else 0
    p.late_flag, p.early_flag = late, early
    db.session.add(AttendanceLog(participant=p, event="join", at=join, ip="10.0.0.12"))
    if leave:
        db.session.add(AttendanceLog(participant=p, event="leave", at=leave, ip="10.0.0.12"))


def seed_demo():
    from .api.minutes import seal_hash
    from .api.voting import close_ballot
    from .audit import log_event

    ensure_roles()
    if User.query.count():
        return False
    roles = {r.name: r for r in Role.query.all()}
    users = {}
    for email, name, title, role, weight in PEOPLE:
        u = User(email=email, full_name=name, title=title, organization="Axiv Holdings Plc", role=roles[role],
                 password_hash=generate_password_hash(DEMO_PASSWORD), status="active", vote_weight=weight)
        db.session.add(u)
        users[email.split("@")[0]] = u
    pending = User(email="newdirector@boardroom.local", full_name="Chanthy Mao", title="Independent Director (nominee)",
                   organization="Axiv Holdings Plc", role=roles["Independent Director"], status="invited")
    db.session.add(pending)
    db.session.flush()
    db.session.add(AuthToken(user_id=pending.id, kind="invite", token_hash=hash_token("demo-invite-token"),
                             expires_at=utcnow() + timedelta(days=30)))
    chair, sec = users["chair"], users["secretary"]
    directors = [users[k] for k in ("vannak", "sreymom", "rithy", "malis")]
    now = utcnow().replace(second=0, microsecond=0)

    # ---------------------------------------------------------- 1. Past meeting: fully governed
    q3_start = (now - timedelta(days=40)).replace(hour=2, minute=0)
    q3 = _meeting("Q3 2026 Board Meeting", q3_start, chair, "board", 120, "ended", 50,
                  "Quarterly results, risk review and dividend decision.",
                  [("Approval of previous minutes", "Dara Kim", 10), ("Q3 financial results", "Malis Pich", 30),
                   ("Enterprise risk review", "Vannak Chea", 30), ("Interim dividend proposal", "Rithy Sok", 20)])
    q3.actual_start, q3.actual_end = q3_start, q3_start + timedelta(minutes=115)
    parts = {"chair": _invite(q3, chair, "chair"), "sec": _invite(q3, sec, "secretary")}
    for d in directors:
        parts[d.email] = _invite(q3, d, "director")
    _invite(q3, users["counsel"], "counsel")
    _invite(q3, users["auditor"], "auditor")
    db.session.flush()
    _attend(parts["chair"], q3_start, q3.actual_end)
    _attend(parts["sec"], q3_start - timedelta(minutes=5), q3.actual_end)
    _attend(parts["vannak@boardroom.local"], q3_start + timedelta(minutes=2), q3.actual_end)
    _attend(parts["rithy@boardroom.local"], q3_start + timedelta(minutes=18), q3.actual_end, late=True)
    _attend(parts["malis@boardroom.local"], q3_start, q3_start + timedelta(minutes=80), early=True)
    for p in q3.participants:
        if p.meeting_role in ("counsel", "auditor"):
            _attend(p, q3_start + timedelta(minutes=1), q3.actual_end)
    ab = AbsenceRequest(meeting=q3, user=users["sreymom"], reason_code="travel",
                        reason_text="Investor roadshow in Singapore", status="approved", reviewed_by=chair.id,
                        reviewed_at=q3_start - timedelta(days=3), created_at=q3_start - timedelta(days=5))
    db.session.add(ab)
    db.session.flush()
    db.session.add(Proxy(meeting=q3, principal_id=users["sreymom"].id, proxy_id=users["vannak"].id,
                         absence_id=ab.id, assigned_by=sec.id, created_at=q3_start - timedelta(days=2)))
    parts["sreymom@boardroom.local"].attendance_status = "proxy"
    mins = Minutes(meeting=q3, status="sealed", current_version=3)
    db.session.add(mins)
    items = q3.agenda_items
    texts = ["Minutes of the Q2 meeting were approved without changes.",
             "Revenue grew 12% year on year to USD 18.4M. Operating margin improved to 21%.",
             "Cyber-security risk upgraded to HIGH. Management to present a mitigation plan in Q4.",
             "The board discussed an interim dividend of USD 0.05 per share; put to a vote."]
    for v in (1, 2, 3):
        db.session.add(MinutesVersion(minutes=mins, version=v, author_id=sec.id,
                                      created_at=q3.actual_end + timedelta(hours=v * 6),
                                      general_notes="Meeting opened at 09:00 by the Chair. Quorum confirmed."
                                      + (" Sreymom Heng represented by proxy (Vannak Chea)." if v == 3 else ""),
                                      items=[{"agenda_item_id": a.id, "title": a.title,
                                              "notes": texts[i] if v > 1 or i < 2 else ""}
                                             for i, a in enumerate(items)],
                                      change_note=["First draft", "Added risk and dividend notes",
                                                   "Final wording after Chair review"][v - 1]))
    items[1].decision = "Q3 financial statements approved."
    items[2].advisory = "Engage external penetration testers before year end."
    items[2].finding = "Two critical vulnerabilities remain open from the Q2 audit."
    items[3].decision = "Interim dividend of USD 0.05 per share approved."
    db.session.flush()
    b1 = Ballot(meeting=q3, agenda_item=items[3], motion="Approve interim dividend of USD 0.05 per share",
                rule="simple", status="closed", opened_at=q3_start + timedelta(minutes=95), created_by=sec.id)
    b2 = Ballot(meeting=q3, agenda_item=items[2], motion="Approve USD 250k cyber-security budget",
                rule="two_thirds", anonymous=True, status="closed", opened_at=q3_start + timedelta(minutes=70),
                created_by=sec.id)
    db.session.add_all([b1, b2])
    db.session.flush()
    for b, choices in ((b1, {"chair": "For", "vannak": "For", "rithy": "For", "malis": "Against", "sreymom": "For"}),
                       (b2, {"chair": "For", "vannak": "For", "rithy": "Abstain", "malis": "For", "sreymom": "For"})):
        for key, choice in choices.items():
            principal = users[key]
            voter = users["vannak"] if key == "sreymom" else principal
            db.session.add(Vote(ballot=b, voter_id=voter.id, principal_id=principal.id, choice=choice,
                                weight=principal.vote_weight if b.weighted else 1,
                                receipt=secrets.token_hex(16), cast_at=b.opened_at + timedelta(minutes=3)))
        db.session.flush()
        close_ballot(b)
        b.closed_at = b.opened_at + timedelta(minutes=10)
    for n, b in enumerate((b1, b2), start=1):
        r = Resolution(number=f"RES-{now.year}-{n:03d}", ballot_id=b.id, meeting=q3, title=b.motion,
                       outcome=b.result["outcome"], tallies=b.result["tallies"], quorum_met=True,
                       certified_by=chair.id, certified_at=b.closed_at)
        r.cert_hash = hashlib.sha256(f"{r.number}{r.title}{r.outcome}".encode()).hexdigest()
        db.session.add(r)
    mins.published_at, mins.published_by = q3.actual_end + timedelta(days=1), sec.id
    mins.sealed_at, mins.sealed_by = q3.actual_end + timedelta(days=2, hours=4), chair.id
    db.session.flush()
    mins.seal_hash = seal_hash(mins)
    _store_doc(q3, "Q3 Financial Statements", ["Revenue: USD 18.4M (+12% YoY)", "Operating margin: 21%",
                                               "Cash position: USD 6.1M"], sec, agenda=items[1])

    # ---------------------------------------------------------- 2. Past committee meeting: quorum breach
    ac_start = (now - timedelta(days=12)).replace(hour=3, minute=0)
    ac = _meeting("Audit Committee Review", ac_start, sec, "committee", 60, "ended", 60,
                  "Internal audit findings and external auditor appointment.",
                  [("Internal audit findings", "Kosal Ly", 30), ("External auditor appointment", "Dara Kim", 20)])
    ac.actual_start, ac.actual_end = ac_start, ac_start + timedelta(minutes=55)
    acp = [_invite(ac, chair, "chair"), _invite(ac, sec, "secretary")] + [_invite(ac, d, "director") for d in directors]
    _invite(ac, users["auditor"], "auditor")
    db.session.flush()
    _attend(acp[0], ac_start, ac.actual_end)
    _attend(acp[1], ac_start, ac.actual_end)
    _attend(acp[2], ac_start + timedelta(minutes=14), ac.actual_end, late=True)
    for p in acp[3:]:
        p.attendance_status = "unexcused"
    for p in ac.participants:
        if p.meeting_role == "auditor":
            _attend(p, ac_start, ac.actual_end)
    acm = Minutes(meeting=ac, status="published", current_version=1, published_at=ac.actual_end + timedelta(hours=20),
                  published_by=sec.id)
    db.session.add(acm)
    db.session.flush()
    db.session.add(MinutesVersion(minutes=acm, version=1, author_id=sec.id, general_notes="Quorum NOT met "
                                  "(2 of 5 voting members). Items discussed for information only.",
                                  items=[{"agenda_item_id": a.id, "title": a.title,
                                          "notes": "Deferred to the next meeting."} for a in ac.agenda_items],
                                  change_note="Draft"))

    # ---------------------------------------------------------- 3. Live meeting (started 10 minutes ago)
    live_start = now - timedelta(minutes=10)
    live = _meeting("Extraordinary Board Meeting – Acquisition Review", live_start, chair, "extraordinary", 90,
                    "live", 50, "Review of the proposed acquisition of Mekong Data Co.",
                    [("Acquisition overview", "Rithy Sok", 30), ("Due diligence findings", "Bopha Nuon", 30),
                     ("Vote on letter of intent", "Dr. Sophea Lim", 20)])
    live.actual_start = live_start
    live.room_url = f"{current_app.config['VIDEO_BASE_URL']}/{live.room_name}"
    live.waiting_room = False
    lp = {"chair": _invite(live, chair, "chair"), "sec": _invite(live, sec, "secretary")}
    for d in directors:
        lp[d.email] = _invite(live, d, "director")
    _invite(live, users["counsel"], "counsel")
    _invite(live, users["observer"], "observer")
    db.session.flush()
    for key in ("chair", "sec", "vannak@boardroom.local", "rithy@boardroom.local"):
        p = lp[key]
        _attend(p, live_start + timedelta(minutes=1), None)
        p.last_leave_at = None
        p.connected = True
        p.current_join_at = live_start + timedelta(minutes=1)
    db.session.add(Ballot(meeting=live, agenda_item=live.agenda_items[2],
                          motion="Authorise the CEO to sign a non-binding letter of intent",
                          description="Letter of intent for the acquisition of Mekong Data Co. at up to USD 12M.",
                          rule="two_thirds", created_by=sec.id))
    _store_doc(live, "Acquisition Due Diligence Report", ["Target: Mekong Data Co.", "Valuation range: USD 10–12M",
                                                          "Key risk: customer concentration (38%)"],
               sec, "strictly_confidential", False, live.agenda_items[1])

    # ---------------------------------------------------------- 4. Upcoming board meeting
    q4_start = (now + timedelta(days=21)).replace(hour=2, minute=0)
    q4 = _meeting("Q4 2026 Board Meeting", q4_start, chair, "board", 120, "scheduled", 50,
                  "FY2027 budget approval and board evaluation.",
                  [("Approval of Q3 minutes", "Dara Kim", 10), ("FY2027 budget", "Malis Pich", 40),
                   ("Board performance evaluation", "Dr. Sophea Lim", 30), ("Any other business", "All", 15)])
    q4p = [_invite(q4, chair, "chair"), _invite(q4, sec, "secretary")] + [_invite(q4, d, "director") for d in directors]
    _invite(q4, users["counsel"], "counsel")
    _invite(q4, users["auditor"], "auditor")
    db.session.flush()
    for p in q4p[2:]:
        p.rsvp = "pending"
    db.session.add(AbsenceRequest(meeting=q4, user=users["malis"], reason_code="medical",
                                  reason_text="Scheduled surgery – medical certificate to follow"))
    _store_doc(q4, "FY2027 Budget Proposal", ["Total budget: USD 21.5M", "Capex: USD 3.2M",
                                              "Headcount growth: +8%"], sec, "confidential", True,
               q4.agenda_items[1])
    db.session.add(Ballot(meeting=q4, agenda_item=q4.agenda_items[1], motion="Approve the FY2027 budget",
                          rule="simple", created_by=sec.id))

    # ---------------------------------------------------------- 5. Recurring monthly risk committee
    series = str(uuid.uuid4())
    from .api.meetings import add_months
    base = (now + timedelta(days=7)).replace(hour=7, minute=0)
    for i in range(3):
        start = add_months(base, i)
        rm = _meeting(f"Risk Committee ({start.strftime('%b %Y')})", start, sec, "committee", 60, "scheduled", 50,
                      "Monthly enterprise risk monitoring.",
                      [("Risk register update", "Vannak Chea", 30), ("Incident report", "Kosal Ly", 20)])
        rm.series_id, rm.recurrence = series, "monthly"
        _invite(rm, sec, "secretary")
        _invite(rm, chair, "chair")
        _invite(rm, users["vannak"], "director")
        _invite(rm, users["sreymom"], "director")
        _invite(rm, users["auditor"], "auditor")

    for u in users.values():
        db.session.add(Notification(user_id=u.id, kind="welcome", title="Welcome to the Boardroom Hub",
                                    body="Your governance workspace is ready.", link="/"))
    db.session.add(Notification(user_id=chair.id, kind="minutes", title="Minutes awaiting your seal",
                                body="Audit Committee Review minutes were published.", link=f"/meetings/{ac.id}"))
    db.session.commit()
    log_event("system.seed", "system", details={"note": "Demo data created"}, user=users["admin"])
    return True


def register_cli(app):
    @app.cli.command("init-db")
    def init_db():
        """Create tables, triggers and default roles."""
        ensure_roles()
        click.echo("Database ready.")

    @app.cli.command("seed")
    def seed():
        """Load demo users and meetings (only into an empty database)."""
        click.echo("Demo data created." if seed_demo() else "Database already has users – nothing to do.")

    @app.cli.command("reset-db")
    @click.confirmation_option(prompt="This deletes ALL data. Continue?")
    def reset_db():
        """Drop and recreate the database with demo data."""
        db.drop_all()
        db.create_all()
        from .audit import install_triggers
        install_triggers()
        seed_demo()
        click.echo("Database reset with demo data.")
