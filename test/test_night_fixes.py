"""The fixes after the first own-client night (2026-11-23), where 17 of 25 runs stopped, as simplified after the first
review: no same-session retry of a check; Devin's own rate-limit text alone is `rate-limited`; the schedule is planned
before the go (no pacer); model ids from the checked list only; the clock check; the second control; `status` in any
locale; the re-run of chosen runs. Nothing is sent and no client is run: fakes and a fake or simulated clock.

    python3 -m unittest discover -s test -p "test_*.py"
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from types import SimpleNamespace
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "harness"))
sys.path.insert(0, HERE)
import clients as C  # noqa: E402
import client_limits as CL  # noqa: E402
import model_ids as M  # noqa: E402
import night  # noqa: E402
import night_plan as NP  # noqa: E402
import probe  # noqa: E402
import test_second_review as R2  # noqa: E402
from test_probe import FakeClient, FakeClock, go as loop, checks  # noqa: E402

ROOT = os.path.dirname(HERE)
FIXTURES = os.path.join(HERE, "fixtures", "clients")
# What Devin printed tonight (results/own-clients-2026-11-23/logs/DV1.log, 11:14:17 UTC), on its stderr.
DEVIN_RATE = ("Error: Agent error: Reached request rate limit. Please switch to a different model or contact support. "
              "Your limit will reset in 2 seconds (at 11:15 UTC).: {\n  \"cognition.ai/errorKind\": \"unavailable\",\n"
              "  \"cognition.ai/retryable\": true\n}")
AT_111417 = 1795000000 - 1795000000 % 86400 + 11 * 3600 + 14 * 60 + 17  # 11:14:17 UTC of some day
SHARED = 18000


def fx(client, case):
    with open(os.path.join(FIXTURES, client, case + ".json")) as f:
        return json.load(f)


def scratch(test):
    tmp = tempfile.mkdtemp(prefix="gt-fixes-")
    test.addCleanup(shutil.rmtree, tmp, True)
    return tmp


# --- A. no same-session retry of a check; a priming again only in a new session ------------------------------------

class FailingCheckClient(FakeClient):
    """FakeClient whose checks of the sessions in `fail` (handle -> an exception to raise) fail after being sent (the
    request counted), and whose primings whose prompt holds a key of `refuse` (-> an exception, how many times) fail."""

    def __init__(self, clock, ttl, fail=None, refuse=None, **kw):
        super().__init__(clock, ttl, **kw)
        self.failing, self.refuse, self.prompts = dict(fail or {}), dict(refuse or {}), []

    def start(self, prompt):
        self.prompts.append(prompt)
        for key, (exc, times) in list(self.refuse.items()):
            if key in prompt and times:
                self.refuse[key] = (exc, times - 1)
                self.requests += 1
                self.clock.t += self.took
                raise exc
        return super().start(prompt)

    def resume(self, handle, prompt):
        if handle in self.failing:
            self.requests += 1
            self.resumes.append(handle)
            self.clock.t += self.took
            raise self.failing[handle]
        return super().resume(handle, prompt)


def devin_rate(n=2):
    return C.Refused("rate-limited", f"Reached request rate limit. Your limit will reset in {n} seconds (at 11:15 UTC)",
                     reset={"in": float(n), "at": None})


class NoCheckRetry(unittest.TestCase):
    def test_a_check_that_fails_after_it_was_sent_is_lost_and_never_resumed_again(self):
        # s5: the 2.5m sample (baseline s0, control s1, its check, then 7.5m s3, 5m s4, 2.5m s5).
        for exc, kind in ((devin_rate(), "rate-limited"),
                          (C.ClientError("exit 1: Agent error: The model ended its turn without a response.",
                                         kind="exit-nonzero"), "exit-nonzero"),
                          (C.ClientError("connection reset"), "other"),
                          (C.Refused("input", "prompt is too long"), "input")):
            with self.subTest(kind=kind):
                clock = FakeClock()
                c = FailingCheckClient(clock, ttl=3600, fail={"s5": exc})
                reason, ev = loop(c, clock)
                self.assertIsNone(reason)
                self.assertEqual(c.resumes.count("s5"), 1)
                failed = [e for e in ev if e["event"] == "check-failed"]
                self.assertEqual([(e["age"], e.get("kind") or e.get("error_kind")) for e in failed], [("2.5m", kind)])
                self.assertEqual([a for a, _ in checks(ev)], ["control", "5m", "7.5m"])

    def test_a_failed_priming_is_tried_again_in_a_new_session_with_a_new_block(self):
        clock = FakeClock()
        c = FailingCheckClient(clock, ttl=3600, refuse={"t-1,": (C.ClientError("exit 1"), 1),
                                                         "t-2,": (C.ClientError("exit 1"), 1)})
        reason, ev = loop(c, clock)
        self.assertIsNone(reason)
        tried = [p for p in c.prompts if "Reference document" in p and "-control" not in p]
        blocks = [p.split("Reference document ", 1)[1].split(",", 1)[0] for p in tried]
        self.assertEqual(len(blocks), len(set(blocks)))  # every try its own block, so its own session
        self.assertEqual([e["try"] for e in ev if e["event"] == "retry"], [1, 2])
        primes = [e for e in ev if e["event"] == "prime" and e["age"] == "7.5m"]
        self.assertEqual(len(primes), 1)

    def test_a_rate_limited_priming_waits_for_the_reset_then_a_new_session(self):
        clock = FakeClock()
        c = FailingCheckClient(clock, ttl=3600, refuse={"t-1,": (devin_rate(40), 1)})
        reason, ev = loop(c, clock)
        self.assertIsNone(reason)
        r = [e for e in ev if e["event"] == "retry"]
        self.assertEqual([(e["age"], e["error_kind"]) for e in r], [("7.5m", "rate-limited")])
        self.assertTrue(41 <= r[0]["waitSec"] <= 45)
        self.assertEqual([a for a, _ in checks(ev)], ["control", "2.5m", "5m", "7.5m"])

    def test_at_most_three_tries_of_a_priming(self):
        clock = FakeClock()
        c = FailingCheckClient(clock, ttl=3600, refuse={"t-": (C.ClientError("exit 1"), 99)})
        c.refuse = {"Reference document t-1,": (C.ClientError("exit 1"), 99),
                    "Reference document t-2,": (C.ClientError("exit 1"), 99),
                    "Reference document t-3,": (C.ClientError("exit 1"), 99)}
        reason, ev = loop(c, clock, ages=("2.5m",))
        self.assertIsNone(reason)
        self.assertEqual([e["event"] for e in ev if e.get("age") == "2.5m"], ["retry", "retry", "retry", "prime-failed"])

    def test_a_priming_s_wait_never_holds_a_check_that_falls_due(self):
        clock = FakeClock()
        c = FailingCheckClient(clock, ttl=36000, refuse={"t-3,": (C.ClientError("exit 1"), 99)})
        reason, ev = loop(c, clock, ages=("2.5m", "5m", "7.5m", "10m"))
        self.assertIsNone(reason)
        self.assertFalse([e for e in ev if e["event"] == "check" and e["late"]])

    def test_three_rate_limited_refusals_in_a_row_end_the_run_as_quota(self):
        clock = FakeClock()
        c = FailingCheckClient(clock, ttl=3600, refuse={"t-1,": (devin_rate(), 9), "t-2,": (devin_rate(), 9),
                                                                 "t-3,": (devin_rate(), 9)})
        reason, ev = loop(c, clock)
        self.assertEqual(reason, "quota")
        self.assertEqual(sum(1 for e in ev if e.get("error_kind") == "rate-limited" or e.get("kind") == "rate-limited"),
                         3)

    def test_a_success_between_ends_the_row(self):
        clock = FakeClock()
        c = FailingCheckClient(clock, ttl=3600, fail={"s4": devin_rate(), "s5": devin_rate()},
                               refuse={"t-4,": (devin_rate(), 1)})
        reason, ev = loop(c, clock)
        self.assertIsNone(reason)

    def test_a_plan_limit_still_ends_the_run(self):
        clock = FakeClock()
        c = FakeClient(clock, ttl=3600)
        c.refuse_prime[3] = "quota"
        reason, ev = loop(c, clock)
        self.assertEqual(reason, "quota")

    def test_tonight_s_code_sent_each_check_once(self):
        # main d80a6dd, harness/probe.py check_once: a failed check is check-failed and never sent again.
        out = subprocess.run(["git", "-C", ROOT, "show", "0950369:harness/probe.py"], capture_output=True, text=True)
        if out.returncode:
            self.skipTest("the base commit is not in this clone")
        body = out.stdout.split("def check_once", 1)[1].split("\n    try:\n        b = prime", 1)[0]
        self.assertEqual(body.count("h.resume("), 1)
        self.assertNotIn("for i in range", body)


# --- B. rate limit vs quota ---------------------------------------------------------------------------------------

class RateLimitKinds(unittest.TestCase):
    def test_tonight_s_devin_refusal_is_rate_limited_with_its_reset(self):
        e = C.classify(DEVIN_RATE)
        self.assertEqual(e.kind, "rate-limited")
        self.assertEqual(e.reset, {"in": 2.0, "at": 11 * 3600 + 15 * 60})
        self.assertEqual(C.reset_wait(e.reset, AT_111417), 43)  # the later of the two: 11:15:00

    def test_the_devin_parse_and_the_session_keep_the_reset(self):
        with self.assertRaises(C.Refused) as r:
            C.Devin("glm-5-3-low").parse("", DEVIN_RATE, 1, {})
        self.assertEqual((r.exception.kind, r.exception.reset["in"]), ("rate-limited", 2.0))
        tmp = scratch(self)
        s = C.Session(C.Devin("glm-5-3-low"), env={}, io=os.path.join(tmp, "io"), work=os.path.join(tmp, "w"),
                      run=lambda *a, **k: (1, "", DEVIN_RATE))
        with self.assertRaises(C.Refused) as r:
            s.start("x")
        self.assertEqual(r.exception.reset, {"in": 2.0, "at": 40500})

    def test_every_other_rate_or_quota_text_is_quota(self):
        for text in ("You've hit your usage limit. Try again later.", "Claude AI usage limit reached. Your limit resets at 3am.",
                     "429 Too Many Requests: quota exceeded", "You've hit your request rate limit. Retry in 2 seconds.",
                     "HTTP 429: monthly ACU limit reached. Retry-After: 10", "rate limit exceeded, retry in 30s",
                     "Reached request rate limit.", "Error: you have reached your usage limit for this billing period"):
            with self.subTest(text=text):
                self.assertEqual(C.classify(text).kind, "quota")

    def test_every_quota_fixture_is_still_quota(self):
        for client in ("claude", "codex", "devin", "muse"):
            f = fx(client, "quota")
            with self.subTest(client=client), self.assertRaises(C.Refused) as r:
                C.CLIENTS[client]("m").parse(f["stdout"], f["stderr"], f["code"], f["files"])
            self.assertEqual(r.exception.kind, "quota")

    def test_the_input_limits_walk_ends_on_a_rate_limit_with_no_row(self):
        class S:
            def start(self, prompt):
                raise devin_rate()
        rows = []
        CL.walk(S(), "m", "devin-cli", None, rows.append, say=lambda *_: None)
        self.assertEqual(rows, [])

    def test_the_public_lines_of_a_rate_limited_run_are_in_the_schema(self):
        import weekly
        start = {"event": "start", "model": "m", "harness": "devin", "ages": "2.5m"}
        for line in ({"event": "retry", "age": "2.5m", "error_kind": "rate-limited", "try": 1, "waitSec": 43.2},
                     {"event": "check-failed", "age": "2.5m", "kind": "rate-limited", "rep": 1, "monoAgeSec": 150}):
            self.assertEqual(weekly.public_line_problems(dict(line, at="x"), start), [])


# --- C. the schedule, planned before the go -----------------------------------------------------------------------

class Schedule(unittest.TestCase):
    def test_the_pacer_is_gone(self):
        self.assertFalse(os.path.exists(os.path.join(ROOT, "harness", "pacing.py")))
        argv = night.command(night.ALL_STEPS["DV1"], "2099-01-01", launch_id="L", delay=0)
        self.assertFalse([a for a in argv if "pace" in a])
        self.assertNotIn("pace", probe.parser().format_help())

    def test_window_max(self):
        self.assertEqual(NP.window_max([0, 1, 59.9, 60, 120], 60), 3)
        self.assertEqual(NP.window_max([], 60), 0)

    def test_the_devin_schedule_keeps_under_40_a_minute_and_300_a_quarter_hour(self):
        sel = night.runs_of(["devin"])
        p = night.plan(sel)["devin"]
        self.assertLessEqual(p["max"][60], 40)
        self.assertLessEqual(p["max"][900], 300)
        starts = list(p["starts"].values())
        self.assertEqual(starts, sorted(starts))
        self.assertTrue(all(b - a >= 20 for a, b in zip(starts, starts[1:])))
        self.assertEqual(p["requests"], 16 * 87 + 3 * 105)

    def test_the_limits_are_configurable_and_the_go_refuses_a_schedule_over_them(self):
        with mock.patch.dict(night.LIMITS, {"devin": {60: 30, 900: 200}}):
            p = night.plan(night.runs_of(["DV1,DV2,DV3,DV4,DV5,DV6"]))["devin"]
            self.assertLessEqual((p["max"][60], p["max"][900]), (30, 200))
        with mock.patch.dict(night.LIMITS, {"devin": {60: 5, 900: 300}}), \
                self.assertRaisesRegex(SystemExit, "alone passes the limits"):
            night.plan(night.runs_of(["DV1"]))
        planned = {"devin": {"limits": {60: 40}, "max": {60: 41, 900: 10}}}
        with self.assertRaisesRegex(SystemExit, "41 requests in 60 s, over 40"):
            night.refuse_over_limits(planned, "--go")
        with mock.patch.dict(night.LIMITS, {}), mock.patch.object(night, "dry_run_go", lambda *a, **k: None):
            night.main(["--date", "2099-01-01", "--limit", "devin=30/250", "--dry-run", "devin"])
            self.assertEqual(night.LIMITS["devin"], {60: 30, 900: 250})
        with self.assertRaises(SystemExit):
            night.main(["--date", "2099-01-01", "--limit", "devin=fast", "--dry-run", "devin"])

    def test_the_plan_is_the_real_loop(self):
        run = night.sim_runs([night.ALL_STEPS["DV1"]])[0]
        times, end = NP.profile(run, 4.0)
        self.assertEqual(len(times), 87)
        self.assertTrue(2 * 3600 < end < 2.5 * 3600)

    def test_the_dry_run_reports_the_schedule_and_its_maxima(self):
        out = []
        planned = night.plan_report(night.runs_of(["DV1,DV2,DV3"]), out=out.append)
        text = "\n".join(out)
        self.assertIn("(limit 40)", text)
        self.assertIn("(limit 300)", text)
        self.assertIn("DV3 +", text)
        self.assertEqual(planned["devin"]["requests"], 3 * 87)

# --- 3. the control's second chance -------------------------------------------------------------------------------

class ColdFirstControl(FakeClient):
    """The first `cold` control checks read cold; everything else as FakeClient."""

    def __init__(self, clock, ttl, cold=1, **kw):
        super().__init__(clock, ttl, **kw)
        self.cold_left, self.control_handles = cold, set()

    def start(self, prompt):
        handle, u = super().start(prompt)
        if "Reference document t-0," in prompt or "Reference document t-c1," in prompt:
            self.control_handles.add(handle)
        return handle, u

    def resume(self, handle, prompt):
        u = super().resume(handle, prompt)
        if handle in self.control_handles and self.cold_left:
            self.cold_left -= 1
            u = dict(u, cached=SHARED)
        return u


class SecondControl(unittest.TestCase):
    def test_a_cold_control_gets_one_more_in_a_fresh_session_and_the_run_goes_on(self):
        clock = FakeClock()
        reason, ev = loop(ColdFirstControl(clock, ttl=3600, cold=1), clock)
        self.assertIsNone(reason)
        controls = [e for e in ev if e.get("age") == "control"]
        self.assertEqual([(e["event"], e.get("rep"), e.get("warm")) for e in controls],
                         [("prime", 0, None), ("check", 0, False), ("prime", 1, None), ("check", 1, True)])
        self.assertNotEqual(controls[0]["session"], controls[2]["session"])
        self.assertEqual(ev[-1]["event"], "done")

    def test_both_cold_end_the_run_after_five_requests_both_recorded(self):
        clock = FakeClock()
        c = FakeClient(clock, ttl=10)
        reason, ev = loop(c, clock)
        self.assertEqual(reason, "no-observable-cache")
        self.assertEqual(c.requests, 5)
        self.assertEqual(checks(ev), [("control", False), ("control", False)])

    def test_the_smoke_review_takes_a_second_control(self):
        start = {"event": "start", "isolation": night.ISOLATION}
        cold = {"event": "check", "age": "control", "late": False, "warm": False, "usage": {"calls": 1}}
        warm = dict(cold, warm=True)
        p, n = night.smoke_problems("S2", [start, cold, warm, {"event": "done"}])
        self.assertEqual(p, [])
        self.assertIn("second (a fresh session) warm", n[0])
        p, n = night.smoke_problems("S3b", [start, cold, cold, {"event": "stop", "reason": "no-observable-cache"}],
                                    cold_expected=True)
        self.assertEqual(p, [])
        p, _ = night.smoke_problems("S2", [start, warm, warm, {"event": "done"}])
        self.assertTrue(p)

    def test_the_builder_counts_both_controls(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("bo", os.path.join(ROOT, "scripts", "build_observed.py"))
        bo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bo)
        clock = FakeClock()
        _, ev = loop(ColdFirstControl(clock, ttl=3600, cold=1), clock)
        rows = [{"event": "start", "harness": "devin", "model": "m", "at": "2026-11-24T00:00:00+00:00"}]
        for e in ev:
            e.pop("handle", None)
            rows.append(dict(e, at="2026-11-24T00:00:00+00:00"))
        tmp = scratch(self)
        with open(os.path.join(tmp, "r.jsonl"), "w") as f:
            f.write("".join(json.dumps(r) + "\n" for r in rows))
        with mock.patch.object(bo, "ROOT", tmp):
            self.assertEqual(bo.read_harness("r.jsonl")["control"], [False, True])


# --- D. model ids: the checked list only --------------------------------------------------------------------------

class ModelIds(unittest.TestCase):
    def test_dv12_is_deepseek_v4_pro_high_and_every_run_is_in_the_checked_list(self):
        self.assertEqual(night.ALL_STEPS["DV12"]["model"], "deepseek-v4-pro-high")
        for s in night.ALL_STEPS.values():
            with self.subTest(run=s["id"]):
                self.assertIn(s["model"], M.checked(s["harness"]))
        self.assertNotIn("deepseek-v4-pro-low", M.checked("devin"))

    def test_an_unknown_id_is_refused_by_name_in_the_dry_run_and_the_go(self):
        with mock.patch.dict(night.ALL_STEPS["DV12"], model="deepseek-v4-pro-low"), \
                mock.patch.object(night, "dry_run", side_effect=AssertionError("planned")), \
                self.assertRaisesRegex(SystemExit, r"DV12 \(deepseek-v4-pro-low\)"):
            night.dry_run_go(["DV12"], "2099-01-01", out=lambda *_: None)
        with mock.patch.dict(night.ALL_STEPS["CX3"], model="gpt-9"), mock.patch.object(night, "guard"), \
                mock.patch.object(night, "launch") as launch, \
                self.assertRaisesRegex(SystemExit, r"--go: refused: .*CX3 \(gpt-9\)"):
            night.go_clients(["CX1,CX3"], "2099-01-01", popen=lambda *a, **k: None, out=lambda *_: None)
        launch.assert_not_called()

    def test_no_client_is_run_to_list_models(self):
        import inspect
        src = inspect.getsource(M)
        for gone in ("subprocess", "models list", "debug models", "tempfile", "sandbox"):
            self.assertNotIn(gone, src.split('"""', 2)[2])
        with mock.patch.object(night.subprocess, "run", side_effect=AssertionError("a client was run")):
            night.check_ids(list(night.ALL_STEPS.values()), "--go")


# --- E. the clock check, F. the second control's rep ------------------------------------------------------------

class SkewClock(FakeClock):
    """FakeClock with a monotonic clock that misses `lost` seconds of the next sleep longer than `after` (a sleep
    macOS's monotonic clock does not count), or a wall clock step."""

    def __init__(self):
        super().__init__()
        self.m, self.lose = 5000.0, None

    def mono(self):
        return self.m

    def sleep(self, seconds):
        if seconds > 0:
            self.t += seconds
            lost = self.lose if self.lose and seconds > 60 else 0
            if lost:
                self.lose = None
            self.m += seconds - lost


class MonoFakeClient(FakeClient):
    def start(self, prompt):
        self.clock.m += self.prime_took.get(self.requests, self.took)
        return super().start(prompt)

    def resume(self, handle, prompt):
        self.clock.m += self.took
        return super().resume(handle, prompt)


class ClockCheck(unittest.TestCase):
    def test_both_ages_are_recorded_and_agree(self):
        clock = SkewClock()
        reason, ev = loop(MonoFakeClient(clock, ttl=3600), clock)
        for e in (e for e in ev if e["event"] == "check"):
            self.assertLessEqual(abs(e["realAgeSec"] - e["monoAgeSec"]), 1)
            self.assertFalse(e["late"])

    def test_a_check_whose_clocks_disagree_by_more_than_5_s_is_late_and_left_out(self):
        clock = SkewClock()
        clock.lose = 30  # a sleep of 30 s the monotonic clock does not count
        reason, ev = loop(MonoFakeClient(clock, ttl=36000), clock)
        late = [e for e in ev if e["event"] == "check" and e["late"]]
        self.assertTrue(late)
        self.assertTrue(all(e["realAgeSec"] - e["monoAgeSec"] >= 29 for e in late))
        self.assertTrue(all(e["realAgeSec"] <= probe.late_after(e["ageSec"]) for e in late))  # on time by the wall

    def test_a_control_whose_clocks_disagree_ends_control_late(self):
        clock = SkewClock()
        c = MonoFakeClient(clock, ttl=3600)
        orig = clock.sleep

        def sleep(seconds):  # the 30 s control wait: the monotonic clock counts 20
            orig(seconds)
            if 25 <= seconds <= 30:
                clock.m -= 10
        clock.sleep = sleep
        reason, ev = loop(c, clock)
        self.assertEqual(reason, "control-late")

    def test_the_second_control_s_check_carries_rep_1(self):
        clock = FakeClock()
        reason, ev = loop(ColdFirstControl(clock, ttl=3600, cold=1), clock)
        self.assertEqual([e["rep"] for e in ev if e["event"] == "check" and e["age"] == "control"], [0, 1])


# --- 5. status and stop in any language -------------------------------------------------------------------------

OWNER = "Mon 23 Nov 13:02:41 2026"  # the owner's shell: tonight's lock
C_LOCALE = "Mon Nov 23 13:02:41 2026"  # a LANG=C.UTF-8 shell


class Lstart(unittest.TestCase):
    def test_both_spellings_are_one_moment_and_another_moment_is_not(self):
        self.assertEqual(night.lstart_time(OWNER), night.lstart_time(C_LOCALE))
        self.assertEqual(night.lstart_time(OWNER), (2026, 11, 23, 13, 2, 41))
        self.assertTrue(night.same_start(C_LOCALE, OWNER))
        self.assertTrue(night.same_start(OWNER, C_LOCALE))
        self.assertFalse(night.same_start("Mon Nov 23 13:02:42 2026", OWNER))
        self.assertFalse(night.same_start("", OWNER))
        self.assertTrue(night.same_start("T", "T"))  # what is not a time is compared as text

    def test_ps_is_read_in_the_c_locale(self):
        seen = {}

        def run(argv, **kw):
            seen.update(kw.get("env") or {})
            return SimpleNamespace(returncode=0, stdout=C_LOCALE + "\n")
        with mock.patch.object(night.subprocess, "run", run), mock.patch.dict(os.environ, {"LANG": "en_GB.UTF-8"}):
            self.assertEqual(night.process_started(1234), C_LOCALE)
        self.assertEqual(seen.get("LC_ALL"), "C")

    def test_a_real_process_matches_a_lock_written_in_either_spelling(self):
        mine = night.process_started(os.getpid())
        t = night.lstart_time(mine)
        self.assertIsNotNone(t)
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        day_first = f"{mine.split()[0]} {t[2]} {months[t[1] - 1]} {t[3]:02d}:{t[4]:02d}:{t[5]:02d} {t[0]}"
        self.assertTrue(night.same_start(night.process_started(os.getpid()), day_first))
        self.assertTrue(night.same_start(night.process_started(os.getpid()), mine))

    def test_status_and_stop_see_tonight_s_live_runs_from_a_c_shell(self):
        lock = {"launch_id": "2026-11-23-devin-0123456789ab", "launcher_pid": 4000, "launcher_started": OWNER,
                "launcher_command": "python3 harness/night.py --go devin", "started": "x",
                "runs": {"DV8": {"pid": 4242, "started": OWNER}}}
        ps = {4242: "python3 harness/probe.py --label DV8 --out x --launch-id 2026-11-23-devin-0123456789ab",
              4000: "python3 harness/night.py --go devin"}

        def started(pid):
            return C_LOCALE
        self.assertEqual(night.runs_alive(lock, ps=ps.get, started=started), {4242: "DV8"})
        self.assertTrue(night.launcher_alive(lock, started=started, ps=ps.get))
        self.assertEqual(night.runs_alive(lock, ps=ps.get, started=lambda pid: "Mon Nov 23 13:02:40 2026"), {})
        with mock.patch.object(night, "read_lock_any", lambda d, n: lock if n == "devin" else None):
            self.assertEqual(night.status("2026-11-23", ps=ps.get, out=lambda *_: None, started=started),
                             {"alive": 1})


# --- 6. re-running some runs ------------------------------------------------------------------------------------

DATE = "2099-06-20"


class Rerun(R2.Owner):
    def ready(self):
        base = self.client_home()
        p = mock.patch.object(night, "process_started", lambda pid: "T")
        p.start()
        self.addCleanup(p.stop)
        night.make_night_dir(DATE)
        R2.write(night.everyday_path(DATE), json.dumps({"files": {}, "keychain": []}))
        folder = os.path.join(self.repo, night.folders(DATE)["smoke"])
        for step in night.PARTS["smoke"]:
            rows = [{"event": "start", "isolation": night.ISOLATION}, {"event": "baseline"},
                    {"event": "prime", "age": "control"},
                    {"event": "check", "age": "control", "late": False, "warm": True, "usage": {"calls": 1}},
                    {"event": "done"}]
            R2.write(os.path.join(folder, step["id"] + ".jsonl"), "".join(json.dumps(r) + "\n" for r in rows))
        night.smoke_reviewed(DATE, out=lambda *_: None)
        return base

    def popen(self):
        pids = iter(range(7000, 8000))
        self.started = []

        def popen(argv, **kw):
            self.started.append(argv)
            return SimpleNamespace(pid=next(pids))
        return popen

    def test_a_list_of_run_ids(self):
        sel = night.runs_of(["CX1,CX3,DV1", "DV12"])
        self.assertEqual({k: [s["id"] for s in v] for k, v in sel.items()},
                         {"codex": ["CX1", "CX3"], "devin": ["DV1", "DV12"]})
        self.assertFalse(night.whole(sel))
        self.assertTrue(night.whole(night.runs_of(["devin"])))
        for bad in (["S2"], ["CX1,XX9"], ["claude"]):
            with self.subTest(bad=bad), self.assertRaises(SystemExit):
                night.runs_of(bad)

    def test_go_starts_exactly_the_chosen_runs_under_the_same_locks_and_rules(self):
        self.ready()
        locks = night.go_clients(["CX1,CX3,DV1,DV12"], DATE, popen=self.popen(), out=lambda *_: None)
        self.assertEqual([sorted(lk["runs"]) for lk in locks], [["CX1", "CX3"], ["DV1", "DV12"]])
        labels = [a[a.index("--label") + 1] for a in self.started]
        self.assertEqual(labels, ["CX1", "CX3", "DV1", "DV12"])
        self.assertEqual([lk["runs"][r]["delay_s"] for lk in locks for r in sorted(lk["runs"])], [0, 15, 0, 20])
        dv12 = self.started[3]
        self.assertEqual(dv12[dv12.index("--model") + 1], "deepseek-v4-pro-high")
        self.assertFalse([a for a in dv12 if "pace" in a])
        with self.assertRaisesRegex(SystemExit, "launched already"):
            night.go_clients(["CX6"], DATE, popen=self.popen(), out=lambda *_: None)

    def test_the_go_of_a_list_keeps_the_night_s_rules(self):
        self.client_home()
        with self.assertRaisesRegex(SystemExit, "snapshot"):
            night.go_clients(["CX1,DV1"], DATE, popen=self.popen(), out=lambda *_: None)
        self.assertEqual(self.started, [])

    def test_a_run_with_results_on_that_date_is_refused(self):
        self.ready()
        R2.write(os.path.join(self.repo, night.folders(DATE)["own"], "DV1.jsonl"), "{}\n")
        popen = self.popen()
        with self.assertRaisesRegex(SystemExit, "DV1 have results for"):
            night.go_clients(["DV1,DV2"], DATE, popen=popen, out=lambda *_: None)
        self.assertEqual(self.started, [])

    def test_main_takes_the_list(self):
        seen = []
        with mock.patch.object(night, "go_clients", lambda names, date: seen.append(names)):
            night.main(["--date", DATE, "--go", "CX1,CX3,DV1"])
        self.assertEqual(seen, [["CX1", "CX3", "DV1"]])
        with mock.patch.object(night, "dry_run", lambda *a, **k: None), redirect_stdout(StringIO()) as out:
            night.main(["--date", DATE, "--dry-run", "CX1,DV12"])
        self.assertIn("`--go CX1,DV12`", out.getvalue())
        self.assertIn("The plan", out.getvalue())


class Docs(unittest.TestCase):
    def test_the_run_doc_has_the_re_run_section_and_names_main(self):
        with open(os.path.join(ROOT, "docs", "own-clients-RUN.md")) as f:
            text = f.read()
        self.assertIn("## Re-running some runs", text)
        self.assertIn("--go CX1,CX3,DV1", text)
        self.assertNotIn("`own-clients` branch", text)


if __name__ == "__main__":
    unittest.main()
