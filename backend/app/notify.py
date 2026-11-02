"""Module 10 – in-app notifications, simulated e-mail outbox, reminders and ICS calendar export."""
from datetime import timedelta

from flask import current_app

from .extensions import db
from .models import EmailOutbox, Meeting, Notification, utcnow


def notify(users, title, body="", link=None, kind="info", email=True, commit=True):
    if not isinstance(users, (list, tuple, set)):
        users = [users]
    seen = set()
    for u in users:
        if u is None or u.id in seen:
            continue
        seen.add(u.id)
        if u.notify_inapp:
            db.session.add(Notification(user_id=u.id, kind=kind, title=title, body=body, link=link))
        if email and u.notify_email:
            url = (current_app.config["FRONTEND_URL"] + link) if link else current_app.config["FRONTEND_URL"]
            db.session.add(EmailOutbox(to_email=u.email, subject=f"[Boardroom Hub] {title}",
                                       body=f"Dear {u.full_name},\n\n{body}\n\nOpen: {url}\n\n— Boardroom Hub",
                                       kind=kind))
    if commit:
        db.session.commit()


def send_email(to_email, subject, text, kind="general"):
    db.session.add(EmailOutbox(to_email=to_email, subject=subject, body=text, kind=kind))
    db.session.commit()


def meeting_users(meeting):
    return [p.user for p in meeting.participants]


def fmt(dt):
    return dt.strftime("%d %b %Y %H:%M UTC")


def send_due_reminders(now=None):
    """Send T-24h and T-1h reminders for upcoming meetings. Returns how many reminders were sent."""
    now = now or utcnow()
    sent = 0
    upcoming = Meeting.query.filter(Meeting.status == "scheduled", Meeting.scheduled_start > now,
                                    Meeting.scheduled_start <= now + timedelta(hours=24)).all()
    for m in upcoming:
        delta = m.scheduled_start - now
        if delta <= timedelta(hours=1) and not m.reminder_1h_sent:
            notify(meeting_users(m), f"Starts within 1 hour: {m.title}",
                   f"Your meeting starts at {fmt(m.scheduled_start)}.", f"/meetings/{m.id}", "reminder", commit=False)
            m.reminder_1h_sent = True
            m.reminder_24h_sent = True
            sent += 1
        elif not m.reminder_24h_sent:
            notify(meeting_users(m), f"Reminder (24h): {m.title}",
                   f"Your meeting is scheduled for {fmt(m.scheduled_start)}.", f"/meetings/{m.id}", "reminder",
                   commit=False)
            m.reminder_24h_sent = True
            sent += 1
    db.session.commit()
    return sent


def _ics_escape(text):
    return (text or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _ics_dt(dt):
    return dt.strftime("%Y%m%dT%H%M%SZ")


def build_ics(meetings):
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Boardroom Hub//Governance Meetings//EN",
             "CALSCALE:GREGORIAN", "METHOD:PUBLISH"]
    for m in meetings:
        if m.status == "cancelled":
            continue
        agenda = "\n".join(f"{a.position}. {a.title}" for a in m.agenda_items)
        lines += [
            "BEGIN:VEVENT",
            f"UID:meeting-{m.id}@boardroom-hub",
            f"DTSTAMP:{_ics_dt(utcnow())}",
            f"DTSTART:{_ics_dt(m.scheduled_start)}",
            f"DTEND:{_ics_dt(m.scheduled_end)}",
            f"SUMMARY:{_ics_escape(m.title)}",
            f"DESCRIPTION:{_ics_escape((m.description or '') + chr(10) + 'Agenda:' + chr(10) + agenda)}",
            f"LOCATION:{_ics_escape('Virtual Boardroom ' + (m.room_name or ''))}",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"
