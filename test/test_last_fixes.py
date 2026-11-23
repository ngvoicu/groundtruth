"""The last night fixes, each proven by one of the second review's cases: a run stops
on five failed requests in a row (`failing`); Devin's rate-limit text is matched within one line and never beside a
plan-limit word; the control's gate and send are one pair of clock readings; the builder counts a run's samples only
beside a valid warm control. Nothing is sent and no client is run: fakes, the real Devin adapter over local fixtures,
and fake clocks.

    python3 -m unittest discover -s test -p "test_*.py"
"""
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "harness"))
sys.path.insert(0, HERE)
import clients as C  # noqa: E402
import night  # noqa: E402
import probe  # noqa: E402
from test_night_fixes import DEVIN_RATE  # noqa: E402

spec = importlib.util.spec_from_file_location("bo_last", os.path.join(ROOT, "scripts", "build_observed.py"))
B = importlib.util.module_from_spec(spec)
spec.loader.exec_module(B)

FIXTURES = os.path.join(HERE, "fixtures", "clients")
CREDITS = "Error: Credits exhausted for this billing period."
MIXED = ("Reached request rate limit.\nMonthly quota exhausted. These credits reset in 2 seconds (at 11:15 UTC).")


def export(key):
    with open(os.path.join(FIXTURES, "devin", key + ".json")) as f:
        return json.loads(json.load(f)["files"]["export"])


class AdapterClock:
    def __init__(self):
        self.t = 40500 - 43

    def now(self):
        return self.t
    mono = now

    def sleep(self, dt):
        self.t += max(0.0, dt)


class MinJitter:
    def uniform(self, a, b):
        return a


def devin_run(test, message, refuse_from=3):
    """The reviewer's adapter replay (adapter_replay.py, `persistent`): the real Devin adapter over local ATIF exports;
    the baseline and the control answer (the control warm), then every new session from the `refuse_from`-th on is
    refused with `message` (exit 1). The standard ladder, 3 replicas: 42 samples. Returns (reason, rows, refused)."""
    tmp = tempfile.mkdtemp(prefix="gt-last-")
    test.addCleanup(shutil.rmtree, tmp, True)
    sessions, new, refused = {}, [], []
    clock = AdapterClock()

    def transport(argv, **kwargs):
        clock.sleep(1)
        with open(argv[argv.index("--prompt-file") + 1]) as f:
            prompt = f.read()
        path = argv[argv.index("--export") + 1]
        code, err = 0, ""
        if "-r" in argv:
            current = sessions[argv[argv.index("-r") + 1]]
            steps = export("warm")["steps"][2:]
            steps[0]["message"] = prompt
            current["steps"].extend(steps)
        else:
            sid = "s" + str(len(new) + 1)
            current = export("prime")
            current["session_id"] = sid
            current["steps"][0]["message"] = prompt
            new.append(hashlib.sha256(prompt.encode()).hexdigest())
            sessions[sid] = current
            if "<doc>" not in prompt:
                current["steps"][1]["metrics"]["prompt_tokens"] = 18717
            if len(new) >= refuse_from:
                refused.append(sid)
                code, err = 1, message
        with open(path, "w") as f:
            f.write(json.dumps(current))
        return code, "", err

    client = C.Session(C.Devin("claude-haiku-5-5-low"), {}, os.path.join(tmp, "io"), os.path.join(tmp, "work"),
                       run=transport)
    start = {"event": "start", "harness": "devin", "model": "claude-haiku-5-5-low", "isolation": probe.ISOLATION,
             "ages": ",".join(probe.ages_of("std", None)[1])}
    public = probe.Public(os.path.join(tmp, "run.jsonl"), start, now=lambda: "2026-11-24T00:00:00Z")
    public.line(start)
    ages, labels = probe.ages_of("std", None)
    reason = probe.run_probe(probe.Harness(client), ages=ages, labels=labels, replicas=3, words=100, salt="review",
                             clock=clock, log=public.line, rng=MinJitter())
    with open(os.path.join(tmp, "run.jsonl")) as f:
        rows = [json.loads(s) for s in f]
    return reason, rows, refused


# --- 1. five failed requests in a row end the run (`failing`) ------------------------------------------------------

class Failing(unittest.TestCase):
    def test_credits_exhausted_replay_stops_within_5_requests(self):
        # The reviewer's case: after a warm control, 126 refused attempts, 42 samples lost, the run `done`.
        reason, rows, refused = devin_run(self, CREDITS)
        self.assertIn(reason, ("quota", "failing"))
        self.assertLessEqual(len(refused), 5)
        self.assertEqual(rows[-1], dict(rows[-1], event="stop", reason=reason))
        self.assertEqual([r["warm"] for r in rows if r["event"] == "check" and r["age"] == "control"], [True])

    def test_an_unknown_refusal_text_stops_as_failing_after_exactly_5(self):
        reason, rows, refused = devin_run(self, "Error: Agent error: something no rule knows.")
        self.assertEqual(reason, "failing")
        self.assertEqual(len(refused), 5)
        self.assertEqual(rows[-1]["reason"], "failing")

    def test_rate_limited_refusals_keep_their_own_stop_at_3(self):
        reason, rows, refused = devin_run(self, DEVIN_RATE)
        self.assertEqual((reason, len(refused)), ("quota", 3))

    def test_an_answered_request_ends_the_row(self):
        from test_night_fixes import FailingCheckClient
        from test_probe import FakeClock, go
        clock = FakeClock()
        # Four failed checks (s4..s7 are the samples), then answered requests: never 5 in a row.
        c = FailingCheckClient(clock, ttl=36000, fail={f"s{n}": C.ClientError("x") for n in (4, 5, 6, 7)})
        reason, ev = go(c, clock, ages=("2.5m", "5m", "7.5m", "10m", "15m"))
        self.assertEqual(sum(e["event"] == "check-failed" for e in ev), 4)
        self.assertIsNone(reason)
        c = FailingCheckClient(clock, ttl=36000, fail={f"s{n}": C.ClientError("x") for n in (3, 4, 5, 6, 7)})
        reason, ev = go(c, clock, ages=("2.5m", "5m", "7.5m", "10m", "15m"))
        self.assertEqual(reason, "failing")

    def test_failing_is_a_stop_reason_and_smoke_weekly_and_the_builder_take_it(self):
        import weekly
        self.assertIn("failing", probe.STOP_REASONS)
        start = {"event": "start", "model": "m", "harness": "devin", "ages": "2.5m", "isolation": probe.ISOLATION}
        stop = {"event": "stop", "reason": "failing"}
        self.assertEqual(weekly.public_line_problems(dict(stop, at="x"), start), [])
        self.assertEqual(weekly.login_outcome([start, stop]), {"outcome": "failed", "kind": "failing"})
        warm = {"event": "check", "age": "control", "late": False, "warm": True, "usage": {"calls": 1}}
        p, _ = night.smoke_problems("S2", [start, warm, stop])
        self.assertEqual(p, ["S2: the run ended on failed requests in a row (failing; harness/probe.py, rule 4)"])
        # The builder publishes what a `failing` run measured before it stopped, as after `quota`.
        rows = own_run([warm, sample("2.5m", True), stop])
        self.assertEqual(build(self, rows)["checks"], [{"age": "2.5m", "age_s": 150, "warm": 1, "total": 1}])


# --- 2. the rate-limit match: one line, never beside a plan-limit word -----------------------------------------------

class RateLimitMatch(unittest.TestCase):
    def test_the_mixed_two_line_diagnostic_is_quota(self):
        e = C.classify(MIXED)
        self.assertEqual((type(e).__name__, e.kind), ("Refused", "quota"))
        reason, rows, refused = devin_run(self, MIXED)
        self.assertEqual((reason, len(refused)), ("quota", 1))  # never retried

    def test_the_match_is_within_one_line(self):
        split = "Error: Agent error: Reached request rate limit.\nYour limit will reset in 2 seconds (at 11:15 UTC)."
        self.assertIsNone(C.rate_reset(split))
        self.assertEqual(C.classify(split).kind, "quota")
        self.assertEqual(C.classify(DEVIN_RATE).kind, "rate-limited")  # tonight's text, its JSON on later lines

    def test_a_plan_limit_word_makes_it_quota(self):
        line = "Reached request rate limit. Your limit will reset in 2 seconds (at 11:15 UTC)."
        for word in ("for this billing period", "monthly", "credits", "usage limit", "ACU", "out of usage"):
            with self.subTest(word=word):
                self.assertEqual(C.classify(f"{line} ({word})").kind, "quota")
        for text in (CREDITS, "Error: Monthly limit exceeded.", "Error: rate-limit exceeded.",
                     "HTTP 429: monthly ACU limit reached. Retry-After: 10"):
            with self.subTest(text=text):
                self.assertEqual(C.classify(text).kind, "quota")


# --- 3. one pair of clock readings for the control ------------------------------------------------------------------

class StepClock:
    """The reviewer's clock (clock_queue_replay.py): wall and monotonic together; `step` adds 10 s to the wall clock
    alone at a chosen moment of the first control: `before-gate` (during the 30 s wait) or `between-reads` (right after
    the control's monotonic reading, where the old gate and the old send each read the clocks)."""

    def __init__(self, step=None):
        self.wall = self.m = 0.0
        self.step, self.armed = step, False

    def now(self):
        return self.wall

    def mono(self):
        if self.armed:
            self.armed = False
            self.wall += 10
        return self.m

    def advance(self, s):
        self.wall += s
        self.m += s

    def sleep(self, s):
        self.advance(max(0, s))
        if 25 <= s <= 30 and self.step:
            if self.step == "before-gate":
                self.wall += 10
            else:
                self.armed = True
            self.step = None


class StepClient:
    def __init__(self, clock):
        self.c, self.sent, self.n = clock, [], 0

    def start(self, prompt):
        self.n += 1
        self.c.advance(1)
        return f"s{self.n}", {"calls": 1, "model": "m", "total": 8000 if "<doc>" in prompt else 2000, "cached": 2000,
                              "write": 0}

    def resume(self, handle, prompt):
        self.sent.append(handle)
        self.c.advance(1)
        return {"calls": 1, "model": "m", "total": 8020, "cached": 8000, "write": 0}


def step_run(step, ages=("2.5m",)):
    clock = StepClock(step)
    client, ev = StepClient(clock), []
    secs = [probe.parse_age(a) for a in ages]
    reason = probe.run_probe(client, ages=secs, labels=list(ages), replicas=1, words=10, salt="t", log=ev.append,
                             clock=clock, rng=MinJitter())
    return reason, ev, client


class OneClockReading(unittest.TestCase):
    def test_a_10_s_step_between_gate_and_send_never_gives_a_warm_late_control(self):
        # The reviewer's case: the old gate read the clocks, then the send read them again with the wall 10 s on:
        # a control row warm and late (40 wall / 30 monotonic). Now the gate is the send's own pair of readings.
        reason, ev, client = step_run("between-reads")
        controls = [e for e in ev if e["event"] == "check" and e["age"] == "control"]
        self.assertEqual([(e["realAgeSec"], e["monoAgeSec"], e["late"], e["warm"]) for e in controls],
                         [(30, 30, False, True)])
        self.assertIsNone(reason)

    def test_a_step_before_the_gate_ends_control_late_and_the_control_is_not_sent(self):
        reason, ev, client = step_run("before-gate")
        self.assertEqual(reason, "control-late")
        self.assertEqual(client.sent, [])
        self.assertFalse([e for e in ev if e["event"] == "check"])

    def test_no_control_row_is_ever_both_warm_and_late(self):
        for step in (None, "before-gate", "between-reads"):
            with self.subTest(step=step):
                _, ev, _ = step_run(step)
                self.assertFalse([e for e in ev if e["event"] == "check" and e["age"] == "control" and e["late"]])

    def test_the_control_reads_the_clocks_once(self):
        class Counting(StepClock):
            def __init__(self):
                super().__init__()
                self.reads = []

            def now(self):
                self.reads.append("now")
                return super().now()

            def mono(self):
                self.reads.append("mono")
                return super().mono()

            def sleep(self, s):
                super().sleep(s)
                if 25 <= s <= 30:
                    self.reads.append("control wait")
        clock = Counting()
        client = StepClient(clock)
        at_send = []

        def resume(handle, prompt, orig=client.resume):
            at_send.append(list(clock.reads[clock.reads.index("control wait") + 1:]))
            return orig(handle, prompt)
        client.resume = resume
        probe.run_probe(client, ages=[], labels=[], replicas=0, words=10, salt="t", log=lambda e: None, clock=clock)
        self.assertEqual(client.sent, ["s2"])
        self.assertEqual(at_send, [["now", "mono"]])  # between the wait and the send: one pair, gate and record


# --- 4. the builder: a run's samples only beside a valid warm control ------------------------------------------------

def sample(age, warm, **kw):
    return dict({"event": "check", "age": age, "late": False, "warm": warm,
                 "usage": {"calls": 1, "model_matches": True, "total": 8020, "cached": 8000}}, **kw)


def own_run(rows):
    start = {"event": "start", "harness": "devin", "model": "m", "isolation": probe.ISOLATION}
    out = [dict(start, at="2026-11-24T00:00:00+00:00")]
    for r in rows:
        if r.get("event") == "check":
            r = dict(r, usage=dict(r.get("usage") or {}, model_matches=True, total=8020, cached=8000))
        out.append(dict(r, at="2026-11-24T00:00:00+00:00"))
    return out


def build(test, rows):
    tmp = tempfile.mkdtemp(prefix="gt-last-b-")
    test.addCleanup(shutil.rmtree, tmp, True)
    rel = os.path.join("results", "own-clients-2026-11-24")
    os.makedirs(os.path.join(tmp, rel))
    with open(os.path.join(tmp, rel, "AUDIT.md"), "w") as f:
        f.write(B.FIRST_LINES["own-clients"] + "\n")
    with open(os.path.join(tmp, rel, "fixture.jsonl"), "w") as f:
        f.write("".join(json.dumps(r) + "\n" for r in rows))
    with mock.patch.object(B, "ROOT", tmp):
        return B.build_cache({"runs": [{"id": "fixture", "file": os.path.join(rel, "fixture.jsonl"), "route": "devin",
                                        "model": "m"}]})[0]


LADDER = [sample(a, True) for a in ("2.5m", "5m", "7.5m")]


class BuilderControlRule(unittest.TestCase):
    def test_zero_valid_controls_rejects_the_whole_run_and_names_why(self):
        # The reviewer's case: a cold control and a warm-but-late one; the builder accepted 42 samples.
        rows = [sample("control", False), sample("control", True, late=True)] + LADDER * 14
        with self.assertRaisesRegex(SystemExit, r"fixture: no valid warm control \(valid controls 1, warm 0; late 1, "
                                                r"invalid 0\): its 42 samples are not counted"):
            build(self, own_run(rows))

    def test_an_invalid_control_is_no_control(self):
        rows = [{"event": "check-invalid", "age": "control", "reason": "not-one-call"}] + LADDER
        with self.assertRaisesRegex(SystemExit, r"no valid warm control .*invalid 1"):
            build(self, own_run(rows))

    def test_one_valid_warm_control_counts_the_samples(self):
        e = build(self, own_run([sample("control", False), sample("control", True)] + LADDER))
        self.assertEqual((e["control"], sum(c["total"] for c in e["checks"])), ({"warm": 1, "total": 2}, 3))

    def test_a_run_ended_at_its_cold_controls_is_still_published(self):
        e = build(self, own_run([sample("control", False), sample("control", False),
                                 {"event": "stop", "reason": "no-observable-cache"}]))
        self.assertEqual((e["control"], e["checks"]), ({"warm": 0, "total": 2}, []))


# --- 5. the docs: the plan's peaks are an estimate --------------------------------------------------------------------

class Docs(unittest.TestCase):
    def test_both_docs_say_the_peaks_are_an_estimate(self):
        for name in ("own-clients.md", "own-clients-RUN.md"):
            with open(os.path.join(ROOT, "docs", name)) as f:
                text = f.read()
            with self.subTest(doc=name):
                self.assertIn("an estimate, not a bound", text)
                self.assertIn("49", text)
                self.assertIn("430", text)


if __name__ == "__main__":
    unittest.main()
