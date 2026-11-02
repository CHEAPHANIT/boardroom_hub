# Enterprise Governance & Boardroom Meeting Hub

Topic Assignment Room 112, Project 1. This is an executive-grade web platform for corporate boards, advisory councils and executive committees.

| Layer | Technology |
|---|---|
| Frontend | **Vue 3** (Vite 6, Vue Router, Pinia, Axios) |
| Backend | **Python Flask RESTful API** (Flask-RESTX with OpenAPI / **Swagger UI**), JWT authentication |
| Database | **SQLite** (Flask-SQLAlchemy). It is created automatically, so there is no database server to install. |
| PDF / reports | ReportLab (minutes, attendance sheets, voting summaries, audit trails, reports) |

---

## 1. Quick start (Windows)

You need **Python 3.10+** and **Node.js 18 or 20+**.

### Option A: double-click

1. `start-backend.bat`: creates a virtual environment, installs the packages and starts the API on **http://localhost:5000**
2. `start-frontend.bat`: installs the npm packages and starts Vue on **http://localhost:5173**
3. Open **http://localhost:5173** and sign in with a demo account (see section 2).

### Option B: commands

```bash
# Terminal 1 – backend
cd backend
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python run.py                      # API  http://localhost:5000   Swagger  http://localhost:5000/api/docs

# Terminal 2 – frontend
cd frontend
npm install
npm run dev                        # App  http://localhost:5173
```

The first `python run.py` creates `backend/instance/boardroom.db` and loads the demo data. It also runs a small background job every 60 seconds that sends the T-24h and T-1h meeting reminders.

**One-server mode (deployment):** run `npm run build` in `frontend`. Flask then also serves the built app at http://localhost:5000.

**Reset the database:** stop the API and delete `backend/instance/`, then start it again. You can also run `flask --app run reset-db` inside `backend`.

---

## 2. Demo accounts

Every account uses the password **`Password123!`**.

| Role | E-mail | What to try |
|---|---|---|
| Administrator | admin@boardroom.local | Users, roles, access matrix, audit trail, archive |
| Board Chair | chair@boardroom.local | Start/end sessions, seal minutes, certify resolutions |
| Company Secretary | secretary@boardroom.local | Create meetings, write minutes, run ballots, approve absences |
| Independent Director | vannak@boardroom.local / sreymom@boardroom.local | Join, vote, vote as proxy, request absence |
| Executive Director | rithy@boardroom.local / malis@boardroom.local | Same as above |
| Legal Counsel | counsel@boardroom.local | Non-voting participant |
| Auditor | auditor@boardroom.local | Read-only access, audit trail, exports |
| Observer | observer@boardroom.local | Read-only |

The seeded data includes:

- a fully governed past meeting (sealed minutes, a proxy, 2 certified resolutions)
- a committee meeting with a **quorum breach**
- a meeting that is **live right now** with a draft ballot
- an upcoming board meeting with a pending absence request
- a **monthly recurring** Risk Committee series

There is also an invited user whose activation link is `/activate?token=demo-invite-token`.

**E-mail is simulated.** Invitations, reminders and password-reset links appear in **Administration → E-mail Outbox**, so no SMTP server is needed. The links are also shown on screen in demo mode.

---

## 3. The 10 modules

| # | Module | Main features | API namespace |
|---|---|---|---|
| 1 | Meeting Lifecycle & Virtual Boardroom | Create, update and reschedule (with notices), cancel (broadcast alert), start/end the live video bridge, room security (passcode, waiting room, watermark, room lock, co-host), recurring bi-weekly/monthly/quarterly schedules | `/api/meetings` |
| 2 | Participant & Attendance Tracking | Add participants, roster with real-time connection/RSVP/role, attendance status (present/excused/unexcused/proxy), automatic join/exit timestamps and active minutes, late/early alerts, digital attendance sheet (PDF/CSV), live quorum | `/api/attendance` |
| 3 | Absence & Proxy Approval Workflow | Absence requests with reason codes, pending queue, approve/reject, supporting documents (type and size checked), assign/revoke voting proxy (rules enforced), history log | `/api/absences` |
| 4 | Structured Minutes (MOM) & Notes | Notes per agenda item, a new version on every save, side-by-side diff, agenda summary (decisions, advisories, findings), publish (frozen), digital **seal** by the Chair (SHA-256), PDF export with signatures and watermark | `/api/minutes` |
| 5 | Voting, Polling & Resolution Tracker | Ballots (simple majority, 2/3, 3/4, unanimous, custom options, anonymous, weighted), live vote window, identified/anonymous/proxy votes, close (late votes blocked), quorum and percentages, certified resolution register (`RES-YYYY-NNN`), signed summary PDF/CSV | `/api/voting` |
| 6 | Roles & Permissions (RBAC) | Custom roles, 28 granular permissions (read/write/vote/sign/export), assign user to role, revoke/modify access, access control matrix | `/api/roles`, `/api/users` |
| 7 | Activity Log & Audit Trail | Every action logged with user, action, IP, **device fingerprint** and time; **hash-chained** and **write-once** (SQLite triggers block UPDATE/DELETE); filter/search; security anomalies (wrong passcodes, blocked downloads, brute force); locked archive batches; signed CSV/PDF export; integrity check | `/api/audit` |
| 8 | User Authentication & Account Security | Invite & activate accounts, JWT login with refresh tokens, **TOTP MFA** (QR code), password reset by e-mail link, lockout after 5 failed attempts, executive profile | `/api/auth`, `/api/users` |
| 9 | Board Pack & Document Repository | Upload board papers, link to agenda items, **secure viewer** with watermark, version history, download restricted by role and classification | `/api/documents` |
| 10 | Notifications & Governance Dashboard | In-app notification centre, e-mail outbox, invitations and T-24h/T-1h reminders, ICS calendar export, executive KPI dashboard, attendance/voting/compliance reports (PDF/CSV) | `/api/notifications`, `/api/dashboard` |

You can explore and try every endpoint in **Swagger UI: http://localhost:5000/api/docs**. Click **Authorize** and paste `Bearer <access_token>` from `POST /api/auth/login`.

---

## 3a. Language – English / ខ្មែរ

Every screen can be shown in **English or Khmer**. Click **EN | ខ្មែរ** at the top of the page (or on the sign-in page), or choose the language in *My profile*. The choice is remembered in the browser.

- Dictionaries: `frontend/src/i18n/en.js` and `frontend/src/i18n/km.js` (same keys).
- Messages from the API (errors, notifications, security alerts) are translated in `frontend/src/i18n/server-km.js`.
- Khmer uses the *Kantumruy Pro* font (Google Fonts); offline it falls back to *Khmer UI* / *Khmer OS*, which Windows already has.
- What stays as typed: meeting titles, names, minutes text and other data users enter. Generated PDFs and e-mails are in English.
- No extra npm package is needed.

## 4. Suggested demo script (about 5 minutes)

1. **Chair** → Dashboard: live meeting banner, KPIs and the quorum breach.
2. Open the live meeting:
   - **Participants** tab: roster and live quorum.
   - **Voting** tab: launch the ballot and vote *For*.
3. **Director** (vannak): vote. Then **rithy**: vote *Against*.
4. **Secretary**: close the vote. The result is CARRIED with 2/3. **Chair**: record the legal resolution. Export the summary PDF.
5. **Board Pack** tab: open the strictly confidential report in the secure viewer. A director's download attempt is blocked and shows up as an anomaly in the audit trail.
6. **Chair**: end the session. Attendance is finalised and absentees are marked unexcused.
7. Open **Q3 2026 Board Meeting → Minutes**: sealed minutes, compare v2→v3, export the PDF.
8. **Admin** → Audit Trail: *Verify integrity*, view anomalies, *Lock & archive*, signed CSV export.

---

## 5. Tests

```bash
cd backend
python -m pytest -q
```

Seven end-to-end API tests cover all 10 modules: lockout/reset, invite/MFA, RBAC, the full meeting lifecycle (proxy voting, quorum, minutes seal), documents, the audit chain write-once triggers, and reports.

---

## 6. Project structure

```
boardroom-hub-sqlite/
├── backend/
│   ├── run.py                 # start the API (+ reminder job, auto-seed)
│   ├── requirements.txt
│   ├── app/
│   │   ├── __init__.py        # app factory, CORS, Swagger, serves frontend/dist
│   │   ├── config.py          # SQLite path, JWT lifetimes, thresholds
│   │   ├── models.py          # 22 SQLAlchemy models
│   │   ├── security.py        # JWT, permissions catalogue, default roles
│   │   ├── audit.py           # hash chain, triggers, anomaly flagging
│   │   ├── notify.py          # notifications, outbox, reminders, ICS
│   │   ├── pdf.py             # ReportLab PDFs with watermark
│   │   ├── uploads.py         # safe file uploads
│   │   ├── seed.py            # demo data + CLI (init-db, seed, reset-db)
│   │   └── api/               # one Flask-RESTX namespace per module
│   └── tests/test_api.py
└── frontend/
    ├── vite.config.js         # /api proxy → :5000
    └── src/
        ├── api/http.js        # Axios + JWT refresh + device fingerprint
        ├── stores/            # Pinia (auth, toast)
        ├── router/            # permission-aware routes
        ├── components/        # AppShell, Modal, DocViewer, …
        └── views/             # Dashboard, Meetings (+ tabs), Absences, Resolutions,
                               # Reports, Notifications, Profile, Audit, admin/*
```

### Notes

- **Video bridge:** the live room embeds a Jitsi Meet room (`https://meet.jit.si/<random room>`). This needs internet access. To use another provider, change `VIDEO_BASE_URL` in `backend/app/config.py`.
- **Time:** times are stored in UTC and shown in the browser's local time zone.
- **Uploads:** files are stored in `backend/instance/uploads/`. The limit is 10 MB, and the allowed types are pdf, Office, png, jpg and txt.
