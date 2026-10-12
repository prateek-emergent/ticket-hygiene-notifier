"""Rules 4-6 (status vs shift, tickets held off shift, L3 escalation check) and the config.py switchboard."""

import asyncio
from types import SimpleNamespace
from datetime import datetime, timedelta, timezone

import pytest

from notifier.config import load_rules_config
from notifier.detectors import Rule, evaluate_escalation, find_triggers
from notifier.kb import EscalationVerdict, load_kb
from notifier.models import Ticket
from notifier.shift_checks import ShiftChecks, waiting_since
from notifier.shifts import ShiftCalendar

from .factory import Timeline, is_human
from .test_service import KRISHNA, RENUKA, CapturingNotifier, make_monitor

UTC = timezone.utc


def write_shifts(tmp_path, rows):
    p = tmp_path / "shifts.csv"
    p.write_text("email,day,start,end\n" + "\n".join(rows) + "\n", encoding="utf-8")
    return p


# --- shift calendar ------------------------------------------------------------------------


def test_calendar_weekly_dated_overnight_and_timezone(tmp_path):
    p = write_shifts(tmp_path, [
        f"{KRISHNA},Wed,09:00,18:00",
        f"{RENUKA},Wed,21:00,06:00",          # overnight
        f"{KRISHNA},2026-10-08,13:00,22:00",  # Thursday, dated
        f"{KRISHNA},Sun,off,",
    ])
    around = datetime(2026, 10, 7, 6, 0, tzinfo=UTC)  # Wed 11:30 IST
    cal = ShiftCalendar.load(p, "Asia/Kolkata", around)
    wed_9am_ist = datetime(2026, 10, 7, 3, 30, tzinfo=UTC)
    assert cal.on_shift(KRISHNA, wed_9am_ist)
    assert not cal.on_shift(KRISHNA, wed_9am_ist - timedelta(minutes=1))
    renuka_night = cal.shift_at(RENUKA, datetime(2026, 10, 7, 23, 0, tzinfo=UTC))  # Thu 04:30 IST
    assert renuka_night and renuka_night.end == datetime(2026, 10, 8, 0, 30, tzinfo=UTC)
    thu = cal.shift_at(KRISHNA, datetime(2026, 10, 8, 8, 0, tzinfo=UTC))  # Thu 13:30 IST
    assert thu and thu.start == datetime(2026, 10, 8, 7, 30, tzinfo=UTC)
    assert not cal.on_shift(KRISHNA, datetime(2026, 10, 11, 6, 0, tzinfo=UTC))  # Sunday off
    assert cal.last_end_before(KRISHNA, datetime(2026, 10, 7, 13, 0, tzinfo=UTC)) == datetime(2026, 10, 7, 12, 30, tzinfo=UTC)


# --- fakes ---------------------------------------------------------------------------------


class DMNotifier(CapturingNotifier):
    def __init__(self):
        super().__init__()
        self.dms = []

    async def dm(self, email, text, blocks):
        self.dms.append((email, text))


class ShiftTrinity:
    def __init__(self, presence=None, open_tickets=None, timelines=None):
        self.presence = presence or {}
        self.open = open_tickets or {}
        self.timelines = timelines or {}
        self.presence_calls = 0

    async def agent(self, email):
        self.presence_calls += 1
        return {"name": email.split("@")[0].title() + " Test", "presence": self.presence.get(email)}

    async def open_tickets(self, email):
        return self.open.get(email, [])

    async def all_events(self, tid):
        return self.timelines[tid].events()


def shift_monitor(tmp_path, shift_rows, rules):
    monitor, _ = make_monitor(tmp_path, None)
    notifier = DMNotifier()
    monitor.notifier = notifier
    monitor.cfg.shifts_file = write_shifts(tmp_path, shift_rows)
    monitor.cfg.shifts_tz = "Asia/Kolkata"
    monitor.cfg.enabled_rules = set(rules)
    checks = ShiftChecks(monitor)
    return monitor, notifier, checks


# --- rule 4 --------------------------------------------------------------------------------

SHIFT_START = datetime(2026, 10, 7, 3, 30, tzinfo=UTC)  # Wed 09:00 IST
SHIFT_END = datetime(2026, 10, 7, 12, 30, tzinfo=UTC)  # Wed 18:00 IST


def test_still_offline_45_min_after_shift_start_alerts_channel_and_dm(tmp_path):
    monitor, notifier, checks = shift_monitor(tmp_path, [f"{KRISHNA},Wed,09:00,18:00"], {Rule.STATUS_SHIFT})
    trinity = ShiftTrinity(presence={KRISHNA: "OFFLINE"})
    run = lambda now: asyncio.run(checks.run(trinity, now))  # noqa: E731
    run(SHIFT_START)  # service starts: watermark
    run(SHIFT_START + timedelta(minutes=44))
    assert notifier.posts == [] and notifier.dms == []
    run(SHIFT_START + timedelta(minutes=46))
    [(text, blocks)] = notifier.posts
    body = "\n".join(b["text"]["text"] for b in blocks if b["type"] == "section")
    assert "still *Offline*" in body and "<@U_LEAD>" in body
    [(dm_to, dm_text)] = notifier.dms
    assert dm_to == KRISHNA and "set yourself Online" in dm_text
    run(SHIFT_START + timedelta(minutes=50))  # no repeat for the same shift start
    assert len(notifier.posts) == 1


def test_online_at_shift_start_and_offline_after_end_is_quiet(tmp_path):
    monitor, notifier, checks = shift_monitor(tmp_path, [f"{KRISHNA},Wed,09:00,18:00"], {Rule.STATUS_SHIFT})
    trinity = ShiftTrinity(presence={KRISHNA: "ONLINE"})
    asyncio.run(checks.run(trinity, SHIFT_START))
    asyncio.run(checks.run(trinity, SHIFT_START + timedelta(minutes=46)))
    trinity.presence[KRISHNA] = "OFFLINE"
    asyncio.run(checks.run(trinity, SHIFT_END + timedelta(minutes=46)))
    assert notifier.posts == [] and notifier.dms == []


def test_still_online_45_min_after_shift_end_alerts(tmp_path):
    monitor, notifier, checks = shift_monitor(tmp_path, [f"{KRISHNA},Wed,09:00,18:00"], {Rule.STATUS_SHIFT})
    trinity = ShiftTrinity(presence={KRISHNA: "ONLINE"})
    asyncio.run(checks.run(trinity, SHIFT_END))
    asyncio.run(checks.run(trinity, SHIFT_END + timedelta(minutes=46)))
    [(_, dm_text)] = notifier.dms
    assert "set yourself Offline" in dm_text


def test_unlisted_engineer_status_is_not_checked(tmp_path):
    monitor, notifier, checks = shift_monitor(tmp_path, ["someone.else@emergent.sh,Wed,09:00,18:00"], {Rule.STATUS_SHIFT})
    trinity = ShiftTrinity(presence={"someone.else@emergent.sh": "OFFLINE"})
    asyncio.run(checks.run(trinity, SHIFT_START))
    asyncio.run(checks.run(trinity, SHIFT_START + timedelta(minutes=46)))
    assert notifier.posts == [] and trinity.presence_calls == 0


# --- rule 5 --------------------------------------------------------------------------------


def _ticket(tid="tk"):
    return Ticket.from_api({"id": tid, "num": 7, "subject": "Help", "status": "OPEN", "assigned_to": KRISHNA})


def _timeline_with_customer_waiting_since(t: datetime, tid="tk"):
    tl = Timeline(tid).customer(0).reply(5, KRISHNA, "<p>Looking into it.</p>").customer(10, "Any update?")
    base = datetime.fromisoformat(tl.raw[-1]["created_at"])
    for r in tl.raw:
        r["created_at"] = (datetime.fromisoformat(r["created_at"]) - base + t).isoformat()
    return tl


def test_customer_waiting_3h_after_shift_end_is_flagged_once(tmp_path):
    monitor, notifier, checks = shift_monitor(tmp_path, [f"{KRISHNA},Wed,09:00,18:00"], {Rule.OFF_SHIFT_HOLD})
    tl = _timeline_with_customer_waiting_since(SHIFT_END - timedelta(hours=1))  # waiting since 17:00 IST
    trinity = ShiftTrinity(open_tickets={KRISHNA: [_ticket()]}, timelines={"tk": tl})
    asyncio.run(checks.run(trinity, SHIFT_END + timedelta(hours=2, minutes=50)))  # counted from shift end: 2h50
    assert notifier.posts == []
    asyncio.run(checks.run(trinity, SHIFT_END + timedelta(hours=3, minutes=10)))
    [(_, blocks)] = notifier.posts
    body = "\n".join(b["text"]["text"] for b in blocks if b["type"] == "section")
    assert "off shift" in body and "Customer waiting since" in body and "<@U_LEAD>" in body
    asyncio.run(checks.run(trinity, SHIFT_END + timedelta(hours=5)))  # same off-shift period: no repeat
    assert len(notifier.posts) == 1


def test_on_shift_engineer_or_answered_ticket_is_not_flagged(tmp_path):
    monitor, notifier, checks = shift_monitor(tmp_path, [f"{KRISHNA},Wed,09:00,18:00"], {Rule.OFF_SHIFT_HOLD})
    tl = _timeline_with_customer_waiting_since(SHIFT_START)
    trinity = ShiftTrinity(open_tickets={KRISHNA: [_ticket()]}, timelines={"tk": tl})
    asyncio.run(checks.run(trinity, SHIFT_START + timedelta(hours=5)))  # on shift
    assert notifier.posts == []
    answered = Timeline("tk").customer(0).reply(5, KRISHNA, "<p>Done.</p>")
    assert waiting_since(answered.events()) is None


# --- rule 6 --------------------------------------------------------------------------------


def _escalation_timeline():
    return (
        Timeline("tk").customer(0, "My production database is empty after deploy")
        .assign(1, KRISHNA, None, KRISHNA)
        ._add(30, type="note", visibility="internal", body="<p>Need DB restore from backup, no access</p>",
              author="Krishna", author_email=KRISHNA)
        ._add(31, action="tag_added", new_value="l3_needs_review", author="Krishna", author_email=KRISHNA)
        ._add(31.1, action="level_changed", old_value="L2", new_value="L3", author="Krishna", author_email=KRISHNA)
    )


def test_escalation_trigger_and_context():
    events = _escalation_timeline().events()
    [t] = [x.event for x in find_triggers(events, is_human) if x.rule == Rule.L3_ESCALATION]
    f = evaluate_escalation(events, t, timedelta(minutes=10))
    assert f.needs_kb_check and f.engineer_email == KRISHNA
    assert "Need DB restore" in f.details["context"] and "CUSTOMER" in f.details["context"]
    assert f.details["tags"] == ["l3_needs_review"]


class FakeJudge:
    def __init__(self, verdict):
        self.verdict = verdict

    async def judge(self, subject, context, tags):
        return self.verdict


def _run_escalation(tmp_path, judge, timeline=None, rules=(Rule.L3_ESCALATION,), rca_judge=None):
    from .test_service import FakeTrinity

    monitor, notifier = make_monitor(tmp_path, None)
    monitor.cfg.enabled_rules = set(rules)
    monitor.escalation_judge = judge
    monitor.rca_judge = rca_judge
    trinity = FakeTrinity({"tk": timeline or _escalation_timeline()})
    asyncio.run(monitor.discover(trinity))
    asyncio.run(monitor.run_due(trinity))
    return notifier.posts


# --- rule 7: escalation note (RCA) quality ----------------------------------------------------


def _escalation(note: str | None, note_at: float = 30):
    tl = Timeline("tk").customer(0, "Preview not loading").assign(1, KRISHNA, None, KRISHNA)
    if note is not None:
        tl = tl._add(note_at, type="note", visibility="internal", body=f"<p>{note}</p>", author="Krishna", author_email=KRISHNA)
    return (tl._add(31, action="tag_added", new_value="l3_needs_review", author="Krishna", author_email=KRISHNA)
              ._add(31.1, action="level_changed", old_value="L2", new_value="L3", author="Krishna", author_email=KRISHNA))


class FakeRcaJudge:
    model = "jev-latest"

    def __init__(self, verdict):
        self.verdict = verdict
        self.calls = 0

    async def judge(self, note):
        self.calls += 1
        return self.verdict


def _bodies(posts):
    return ["\n".join(b["text"]["text"] for b in blocks if b["type"] == "section") for _, blocks in posts]


def test_one_escalation_is_one_trigger_per_rule():
    events = _escalation("x" * 200).events()
    rules = [t.rule for t in find_triggers(events, is_human)]
    assert rules.count(Rule.ESCALATION_NOTE) == 1 and rules.count(Rule.L3_ESCALATION) == 1


def test_missing_note_is_flagged_without_a_judge(tmp_path):
    judge = FakeRcaJudge(None)
    [body] = _bodies(_run_escalation(tmp_path, None, _escalation(None), (Rule.ESCALATION_NOTE,), judge))
    assert "no internal note" in body and "Missing" in body and judge.calls == 0


def test_note_written_long_before_the_escalation_does_not_count(tmp_path):
    [body] = _bodies(_run_escalation(tmp_path, None, _escalation("Job id abc, root cause: x" * 5, note_at=-400),
                                     (Rule.ESCALATION_NOTE,), FakeRcaJudge(None)))
    assert "no internal note" in body


def test_too_short_note_is_vague_without_a_judge(tmp_path):
    judge = FakeRcaJudge(None)
    [body] = _bodies(_run_escalation(tmp_path, None, _escalation("escalated to L3"), (Rule.ESCALATION_NOTE,), judge))
    assert "too short" in body and judge.calls == 0


def test_judged_note_flags_vague_and_unsupported_only(tmp_path):
    from notifier.rca import QUESTIONS, RcaVerdict, score

    note = "Customer says preview is not loading since morning, please check and assign back to me. " * 2
    yes = {q: True for q in QUESTIONS}
    vague = RcaVerdict(score({**yes, "cause": False, "ask": False}), {**yes, "cause": False, "ask": False}, judged_by="jev-latest")
    [body] = _bodies(_run_escalation(tmp_path, None, _escalation(note), (Rule.ESCALATION_NOTE,), FakeRcaJudge(vague)))
    assert "vague" in body and "no root cause" in body and "only 'please check'" in body
    (tmp_path / "b").mkdir()
    partial = RcaVerdict(score({**yes, "identifier": False}), {**yes, "identifier": False}, judged_by="jev-latest")
    assert _run_escalation(tmp_path / "b", None, _escalation(note), (Rule.ESCALATION_NOTE,), FakeRcaJudge(partial)) == []


def test_rca_scoring_rule():
    from notifier.rca import QUESTIONS, score

    yes = {q: True for q in QUESTIONS}
    assert score(yes) == "COMPLETE"
    assert score({**yes, "own_handoff": False}) == "VAGUE"
    assert score({**yes, "cause": False, "ask": False}) == "VAGUE"
    assert score({**yes, "evidence": False}) == "UNSUPPORTED"
    assert score({**yes, "cause": False}) == "PARTIAL"
    assert score({**yes, "identifier": False}) == "PARTIAL"


def test_jev_rca_judge_falls_back_when_unsure():
    from notifier.rca import JevRcaJudge, QUESTIONS, RcaVerdict

    class Claude:
        model = "claude-opus-5-5"

        async def judge(self, note):
            return RcaVerdict("COMPLETE", {q: True for q in QUESTIONS})

    j = JevRcaJudge("http://jev", "jev-latest", "k", Claude())

    async def sure(note):
        return {q: 0.9 for q in QUESTIONS} | {"evidence": 0.1}

    async def unsure(note):
        return {q: 0.9 for q in QUESTIONS} | {"cause": 0.5}

    j._ask = sure
    v = asyncio.run(j.judge("n" * 200))
    assert v.verdict == "UNSUPPORTED" and v.judged_by == "jev-latest"
    j._ask = unsure
    v = asyncio.run(j.judge("n" * 200))
    assert v.verdict == "COMPLETE" and "fallback" in v.judged_by
    j.fallback = None
    assert asyncio.run(j.judge("n" * 200)).verdict == "UNKNOWN"


def test_escalation_kb_says_l2_could_handle_is_flagged(tmp_path):
    v = EscalationVerdict(False, "database-restore.md: L2 can resolve when", "Preview DB, not production.",
                          "Switch the viewer to production first.", "high")
    [(_, blocks)] = _run_escalation(tmp_path, FakeJudge(v))
    body = "\n".join(b["text"]["text"] for b in blocks if b["type"] == "section")
    assert "database-restore.md" in body and "Switch the viewer" in body and "<@U_LEAD>" in body


@pytest.mark.parametrize("verdict", [
    EscalationVerdict(True, "x.md", "Needs prod restore.", "", "high"),       # genuine
    EscalationVerdict(False, "x.md", "Probably L2.", "", "low"),              # not confident enough
    EscalationVerdict(True, "", "Check failed (boom).", "", "low", error="boom"),  # judge error
])
def test_escalation_not_flagged_when_genuine_unsure_or_failed(tmp_path, verdict):
    assert _run_escalation(tmp_path, FakeJudge(verdict)) == []


KB_FILES = {
    "database-restore.md": "# Database restores\n\n## Needs L3 when\n- Restoring a production database from backup.\n\n"
                           "## L2 can resolve when\n- The customer is looking at the preview database.\n\n"
                           "## L2 must try first\n1. Switch the DB viewer to production.\n2. Check the backup list.\n",
    "custom-domains.md": "# Custom domains\n\n## L2 can resolve when\n- DNS records are wrong.\n",
}


class ScriptedJev:
    """Stands in for Jev's /v1/systemone: answers each call from a script, in order."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.states = []

    async def __call__(self, session, state, questions):
        self.states.append(state)
        a = self.answers.pop(0)
        if isinstance(a, Exception):
            raise a
        return a


class FakeClaudeJudge:
    model = "claude-opus-5-5"

    def __init__(self):
        self.calls = 0

    async def judge(self, subject, context, tags):
        self.calls += 1
        return EscalationVerdict(False, "database-restore.md", "Claude: preview DB.", "Switch the viewer.", "high")


def _jev_judge(script, fallback=None):
    from notifier.kb import JevEscalationJudge

    judge = JevEscalationJudge(KB_FILES, "http://jev", "jev-latest", "k", fallback)
    judge._ask = script
    return judge


def _file(name):
    return {"file": {"choice": name}}


def _verdict(p, why="l2_can_resolve"):
    """Jev's answers when an L3 bullet matches with probability p and the other side with 1 - p."""
    other = 1 - p
    return {"l3_match": {"noul": p}, "needs_l3": {"noul": p},
            "l2_match": {"noul": other if why == "l2_can_resolve" else 0.05},
            "nofault_match": {"noul": other if why == "not_a_fault" else 0.05}}


def test_jev_judge_not_needed_quotes_the_kb_section():
    script = ScriptedJev(_file("database-restore.md"), _verdict(0.1))
    v = asyncio.run(_jev_judge(script).judge("Need DB restore", "CUSTOMER: my data is gone", ["l3_needs_review"]))
    assert (v.needs_l3, v.confidence, v.judged_by) == (False, "high", "jev-latest")
    assert v.kb_reference == "database-restore.md: L2 can resolve when"
    assert "preview database" in v.what_l2_should_try and "90%" in v.reason and "10%" in v.reason
    assert set(v.scores) == {"l3_match", "l2_match", "nofault_match", "needs_l3"}
    # call 1: the ticket only (the files are the choice's options); call 2: the chosen file only
    assert "KNOWLEDGE" not in script.states[0] and "Database restores" in script.states[1]
    assert "custom-domains.md" not in script.states[1]


def test_kb_layout_shared_principles_and_reference_folder(tmp_path):
    from notifier.kb import JevEscalationJudge, kb_covers, load_kb_files

    kb = tmp_path / "kb"
    (kb / "reference").mkdir(parents=True)
    (kb / "README.md").write_text("# readme", encoding="utf-8")
    (kb / "reference" / "permissions.md").write_text("# full table", encoding="utf-8")
    (kb / "_principles.md").write_text("# Principles\n\n- judge the action, not the fixer", encoding="utf-8")
    (kb / "db.md").write_text("# Databases\n\n## Covers\n- data loss\n- restores\n\n## Needs L3 when\n- x", encoding="utf-8")
    files = load_kb_files(kb)
    assert set(files) == {"_principles.md", "db.md"}
    assert kb_covers(files["db.md"]) == "- data loss - restores"
    j = JevEscalationJudge(files, "http://jev", "jev-latest", "k")
    assert set(j.issue_files) == {"db.md"} and set(j.file_question["criteria"]) == {"none", "db.md"}
    assert "data loss" in j.file_question["criteria"]["db.md"]

    script = ScriptedJev(_file("db.md"), _verdict(0.9))
    j._ask = script
    asyncio.run(j.judge("s", "c", []))
    assert "judge the action, not the fixer" in script.states[1]


def test_jev_judge_needed_or_not_covered_is_not_flagged():
    v = asyncio.run(_jev_judge(ScriptedJev(_file("database-restore.md"), _verdict(0.9))).judge("s", "c", []))
    assert v.needs_l3 and v.confidence == "high"
    v = asyncio.run(_jev_judge(ScriptedJev(_file("none"))).judge("s", "c", []))
    assert v.needs_l3 and v.confidence == "low"


def test_jev_judge_falls_back_to_claude_when_unsure_failing_or_too_long():
    from notifier.kb import TooLong

    for script in (ScriptedJev(_file("database-restore.md"), _verdict(0.5)),
                   ScriptedJev(RuntimeError("HTTP 503")),
                   ScriptedJev(TooLong())):
        claude = FakeClaudeJudge()
        v = asyncio.run(_jev_judge(script, claude).judge("s", "c", []))
        assert claude.calls == 1 and v.reason == "Claude: preview DB." and "fallback" in v.judged_by
    # no fallback configured: not judged, never alerted
    v = asyncio.run(_jev_judge(ScriptedJev(RuntimeError("HTTP 503"))).judge("s", "c", []))
    assert v.error and v.needs_l3


def test_jev_judge_through_the_monitor_posts_the_kb_section(tmp_path):
    posts = _run_escalation(tmp_path, _jev_judge(ScriptedJev(_file("database-restore.md"), _verdict(0.05))))
    [(_, blocks)] = posts
    body = "\n".join(b["text"]["text"] for b in blocks if b["type"] == "section")
    assert "database-restore.md: L2 can resolve when" in body and "preview database" in body
    assert "Judged by:* jev-latest" in body


def test_rule6_on_needs_the_jev_key(tmp_path, monkeypatch):
    from pathlib import Path

    from notifier.config import Config

    src = (Path(__file__).resolve().parent.parent / "config.py").read_text(encoding="utf-8")
    cfg_file = tmp_path / "config.py"
    cfg_file.write_text(src.replace('"l3_escalation_check": False', '"l3_escalation_check": True'), encoding="utf-8")
    monkeypatch.setenv("RULES_CONFIG", str(cfg_file))
    monkeypatch.setenv("TRINITY_MCP_URL", "http://trinity")
    monkeypatch.setenv("PENDING_MODEL_OPTION", "A")
    monkeypatch.delenv("JEV_API_KEY", raising=False)
    with pytest.raises(SystemExit, match="JEV_API_KEY"):
        Config.from_env(env_file=None)
    monkeypatch.setenv("JEV_API_KEY", "k")
    cfg = Config.from_env(env_file=None)
    assert (cfg.l3_model, cfg.l3_fallback_model, cfg.l3_api_key) == ("jev-latest", "claude-opus-5-5", "k")


def test_escalation_without_kb_is_not_judged(tmp_path):
    assert _run_escalation(tmp_path, None) == []
    (tmp_path / "kb").mkdir()
    (tmp_path / "kb" / "README.md").write_text("# readme", encoding="utf-8")
    assert load_kb(tmp_path / "kb") is None
    (tmp_path / "kb" / "db.md").write_text("# DB restores", encoding="utf-8")
    assert "FILE: db.md" in load_kb(tmp_path / "kb")


# --- config.py switchboard -----------------------------------------------------------------


def test_switchboard_loads_and_rejects_unknown_rule(tmp_path):
    from pathlib import Path

    real = load_rules_config(Path(__file__).resolve().parent.parent / "config.py")
    assert set(real.THEMES) == {r.value for r in Rule}
    bad = tmp_path / "config.py"
    bad.write_text("RULES = {'pending_without_open_qestion': True}\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        load_rules_config(bad)


def test_pending_model_options(monkeypatch):
    from pathlib import Path

    from notifier.config import pending_model

    rc = load_rules_config(Path(__file__).resolve().parent.parent / "config.py")
    monkeypatch.delenv("PENDING_MODEL_OPTION", raising=False)
    monkeypatch.delenv("JEV_API_KEY", raising=False)
    option, a, key = pending_model(rc, "A")
    assert (a["english_model"], a["other_languages_model"], a["score_sentences"], key) == ("von", "decider:4b", True, None)
    assert "127.0.0.1" in a["url"]
    # B without its key: refuse to start rather than skip every PENDING check
    with pytest.raises(SystemExit, match="JEV_API_KEY"):
        pending_model(rc, "B")
    monkeypatch.setenv("JEV_API_KEY", "k")
    option, b, key = pending_model(rc, "b")
    assert (option, b["english_model"], b["other_languages_model"], b["score_sentences"], key) == (
        "B", "jev-latest", "jev-latest", False, "k")
    monkeypatch.setenv("PENDING_MODEL_OPTION", "B")  # one-run override of config.py
    assert pending_model(rc)[0] == "B"
    with pytest.raises(SystemExit, match="one of"):
        pending_model(rc, "C")


# --- the team roster grid (real file layout, made-up people) ---------------------------------

ROSTER = """6A-3P SHIFT (L2),,,,,,
Agent,Email,Role,Fixed Weekly Off,9-Oct : Fri,10-Oct : Sat,11-Oct : Sun
Engineer One,one@emergent.sh,Agent,Monday,Off,comp off(2oct),6A-3P
Engineer Two,two@emergent.sh,Agent,Tuesday,9P-6A,EL,swap(12th)
On duty (count),,,,1,0,1
,,,,9-Oct : Fri,10-Oct : Sat,11-Oct : Sun
,,,6A-3P,1,0,1
Doom-Loop Calls,,,,,,
Agent,Email,Role,Fixed Weekly Off,9-Oct : Fri,10-Oct : Sat,11-Oct : Sun
Engineer Three,three@emergent.sh,Agent,Sunday,11A-8P,1P-10P,Off
"""


def test_roster_grid_is_read_cell_by_cell(tmp_path):
    from zoneinfo import ZoneInfo

    from notifier.shifts import parse_shift_code

    p = tmp_path / "roster.csv"
    p.write_text(ROSTER, encoding="utf-8")
    ist = ZoneInfo("Asia/Kolkata")
    cal = ShiftCalendar.load(p, "Asia/Kolkata", datetime(2026, 10, 7, 6, 0, tzinfo=UTC))
    assert cal.people == {"one@emergent.sh", "two@emergent.sh", "three@emergent.sh"}
    # one: off, comp off, then 6A-3P on Sun 11 Oct (2026 inferred from the weekday)
    assert not cal.on_shift("one@emergent.sh", datetime(2026, 10, 9, 8, 0, tzinfo=ist))
    assert not cal.on_shift("one@emergent.sh", datetime(2026, 10, 10, 8, 0, tzinfo=ist))
    assert cal.on_shift("one@emergent.sh", datetime(2026, 10, 11, 8, 0, tzinfo=ist))
    # two: 9P-6A crosses midnight; leave (EL) next day; swap cell = unknown day, not "off"
    assert cal.on_shift("two@emergent.sh", datetime(2026, 10, 10, 2, 0, tzinfo=ist))
    assert not cal.is_certain("two@emergent.sh", datetime(2026, 10, 11, 12, 0, tzinfo=ist))
    assert cal.is_certain("two@emergent.sh", datetime(2026, 10, 10, 12, 0, tzinfo=ist))
    # three: in the Doom-Loop block; 1P-10P parsed
    assert cal.info["three@emergent.sh"]["block"] == "Doom-Loop Calls"
    assert cal.on_shift("three@emergent.sh", datetime(2026, 10, 10, 21, 30, tzinfo=ist))
    assert parse_shift_code("12P-9P")[0].hour == 12 and parse_shift_code("12A-9A")[0].hour == 0
    assert parse_shift_code("Comp Off") is None and parse_shift_code("swap(17th)") == "unknown"


def test_off_shift_sweep_skips_unknown_roster_days(tmp_path):
    monitor, notifier, checks = shift_monitor(tmp_path, [f"{KRISHNA},Wed,09:00,18:00"], {Rule.OFF_SHIFT_HOLD})
    from zoneinfo import ZoneInfo

    cal = checks.calendar(SHIFT_END)
    cal.unknown_days.add((KRISHNA, SHIFT_END.astimezone(ZoneInfo("Asia/Kolkata")).date()))
    tl = _timeline_with_customer_waiting_since(SHIFT_END - timedelta(hours=1))
    trinity = ShiftTrinity(open_tickets={KRISHNA: [_ticket()]}, timelines={"tk": tl})
    asyncio.run(checks.check_off_shift_tickets(trinity, cal, SHIFT_END + timedelta(hours=4)))
    assert notifier.posts == []


def test_jev_judge_alerts_only_on_a_clear_l2_match_with_no_l3_match():
    both = {"l3_match": {"noul": 0.8}, "l2_match": {"noul": 0.9}, "nofault_match": {"noul": 0.1}, "needs_l3": {"noul": 0.2}}
    v = asyncio.run(_jev_judge(ScriptedJev(_file("database-restore.md"), both)).judge("s", "c", []))
    assert v.needs_l3  # an L3 bullet matches too: no alert
    nofault = _verdict(0.05, "not_a_fault")
    v = asyncio.run(_jev_judge(ScriptedJev(_file("database-restore.md"), nofault)).judge("s", "c", []))
    assert not v.needs_l3 and "not a platform fault" in v.reason


# --- Claude fallback: off without a key, switched off when the key is rejected, never alerts on failure ---

def _auth_error():
    import anthropic
    import httpx2 as httpx
    resp = httpx.Response(401, request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"))
    return anthropic.AuthenticationError("invalid x-api-key", response=resp, body=None)


def test_claude_fallback_is_off_without_a_key_and_never_errors(monkeypatch, caplog):
    from notifier.__main__ import claude_fallback
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert claude_fallback("claude-opus-5-5", "theme 6") is None
    assert "ANTHROPIC_API_KEY is not set" in caplog.text
    monkeypatch.setenv("ANTHROPIC_API_KEY", "   ")  # blank counts as not set
    assert claude_fallback("claude-opus-5-5", "theme 6") is None
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    assert claude_fallback("claude-opus-5-5", "theme 6") == "claude-opus-5-5"
    assert claude_fallback(None, "theme 6") is None  # None in config.py = never use Claude


def test_claude_backend_without_a_key_stops_with_a_clear_message(monkeypatch):
    from notifier.__main__ import build_classifier
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    cfg = SimpleNamespace(classifier_backend="claude", classifier_model="m", classifier_effort="low",
                          classifier_fallbacks=True)
    with pytest.raises(SystemExit, match="ANTHROPIC_API_KEY"):
        build_classifier(cfg)


def test_rejected_claude_key_switches_the_fallback_off_for_the_run(monkeypatch):
    from notifier.kb import EscalationJudge
    from notifier.rca import ClaudeRcaJudge, JevRcaJudge, QUESTIONS
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-wrong")
    calls = []

    async def create(**kw):
        calls.append(kw)
        raise _auth_error()

    for judge in (EscalationJudge("kb", "claude-opus-5-5", use_fallbacks=False),
                  ClaudeRcaJudge("claude-opus-5-5", use_fallbacks=False)):
        judge.client = SimpleNamespace(messages=SimpleNamespace(create=create))
        v = asyncio.run(judge.judge("subj", "ctx", []) if isinstance(judge, EscalationJudge) else judge.judge("n"))
        assert v.error and "rejected" in judge.disabled  # failed check: never alerted

    # Once switched off, Jev's unsure cases are "not judged" without calling Claude again.
    n = len(calls)
    rca = JevRcaJudge("http://jev", "jev-latest", "k", judge)

    async def unsure(note):
        return {q: 0.9 for q in QUESTIONS} | {"cause": 0.5}

    rca._ask = unsure
    assert asyncio.run(rca.judge("n" * 200)).verdict == "UNKNOWN" and len(calls) == n


def test_jev_escalation_judge_survives_a_crashing_fallback():
    from notifier.kb import JevEscalationJudge

    class Boom:
        model = "claude-opus-5-5"
        disabled = None

        async def judge(self, *a):
            raise RuntimeError("no network")

        @staticmethod
        def _failed(msg):
            return EscalationVerdict(True, "", f"Check failed ({msg}).", "", "low", error=msg)

    j = JevEscalationJudge({"a.md": "# A"}, "http://jev", "jev-latest", "k", Boom())
    v = asyncio.run(j._fall_back("Jev unsure", "s", "c", []))
    assert v.needs_l3 and v.error and "fallback" in v.judged_by  # no alert


def test_failed_theme1_fallback_is_skipped_not_alerted():
    from notifier.classifier import Verdict
    from notifier.systemone import SystemOneClassifier

    class Failing:
        model = "claude-opus-5-5"
        disabled = None

        async def classify(self, *a):
            return Verdict(False, "", "Automatic check failed (API error 500).", "low", error="500")

    clf = SystemOneClassifier("http://jev", "jev-latest", api_key="k", fallback=Failing())
    v = asyncio.run(clf._ask_fallback("reply", None, "subj"))
    assert v.error and v.uncertain  # uncertain => skipped unless ALERT_UNCERTAIN
    clf.fallback.disabled = "key rejected"
    assert asyncio.run(clf._ask_fallback("reply", None, "subj")) is None
