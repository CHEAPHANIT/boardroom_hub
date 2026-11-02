"""End-to-end API tests covering all 10 modules.  Run:  python -m pytest -q"""
import io
from datetime import datetime, timedelta, timezone

import pyotp
import pytest
from sqlalchemy import text

from app import create_app
from app.config import TestConfig
from app.extensions import db
from app.seed import seed_demo

PW = "Password123!"


@pytest.fixture()
def app(tmp_path):
    class Cfg(TestConfig):
        UPLOAD_FOLDER = str(tmp_path / "uploads")

    application = create_app(Cfg)
    with application.app_context():
        seed_demo()
    yield application
    with application.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def login(client, email, password=PW):
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.json
    return {"Authorization": "Bearer " + r.json["access_token"]}


def uid(client, h, email):
    return next(u["id"] for u in client.get("/api/users/directory", headers=h).json if u["email"] == email)


def soon(minutes=30):
    return (datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=minutes)).isoformat() + "Z"


# ----------------------------------------------------------------------------- Module 8
def test_login_lockout_and_reset(client):
    for _ in range(5):
        assert client.post("/api/auth/login", json={"email": "rithy@boardroom.local", "password": "bad"}).status_code == 401
    r = client.post("/api/auth/login", json={"email": "rithy@boardroom.local", "password": PW})
    assert r.status_code == 423
    r = client.post("/api/auth/forgot-password", json={"email": "rithy@boardroom.local"})
    token = r.json["dev_reset_link"].split("token=")[1]
    assert client.post("/api/auth/reset-password", json={"token": token, "new_password": "NewPass2026"}).status_code == 200
    login(client, "rithy@boardroom.local", "NewPass2026")
    admin = login(client, "admin@boardroom.local")
    anomalies = client.get("/api/audit/anomalies", headers=admin).json
    assert any(a["kind"] == "brute_force" for a in anomalies)


def test_invite_activate_and_mfa(client):
    sec = login(client, "secretary@boardroom.local")
    roles = client.get("/api/roles", headers=sec).json
    rid = next(r["id"] for r in roles if r["name"] == "Independent Director")
    r = client.post("/api/users/invite", headers=sec, json={"email": "new@x.com", "full_name": "New Director",
                                                            "role_id": rid})
    assert r.status_code == 201
    token = r.json["dev_invite_link"].split("token=")[1]
    assert client.get(f"/api/auth/invite/{token}").json["email"] == "new@x.com"
    r = client.post("/api/auth/activate", json={"token": token, "password": "Welcome2026"})
    h = {"Authorization": "Bearer " + r.json["access_token"]}
    secret = client.post("/api/auth/mfa/setup", headers=h).json["secret"]
    assert client.post("/api/auth/mfa/enable", headers=h, json={"code": pyotp.TOTP(secret).now()}).status_code == 200
    r = client.post("/api/auth/login", json={"email": "new@x.com", "password": "Welcome2026"})
    assert r.json["mfa_required"]
    r = client.post("/api/auth/mfa/verify", json={"mfa_token": r.json["mfa_token"], "code": pyotp.TOTP(secret).now()})
    assert r.status_code == 200 and r.json["user"]["mfa_enabled"]


# ----------------------------------------------------------------------------- Module 6
def test_rbac_roles_matrix_and_denial(client):
    admin = login(client, "admin@boardroom.local")
    r = client.post("/api/roles", headers=admin, json={"name": "Audit Committee Member",
                                                       "permissions": ["meeting.view", "minutes.view"]})
    assert r.status_code == 201
    matrix = client.get("/api/roles/matrix", headers=admin).json
    assert any(p["code"] == "vote.cast" for p in matrix["permissions"])
    observer = login(client, "observer@boardroom.local")
    assert client.post("/api/meetings", headers=observer, json={"title": "x", "scheduled_start": soon()}).status_code == 403
    assert client.get("/api/audit/logs", headers=observer).status_code == 403
    uid_obs = uid(client, admin, "observer@boardroom.local")
    assert client.post(f"/api/users/{uid_obs}/deactivate", headers=admin).status_code == 200
    assert client.get("/api/auth/me", headers=observer).status_code == 401


# ----------------------------------------------------------------------------- Modules 1-5 full lifecycle
def test_full_meeting_lifecycle(client):
    sec = login(client, "secretary@boardroom.local")
    chair = login(client, "chair@boardroom.local")
    ids = {k: uid(client, sec, f"{k}@boardroom.local") for k in ("chair", "vannak", "sreymom", "rithy", "malis")}
    r = client.post("/api/meetings", headers=sec, json={
        "title": "Test Board Meeting", "scheduled_start": soon(5), "duration_minutes": 60, "classification": "board",
        "passcode": "1234", "waiting_room": False, "cohost_id": ids["chair"],
        "agenda_items": [{"title": "Budget"}, {"title": "AOB"}],
        "participants": [{"user_id": ids["chair"], "meeting_role": "chair"}] +
                        [{"user_id": ids[k], "meeting_role": "director"} for k in ("vannak", "sreymom", "rithy", "malis")]})
    assert r.status_code == 201, r.json
    mid = r.json["id"]
    # recurring schedule
    r = client.post("/api/meetings", headers=sec, json={"title": "Risk", "scheduled_start": soon(60 * 48),
                                                        "recurrence": "quarterly", "occurrences": 4})
    assert len(r.json["series_meeting_ids"]) == 4
    # reschedule + ICS
    r = client.put(f"/api/meetings/{mid}", headers=sec, json={"duration_minutes": 90})
    assert r.json["duration_minutes"] == 90
    assert b"BEGIN:VCALENDAR" in client.get(f"/api/meetings/{mid}/ics", headers=sec).data
    # absence + proxy (Sreymom absent, Vannak proxy)
    sreymom = login(client, "sreymom@boardroom.local")
    r = client.post("/api/absences", headers=sreymom, json={"meeting_id": mid, "reason_code": "travel"})
    aid = r.json["id"]
    data = {"file": (io.BytesIO(b"%PDF-1.4 ticket"), "ticket.pdf")}
    assert client.post(f"/api/absences/{aid}/documents", headers=sreymom, data=data,
                       content_type="multipart/form-data").status_code == 201
    bad = {"file": (io.BytesIO(b"MZ"), "virus.exe")}
    assert client.post(f"/api/absences/{aid}/documents", headers=sreymom, data=bad,
                       content_type="multipart/form-data").status_code == 400
    assert client.post(f"/api/absences/{aid}/approve", headers=chair, json={"comment": "OK"}).json["status"] == "approved"
    r = client.post("/api/absences/proxies", headers=sec, json={"meeting_id": mid, "principal_id": ids["sreymom"],
                                                                "proxy_id": ids["vannak"]})
    assert r.status_code == 201, r.json
    # start, join with passcode
    assert client.post(f"/api/meetings/{mid}/start", headers=chair).json["status"] == "live"
    vannak = login(client, "vannak@boardroom.local")
    rithy = login(client, "rithy@boardroom.local")
    assert client.post(f"/api/attendance/{mid}/join", headers=vannak, json={"passcode": "0000"}).status_code == 403
    assert client.post(f"/api/attendance/{mid}/join", headers=vannak, json={"passcode": "1234"}).json["room_url"]
    client.post(f"/api/attendance/{mid}/join", headers=rithy, json={"passcode": "1234"})
    client.post(f"/api/attendance/{mid}/join", headers=chair, json={})
    roster = client.get(f"/api/attendance/{mid}/roster", headers=sec).json
    assert roster["quorum"]["met"] and roster["quorum"]["present"] == 4  # chair, vannak, rithy, sreymom(proxy)
    # voting: supermajority, proxy vote, duplicate blocked
    r = client.post("/api/voting/ballots", headers=sec, json={"meeting_id": mid, "motion": "Approve budget",
                                                              "rule": "two_thirds"})
    bid = r.json["id"]
    assert client.post(f"/api/voting/ballots/{bid}/launch", headers=sec, json={}).json["status"] == "open"
    assert client.post(f"/api/voting/ballots/{bid}/vote", headers=vannak, json={"choice": "For"}).status_code == 201
    assert client.post(f"/api/voting/ballots/{bid}/vote", headers=vannak,
                       json={"choice": "For", "on_behalf_of": ids["sreymom"]}).status_code == 201
    assert client.post(f"/api/voting/ballots/{bid}/vote", headers=vannak, json={"choice": "Against"}).status_code == 409
    assert client.post(f"/api/voting/ballots/{bid}/vote", headers=rithy, json={"choice": "Against"}).status_code == 201
    assert client.post(f"/api/voting/ballots/{bid}/vote", headers=chair, json={"choice": "For"}).status_code == 201
    malis = login(client, "malis@boardroom.local")
    assert client.post(f"/api/voting/ballots/{bid}/vote", headers=malis, json={"choice": "For"}).status_code == 403
    r = client.post(f"/api/voting/ballots/{bid}/close", headers=sec)
    assert r.json["result"]["passed"] and r.json["result"]["support_percent"] == 75.0
    assert client.post(f"/api/voting/ballots/{bid}/vote", headers=rithy, json={"choice": "For"}).status_code == 400
    r = client.post(f"/api/voting/ballots/{bid}/resolution", headers=chair, json={})
    assert r.json["number"].startswith("RES-")
    assert client.get(f"/api/voting/ballots/{bid}/export?format=pdf", headers=sec).data[:4] == b"%PDF"
    # leave early -> alert; end meeting
    client.post(f"/api/attendance/{mid}/leave", headers=rithy)
    assert client.get(f"/api/attendance/{mid}/alerts", headers=sec).json
    assert client.post(f"/api/meetings/{mid}/end", headers=chair).json["status"] == "ended"
    roster = client.get(f"/api/attendance/{mid}/roster", headers=sec).json
    statuses = {p["user"]["email"]: p["attendance_status"] for p in roster["participants"]}
    assert statuses["malis@boardroom.local"] == "unexcused" and statuses["sreymom@boardroom.local"] == "proxy"
    assert client.get(f"/api/attendance/{mid}/sheet?format=csv", headers=sec).status_code == 200
    # minutes: versions, diff, publish, seal, locked, pdf
    agenda = client.get(f"/api/meetings/{mid}", headers=sec).json["agenda_items"]
    client.put(f"/api/minutes/{mid}", headers=sec, json={"general_notes": "Opened 09:00", "items": [
        {"agenda_item_id": agenda[0]["id"], "notes": "Budget discussed"}]})
    client.put(f"/api/minutes/{mid}", headers=sec, json={"general_notes": "Opened 09:02", "items": [
        {"agenda_item_id": agenda[0]["id"], "notes": "Budget approved"}], "change_note": "fix"})
    assert len(client.get(f"/api/minutes/{mid}/versions", headers=sec).json) == 2
    assert any(line["kind"] == "add" for line in client.get(f"/api/minutes/{mid}/diff/1/2", headers=sec).json["lines"])
    client.put(f"/api/minutes/{mid}/agenda/{agenda[0]['id']}", headers=sec, json={"decision": "Budget approved"})
    assert client.post(f"/api/minutes/{mid}/seal", headers=chair).status_code == 400  # must publish first
    assert client.post(f"/api/minutes/{mid}/publish", headers=sec).json["status"] == "published"
    assert client.put(f"/api/minutes/{mid}", headers=sec, json={"general_notes": "x"}).status_code == 423
    r = client.post(f"/api/minutes/{mid}/seal", headers=chair)
    assert r.json["status"] == "sealed" and r.json["seal_valid"]
    assert client.get(f"/api/minutes/{mid}/pdf", headers=chair).data[:4] == b"%PDF"


# ----------------------------------------------------------------------------- Module 9
def test_documents_versions_and_download_control(client):
    sec = login(client, "secretary@boardroom.local")
    vannak = login(client, "vannak@boardroom.local")
    meetings = client.get("/api/meetings", headers=sec).json
    mid = next(m["id"] for m in meetings if m["title"] == "Q4 2026 Board Meeting")
    data = {"meeting_id": str(mid), "title": "Strategy paper", "classification": "strictly_confidential",
            "allow_download": "false", "file": (io.BytesIO(b"%PDF-1.4 strategy"), "strategy.pdf")}
    r = client.post("/api/documents", headers=sec, data=data, content_type="multipart/form-data")
    assert r.status_code == 201
    did = r.json["id"]
    r = client.post(f"/api/documents/{did}/versions", headers=sec, content_type="multipart/form-data",
                    data={"note": "v2", "file": (io.BytesIO(b"%PDF-1.4 strategy v2"), "strategy-v2.pdf")})
    assert r.json["current_version"] == 2
    assert client.get(f"/api/documents/{did}/view", headers=vannak).status_code == 200
    assert client.get(f"/api/documents/{did}/download", headers=vannak).status_code == 403
    admin = login(client, "admin@boardroom.local")
    assert any(a["kind"] == "unauthorized_access" for a in client.get("/api/audit/anomalies", headers=admin).json)


# ----------------------------------------------------------------------------- Module 7 + 10
def test_audit_chain_is_write_once_and_exports(app, client):
    admin = login(client, "admin@boardroom.local")
    assert client.get("/api/audit/verify", headers=admin).json["valid"]
    with app.app_context():
        with pytest.raises(Exception):
            db.session.execute(text("UPDATE audit_logs SET action='tampered' WHERE id=1"))
            db.session.commit()
        db.session.rollback()
        with pytest.raises(Exception):
            db.session.execute(text("DELETE FROM audit_logs"))
            db.session.commit()
        db.session.rollback()
    r = client.post("/api/audit/archives", headers=admin, json={"note": "Quarter close"})
    assert r.status_code == 201
    assert client.get(f"/api/audit/archives/{r.json['id']}/verify", headers=admin).json["valid"]
    csv_data = client.get("/api/audit/export?format=csv", headers=admin).data.decode()
    assert "signature_sha256" in csv_data
    assert client.get("/api/audit/export?format=pdf", headers=admin).data[:4] == b"%PDF"
    logs = client.get("/api/audit/logs?category=auth", headers=admin).json
    assert logs["total"] >= 1


def test_dashboard_reports_notifications(client):
    chair = login(client, "chair@boardroom.local")
    d = client.get("/api/dashboard", headers=chair).json
    assert d["kpis"]["quorum_breaches"] >= 1 and d["kpis"]["live_meetings"] == 1
    for kind in ("attendance", "voting", "compliance"):
        assert client.get(f"/api/dashboard/reports/{kind}", headers=chair).status_code == 200
        assert client.get(f"/api/dashboard/reports/{kind}?format=pdf", headers=chair).data[:4] == b"%PDF"
    n = client.get("/api/notifications", headers=chair).json
    assert n["unread"] >= 1
    client.post("/api/notifications/read-all", headers=chair)
    assert client.get("/api/notifications", headers=chair).json["unread"] == 0
    assert b"VCALENDAR" in client.get("/api/meetings/calendar.ics", headers=chair).data
    sec = login(client, "secretary@boardroom.local")
    assert client.post("/api/notifications/send-reminders", headers=sec).status_code == 200
    assert client.get("/api/notifications/outbox", headers=sec).status_code == 200
