"""Module 5 – Voting, Polling & Resolution Tracker."""
import csv
import hashlib
import io
import json
import secrets
from datetime import timedelta

from flask import Response, request
from flask_restx import Namespace, Resource, abort, fields

from ..audit import audit
from ..extensions import db
from ..models import Ballot, Meeting, Proxy, Resolution, Vote, iso, utcnow
from ..notify import notify
from ..pdf import make_pdf
from ..security import auth_required, body, current_user, get_or_404, need, require_perm
from .attendance import quorum_status
from .meetings import can_view, load_visible

ns = Namespace("voting", description="Module 5 – ballots, live votes, quorum, resolutions and voting summaries")

ballot_model = ns.model("BallotIn", {
    "meeting_id": fields.Integer(required=True),
    "motion": fields.String(required=True, example="Approve the FY2027 budget"),
    "description": fields.String(example="Budget of USD 4.2M as presented by the CFO"),
    "rule": fields.String(example="simple", enum=list(Ballot.RULE_LABELS)),
    "anonymous": fields.Boolean(example=False),
    "weighted": fields.Boolean(example=False),
    "options": fields.List(fields.String, example=["For", "Against", "Abstain"]),
    "agenda_item_id": fields.Integer(),
})
THRESHOLD = {"simple": 0.5, "two_thirds": 2 / 3, "three_quarters": 0.75}


def load_ballot(ballot_id):
    b = get_or_404(Ballot, ballot_id, "Ballot")
    if not can_view(b.meeting, current_user()):
        abort(403, "You are not invited to this meeting.")
    return b


def _check_open(b):
    if b.status == "open" and b.closes_at and utcnow() > b.closes_at:
        close_ballot(b)
        db.session.commit()
    if b.status != "open":
        abort(400, "Voting is closed for this ballot." if b.status == "closed" else "This ballot has not been launched.")


def compute_result(b):
    tallies = {opt: {"option": opt, "votes": 0, "weight": 0} for opt in b.options}
    for v in b.votes:
        t = tallies.setdefault(v.choice, {"option": v.choice, "votes": 0, "weight": 0})
        t["votes"] += 1
        t["weight"] += v.weight
    total_weight = sum(t["weight"] for t in tallies.values())
    for t in tallies.values():
        t["percent"] = round(100 * t["weight"] / total_weight, 1) if total_weight else 0.0
    quorum = quorum_status(b.meeting)
    result = {"tallies": list(tallies.values()), "total_votes": len(b.votes), "total_weight": total_weight,
              "quorum": quorum, "rule": b.rule, "rule_label": Ballot.RULE_LABELS.get(b.rule, b.rule)}
    if "For" in tallies and "Against" in tallies:
        yes, no = tallies["For"]["weight"], tallies["Against"]["weight"]
        decisive = yes + no
        if b.rule == "unanimous":
            ok = yes > 0 and no == 0
        else:
            ok = decisive > 0 and (yes / decisive > THRESHOLD[b.rule] if b.rule == "simple"
                                   else yes / decisive >= THRESHOLD[b.rule])
        result["support_percent"] = round(100 * yes / decisive, 1) if decisive else 0.0
        result["passed"] = bool(ok and quorum["met"])
        result["outcome"] = "passed" if result["passed"] else "failed"
        result["outcome_label"] = ("CARRIED" if result["passed"] else
                                   "NOT CARRIED – quorum not met" if not quorum["met"] else "NOT CARRIED")
    else:
        best = max(tallies.values(), key=lambda t: t["weight"]) if tallies else None
        tie = best and sum(1 for t in tallies.values() if t["weight"] == best["weight"]) > 1
        result["winner"] = None if (not best or tie or not best["weight"]) else best["option"]
        result["passed"] = bool(result["winner"] and quorum["met"])
        result["outcome"] = "passed" if result["passed"] else "failed"
        result["outcome_label"] = (f"DECIDED: {result['winner']}" if result["passed"] else
                                   "NO DECISION – quorum not met" if not quorum["met"] else "NO DECISION (tie)")
    return result


def close_ballot(b):
    b.status = "closed"
    b.closed_at = min(utcnow(), b.closes_at) if b.closes_at else utcnow()
    b.result = compute_result(b)


def _voting_participant(meeting, user_id):
    return next((p for p in meeting.participants if p.user_id == user_id and p.is_voting), None)


@ns.route("/ballots")
class BallotList(Resource):
    @auth_required("meeting.view")
    def get(self):
        """List ballots (?meeting_id=, ?status=)."""
        user = current_user()
        q = Ballot.query
        if request.args.get("meeting_id"):
            load_visible(request.args["meeting_id"])
            q = q.filter_by(meeting_id=int(request.args["meeting_id"]))
        if request.args.get("status"):
            q = q.filter(Ballot.status.in_(request.args["status"].split(",")))
        out = []
        for b in q.order_by(Ballot.created_at.desc()).all():
            if b.status == "open" and b.closes_at and utcnow() > b.closes_at:
                close_ballot(b)
                db.session.commit()
            if can_view(b.meeting, user):
                out.append(b.to_dict(viewer=user))
        return out

    @ns.expect(ballot_model)
    @auth_required("vote.manage")
    def post(self):
        """Create ballot: motion, voting rule (simple majority vs supermajority) and choice options."""
        data = body()
        need(data, "meeting_id", "motion")
        meeting = load_visible(data["meeting_id"])
        if meeting.status in ("cancelled", "ended"):
            abort(400, f"Cannot create a ballot for a {meeting.status} meeting.")
        rule = data.get("rule") or "simple"
        if rule not in Ballot.RULE_LABELS:
            abort(400, "Rule must be simple, two_thirds, three_quarters or unanimous.")
        options = [str(o).strip() for o in (data.get("options") or ["For", "Against", "Abstain"]) if str(o).strip()]
        if len(options) < 2 or len(set(options)) != len(options):
            abort(400, "Give at least two different options.")
        agenda_id = data.get("agenda_item_id")
        if agenda_id and not any(a.id == int(agenda_id) for a in meeting.agenda_items):
            abort(400, "Agenda item does not belong to this meeting.")
        b = Ballot(meeting_id=meeting.id, motion=data["motion"].strip(), description=data.get("description", ""),
                   rule=rule, anonymous=bool(data.get("anonymous")), weighted=bool(data.get("weighted")),
                   options=options, agenda_item_id=int(agenda_id) if agenda_id else None,
                   created_by=current_user().id)
        db.session.add(b)
        db.session.commit()
        audit("ballot.create", "vote", "ballot", b.id, meeting.id, motion=b.motion, rule=rule)
        return b.to_dict(viewer=current_user()), 201


@ns.route("/ballots/<int:ballot_id>")
class BallotItem(Resource):
    @auth_required("meeting.view")
    def get(self, ballot_id):
        b = load_ballot(ballot_id)
        if b.status == "open" and b.closes_at and utcnow() > b.closes_at:
            close_ballot(b)
            db.session.commit()
        d = b.to_dict(viewer=current_user())
        d["eligible"] = _eligibility(b, current_user())
        return d

    @auth_required("vote.manage")
    def put(self, ballot_id):
        """Edit a draft ballot."""
        b = load_ballot(ballot_id)
        if b.status != "draft":
            abort(400, "Only draft ballots can be edited.")
        data = body()
        if data.get("motion"):
            b.motion = data["motion"].strip()
        if "description" in data:
            b.description = data["description"] or ""
        if data.get("rule"):
            if data["rule"] not in Ballot.RULE_LABELS:
                abort(400, "Invalid rule.")
            b.rule = data["rule"]
        for f in ("anonymous", "weighted"):
            if f in data:
                setattr(b, f, bool(data[f]))
        if data.get("options"):
            opts = [str(o).strip() for o in data["options"] if str(o).strip()]
            if len(opts) < 2 or len(set(opts)) != len(opts):
                abort(400, "Give at least two different options.")
            b.options = opts
        db.session.commit()
        audit("ballot.update", "vote", "ballot", b.id, b.meeting_id)
        return b.to_dict(viewer=current_user())

    @auth_required("vote.manage")
    def delete(self, ballot_id):
        b = load_ballot(ballot_id)
        if b.status != "draft":
            abort(400, "Only draft ballots can be deleted.")
        mid = b.meeting_id
        db.session.delete(b)
        db.session.commit()
        audit("ballot.delete", "vote", "ballot", ballot_id, mid)
        return {"message": "Ballot deleted"}


def _eligibility(b, user):
    """Which members this user may vote for (self and/or proxy principals)."""
    meeting = b.meeting
    out = []
    if not user.can("vote.cast"):
        return out
    voted = {v.principal_id for v in b.votes}
    me = _voting_participant(meeting, user.id)
    if me and me.attendance_status == "present":
        out.append({"user": user.brief(), "self": True, "already_voted": user.id in voted})
    for px in Proxy.query.filter_by(meeting_id=meeting.id, proxy_id=user.id, revoked=False).all():
        if _voting_participant(meeting, px.principal_id):
            out.append({"user": px.principal.brief(), "self": False, "already_voted": px.principal_id in voted})
    return out


@ns.route("/ballots/<int:ballot_id>/launch")
class Launch(Resource):
    @auth_required("vote.manage")
    def post(self, ballot_id):
        """Launch live vote: opens a real-time voting window during the live meeting."""
        b = load_ballot(ballot_id)
        if b.status != "draft":
            abort(400, "This ballot has already been launched.")
        if b.meeting.status != "live":
            abort(400, "Votes can only be launched while the meeting is live.")
        minutes = int(body().get("duration_minutes") or 0)
        if minutes < 0 or minutes > 240:
            abort(400, "Voting window must be 0–240 minutes (0 = until closed manually).")
        b.status = "open"
        b.opened_at = utcnow()
        b.closes_at = utcnow() + timedelta(minutes=minutes) if minutes else None
        db.session.commit()
        voters = [p.user for p in b.meeting.participants if p.is_voting]
        notify(voters, f"Vote open: {b.motion}", "A live vote has opened. Cast your vote now.",
               f"/meetings/{b.meeting_id}?tab=voting", "vote", email=False)
        audit("ballot.launch", "vote", "ballot", b.id, b.meeting_id, window_minutes=minutes)
        return b.to_dict(viewer=current_user())


@ns.route("/ballots/<int:ballot_id>/vote")
class Cast(Resource):
    @auth_required("vote.cast")
    def post(self, ballot_id):
        """Cast an identified or anonymous vote (for yourself or as an appointed proxy)."""
        b = load_ballot(ballot_id)
        user = current_user()
        _check_open(b)
        data = body()
        choice = data.get("choice")
        if choice not in b.options:
            abort(400, f"Choice must be one of: {', '.join(b.options)}.")
        principal_id = int(data.get("on_behalf_of") or user.id)
        meeting = b.meeting
        principal_part = _voting_participant(meeting, principal_id)
        if not principal_part:
            abort(403, "This member is not a voting participant of the meeting.")
        if principal_id == user.id:
            if principal_part.attendance_status != "present":
                abort(403, "You must be present in the meeting to vote.")
        else:
            px = Proxy.query.filter_by(meeting_id=meeting.id, principal_id=principal_id, proxy_id=user.id,
                                       revoked=False).first()
            if not px:
                abort(403, "You are not the appointed proxy for this member.")
            me = _voting_participant(meeting, user.id)
            if not me or me.attendance_status != "present":
                abort(403, "A proxy holder must be present in the meeting to vote.")
        if Vote.query.filter_by(ballot_id=b.id, principal_id=principal_id).first():
            abort(409, "A vote has already been cast for this member.")
        weight = principal_part.user.vote_weight if b.weighted else 1
        receipt = hashlib.sha256(f"{b.id}:{principal_id}:{secrets.token_hex(8)}".encode()).hexdigest()
        db.session.add(Vote(ballot_id=b.id, voter_id=user.id, principal_id=principal_id, choice=choice,
                            weight=weight, receipt=receipt))
        db.session.commit()
        audit("vote.cast", "vote", "ballot", b.id, meeting.id, proxy=principal_id != user.id,
              **({} if b.anonymous else {"choice": choice}))
        return {"message": "Vote recorded", "receipt": receipt[:16], "ballot": b.to_dict(viewer=user)}, 201


@ns.route("/ballots/<int:ballot_id>/close")
class Close(Resource):
    @auth_required("vote.manage")
    def post(self, ballot_id):
        """Close voting: ends the voting period and blocks post-deadline ballots."""
        b = load_ballot(ballot_id)
        if b.status != "open":
            abort(400, "Only an open ballot can be closed.")
        close_ballot(b)
        db.session.commit()
        notify([p.user for p in b.meeting.participants], f"Vote closed: {b.motion}",
               f"Result: {b.result['outcome_label']}.", f"/meetings/{b.meeting_id}?tab=voting", "vote", email=False)
        audit("ballot.close", "vote", "ballot", b.id, b.meeting_id, outcome=b.result["outcome"])
        return b.to_dict(viewer=current_user())


@ns.route("/ballots/<int:ballot_id>/results")
class Results(Resource):
    @auth_required("meeting.view")
    def get(self, ballot_id):
        """Calculate quorum & percentages (live tallies for vote managers while open)."""
        b = load_ballot(ballot_id)
        user = current_user()
        if b.status == "open" and not user.can("vote.manage"):
            abort(403, "Results are visible after the vote closes.")
        result = b.result if b.status == "closed" else compute_result(b)
        voters = None
        if not b.anonymous:
            voters = [{"member": v.principal.brief(), "cast_by": v.voter.brief(), "choice": v.choice,
                       "weight": v.weight, "cast_at": iso(v.cast_at)} for v in b.votes]
        return {"ballot": b.to_dict(viewer=user), "result": result, "votes": voters}


@ns.route("/ballots/<int:ballot_id>/resolution")
class RecordResolution(Resource):
    @auth_required("resolution.record")
    def post(self, ballot_id):
        """Record legal resolution: binds the certified outcome to the company resolution registry."""
        b = load_ballot(ballot_id)
        if b.status != "closed":
            abort(400, "Close the vote before recording the resolution.")
        if Resolution.query.filter_by(ballot_id=b.id).first():
            abort(409, "A resolution has already been recorded for this ballot.")
        data = body()
        year = utcnow().year
        count = Resolution.query.filter(Resolution.number.like(f"RES-{year}-%")).count()
        r = Resolution(number=f"RES-{year}-{count + 1:03d}", ballot_id=b.id, meeting_id=b.meeting_id,
                       title=(data.get("title") or b.motion).strip(),
                       text=(data.get("text") or b.description or "").strip(),
                       outcome=b.result["outcome"], tallies=b.result["tallies"],
                       quorum_met=b.result["quorum"]["met"], certified_by=current_user().id, certified_at=utcnow())
        r.cert_hash = hashlib.sha256(json.dumps(
            {"number": r.number, "ballot": b.id, "title": r.title, "outcome": r.outcome, "tallies": r.tallies,
             "certified_by": r.certified_by, "at": r.certified_at.isoformat()}, sort_keys=True).encode()).hexdigest()
        db.session.add(r)
        db.session.commit()
        audit("resolution.record", "vote", "resolution", r.id, b.meeting_id, number=r.number, outcome=r.outcome)
        return r.to_dict(), 201


@ns.route("/resolutions")
class Resolutions(Resource):
    @auth_required("meeting.view")
    def get(self):
        """Company resolution register."""
        user = current_user()
        q = Resolution.query.order_by(Resolution.certified_at.desc())
        if request.args.get("outcome"):
            q = q.filter_by(outcome=request.args["outcome"])
        return [r.to_dict() for r in q.all() if can_view(r.meeting, user)]


@ns.route("/ballots/<int:ballot_id>/export")
class ExportSummary(Resource):
    @auth_required("meeting.view")
    def get(self, ballot_id):
        """Export voting summary: signed tallies and ballot distribution (?format=pdf|csv)."""
        b = load_ballot(ballot_id)
        user = current_user()
        require_perm(user, "export.data")
        if b.status != "closed":
            abort(400, "Close the vote before exporting the summary.")
        res = b.result
        resolution = Resolution.query.filter_by(ballot_id=b.id).first()
        fmt = request.args.get("format", "pdf")
        audit("ballot.export", "vote", "ballot", b.id, b.meeting_id, format=fmt)
        if fmt == "csv":
            buf = io.StringIO()
            w = csv.writer(buf)
            w.writerow(["Motion", b.motion])
            w.writerow(["Rule", res["rule_label"]])
            w.writerow(["Outcome", res["outcome_label"]])
            w.writerow(["Quorum", f"{res['quorum']['present']}/{res['quorum']['eligible']} "
                                  f"({res['quorum']['percent']}%)"])
            w.writerow([])
            w.writerow(["Option", "Votes", "Weight", "Percent"])
            for t in res["tallies"]:
                w.writerow([t["option"], t["votes"], t["weight"], t["percent"]])
            if not b.anonymous:
                w.writerow([])
                w.writerow(["Member", "Cast by", "Choice", "Weight", "Cast at (UTC)"])
                for v in b.votes:
                    w.writerow([v.principal.full_name, v.voter.full_name, v.choice, v.weight, iso(v.cast_at)])
            return Response(buf.getvalue(), mimetype="text/csv",
                            headers={"Content-Disposition": f"attachment; filename=ballot-{b.id}.csv"})
        signature = hashlib.sha256(json.dumps(res, sort_keys=True, default=str).encode()).hexdigest()
        blocks = [("kv", [("Meeting", b.meeting.title), ("Motion", b.motion), ("Voting rule", res["rule_label"]),
                          ("Ballot type", ("Anonymous" if b.anonymous else "Identified")
                           + (" · weighted" if b.weighted else "")),
                          ("Opened / closed", f"{iso(b.opened_at)} / {iso(b.closed_at)}"),
                          ("Quorum", f"{res['quorum']['present']}/{res['quorum']['eligible']} voting members "
                                     f"({res['quorum']['percent']}%) – required {res['quorum']['required_percent']}%"),
                          ("OUTCOME", res["outcome_label"]),
                          ("Resolution", resolution.number if resolution else "Not yet recorded")]),
                  ("h", "Tally"),
                  ("table", [["Option", "Votes", "Weight", "%"]] +
                   [[t["option"], t["votes"], t["weight"], f"{t['percent']}%"] for t in res["tallies"]])]
        if not b.anonymous:
            blocks += [("h", "Ballot distribution"),
                       ("table", [["Member", "Cast by", "Choice", "Weight"]] +
                        [[v.principal.full_name, v.voter.full_name, v.choice, v.weight] for v in b.votes])]
        blocks += [("p", f"Signed tally SHA-256: {signature}"), ("sig", ["Company Secretary", "Board Chair"])]
        pdf = make_pdf("Voting Summary", b.motion, blocks, watermark=f"{user.full_name} · {user.email}")
        return Response(pdf, mimetype="application/pdf",
                        headers={"Content-Disposition": f"attachment; filename=ballot-{b.id}.pdf"})


__all__ = ["ns", "Meeting"]
