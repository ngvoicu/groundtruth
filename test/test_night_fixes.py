"""The fixes after the first own-client night (2026-11-23), where 17 of 25 runs stopped: a rate limit taken for quota,
no shared request budget, one cold control ending a run, an unknown model id, `status` tied to the shell's language;
and the re-run of chosen runs. Nothing is sent and no client is run: fakes, a fake or simulated clock, fake listings.

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
os.environ.setdefault("GROUNDTRUTH_MODEL_LIST", "checked")
sys.path.insert(0, os.path.join(HERE, "..", "harness"))
sys.path.insert(0, HERE)
import clients as C  # noqa: E402
import client_limits as CL  # noqa: E402
import model_ids as M  # noqa: E402
import night  # noqa: E402
import pacing as P  # noqa: E402
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


# --- 1. a rate limit waits; it is not quota ---------------------------------------------------------------------------

class RateLimitKinds(unittest.TestCase):
    def test_tonight_s_devin_refusal_is_rate_limited_with_its_reset(self):
        e = C.classify(DEVIN_RATE)
        self.assertEqual(e.kind, "rate-limited")
        self.assertEqual(e.reset, {"in": 2.0, "at": 11 * 3600 + 15 * 60})
        # The later of the two: 11:15:00, 43 s after 11:14:17 (not the 2 s).
        self.assertEqual(C.reset_wait(e.reset, AT_111417), 43)

    def test_the_devin_parse_and_the_session_keep_the_reset(self):
        with self.assertRaises(C.Refused) as r:
            C.Devin("glm-5-3-low").parse("", DEVIN_RATE, 1, {})
        self.assertEqual((r.exception.kind, r.exception.reset["in"]), ("rate-limited", 2.0))
        tmp = scratch(self)
        s = C.Session(C.Devin("glm-5-3-low"), env={}, io=os.path.join(tmp, "io"), work=os.path.join(tmp, "w"),
                      run=lambda *a, **k: (1, "", DEVIN_RATE))
        with self.assertRaises(C.Refused) as r:
            s.start("x")
        self.assertEqual(r.exception.kind, "rate-limited")
        self.assertEqual(r.exception.reset, {"in": 2.0, "at": 40500})

    def test_the_general_shape_rate_limit_reset_or_retry_in_n(self):
        for text, wait in (("rate limit exceeded, retry in 30s", 30), ("429 Too Many Requests; try again in 1 minute", 60),
                           ("Rate limit reached. Please try again in 1.5 seconds.", 1.5),
                           ("HTTP 429 rate_limited, Retry-After: 20", 20), ("rate limit: resets in 500ms", 0.5)):
            with self.subTest(text=text):
                e = C.classify(text)
                self.assertEqual(e.kind, "rate-limited")
                self.assertAlmostEqual(C.reset_wait(e.reset, 0), wait)

    def test_a_plan_limit_stays_quota_and_a_rate_limit_without_a_reset_too(self):
        for text in ("You've hit your usage limit. Try again later.",  # Codex, protocol/src/error.rs
                     "You've hit your usage limit. Upgrade to Pro or try again in 3 days 4 hours.",
                     "Error: you have reached your usage limit for this billing period",  # the Devin fixture
                     "Claude AI usage limit reached. Your limit resets at 3am.",  # the Claude fixture
                     "429 Too Many Requests: quota exceeded",  # the Muse fixture
                     "You are out of credits; reset in 30 seconds", "Reached request rate limit.",
                     "stream error: exceeded retry limit, last status: 429 Too Many Requests"):
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
                raise C.Refused("rate-limited", "rate limit, retry in 5s", reset={"in": 5, "at": None})
        rows = []
        CL.walk(S(), "m", "devin-cli", None, rows.append, say=lambda *_: None)
        self.assertEqual(rows, [])


class RateLimitedClient(FakeClient):
    """FakeClient whose primings (by a text of their prompt: `t-1,` is the first sample's) and checks (by session:
    s1 the control, s5 the 2.5m sample) listed in `limited` (-> how many times) are first refused as rate-limited, each
    refusal naming a reset `reset_in` seconds away."""

    def __init__(self, clock, ttl, limited=None, reset_in=2.0, **kw):
        super().__init__(clock, ttl, **kw)
        self.limited, self.reset_in, self.refusals = dict(limited or {}), reset_in, 0

    def _gate(self, key):
        if key and self.limited.get(key, 0) > 0:
            self.limited[key] -= 1
            self.refusals += 1
            raise C.Refused("rate-limited", f"Reached request rate limit. Your limit will reset in {self.reset_in} "
                                            "seconds", reset={"in": self.reset_in, "at": None})

    def start(self, prompt):
        self._gate(next((k for k in self.limited if k in prompt), None))
        return super().start(prompt)

    def resume(self, handle, prompt):
        self._gate(handle if handle in self.limited else None)
        return super().resume(handle, prompt)


class RateLimitWaits(unittest.TestCase):
    def test_a_rate_limited_priming_waits_and_goes_on_each_wait_an_event(self):
        clock = FakeClock()
        c = RateLimitedClient(clock, ttl=3600, limited={"t-1,": 2})  # the first sample's priming, twice
        reason, ev = loop(c, clock)
        self.assertIsNone(reason)
        waits = [e for e in ev if e["event"] == "rate-wait"]
        self.assertEqual([(w["age"], w["try"]) for w in waits], [("7.5m", 1), ("7.5m", 2)])
        self.assertTrue(all(3 <= w["waitSec"] <= 7 for w in waits))  # 2 s and 1 - 5 s of jitter
        self.assertEqual([a for a, _ in checks(ev)], ["control", "2.5m", "5m", "7.5m"])
        self.assertNotIn("stop", [e["event"] for e in ev])

    def test_a_rate_limited_check_waits_and_a_wait_that_makes_it_late_keeps_late(self):
        clock = FakeClock()
        c = RateLimitedClient(clock, ttl=36000, limited={"s5": 1}, reset_in=120)  # the 2.5m check
        reason, ev = loop(c, clock)
        self.assertIsNone(reason)
        check = next(e for e in ev if e["event"] == "check" and e["age"] == "2.5m")
        self.assertGreaterEqual(check["realAgeSec"], 150 + 120)
        self.assertTrue(check["late"])  # more than 150 x 1.1 + 90 s after its priming
        self.assertEqual(c.resumes.count(check["handle"]), 1)  # the refused try reached no model: one answer

    def test_at_most_five_tries_then_the_sample_is_lost_not_the_run(self):
        clock = FakeClock()
        c = RateLimitedClient(clock, ttl=3600, limited={"t-1,": 99})
        reason, ev = loop(c, clock)
        self.assertIsNone(reason)
        self.assertEqual(c.refusals, probe.RATE_TRIES)
        self.assertEqual(len([e for e in ev if e["event"] == "rate-wait"]), probe.RATE_TRIES - 1)
        lost = [e for e in ev if e["event"] == "prime-refused"]
        self.assertEqual([(e["age"], e["kind"]) for e in lost], [("7.5m", "rate-limited")])

    def test_at_most_ten_minutes_of_waits_for_one_sample(self):
        clock = FakeClock()
        c = RateLimitedClient(clock, ttl=3600, limited={"t-1,": 99}, reset_in=250)
        reason, ev = loop(c, clock)
        waits = [e for e in ev if e["event"] == "rate-wait"]
        self.assertEqual(len(waits), 2)  # 2 x (250 + jitter) <= 600 s; a third wait would pass it
        self.assertLessEqual(sum(w["waitSec"] for w in waits), probe.RATE_WAIT_MAX)
        self.assertEqual([e["kind"] for e in ev if e["event"] == "prime-refused"], ["rate-limited"])

    def test_a_check_that_stays_rate_limited_is_check_failed_rate_limited(self):
        clock = FakeClock()
        c = RateLimitedClient(clock, ttl=3600, limited={"s5": 99})
        reason, ev = loop(c, clock)
        self.assertIsNone(reason)
        failed = [e for e in ev if e["event"] == "check-failed"]
        self.assertEqual([(e["age"], e["kind"]) for e in failed], [("2.5m", "rate-limited")])

    def test_a_plan_limit_still_ends_the_run(self):
        clock = FakeClock()
        c = FakeClient(clock, ttl=3600)
        c.refuse_prime[3] = "quota"
        reason, ev = loop(c, clock)
        self.assertEqual(reason, "quota")
        self.assertNotIn("rate-wait", [e["event"] for e in ev])

    def test_a_rate_limited_control_check_that_would_be_late_ends_control_late(self):
        clock = FakeClock()
        c = RateLimitedClient(clock, ttl=3600, limited={"s1": 1}, reset_in=200)  # the control's check
        reason, ev = loop(c, clock)
        self.assertEqual(reason, "control-late")

    def test_the_rate_wait_line_is_in_the_public_schema(self):
        import weekly
        start = {"event": "start", "model": "m", "harness": "devin", "ages": "2.5m"}
        line = {"event": "rate-wait", "age": "2.5m", "rep": 1, "try": 2, "waitSec": 43.2, "at": "x"}
        self.assertEqual(weekly.public_line_problems(line, start), [])
        pub = probe.Public(os.path.join(scratch(self), "r.jsonl"), start)
        self.assertIn('"waitSec": 43.2', pub.line(dict(line)))
        self.assertIn('"kind": "rate-limited"', pub.line({"event": "check-failed", "age": "2.5m", "kind": "rate-limited"}))


# --- 2. pacing: one budget per client, across processes -----------------------------------------------------------

class Pacing(unittest.TestCase):
    def test_never_more_than_the_budget_in_any_minute_and_spread(self):
        clock = FakeClock()
        p = P.Pacer(P.MemoryStore(), 24, clock, jitter=0)
        times = []
        for i in range(100):
            p.acquire("check" if i % 3 == 0 else "prime")
            times.append(clock.now())
        self.assertLessEqual(P.busiest_minute(times), 24)
        self.assertGreaterEqual(min(b - a for a, b in zip(times, times[1:])), 60 / 24 - 1e-9)

    def test_primings_leave_room_for_checks(self):
        clock = FakeClock()
        p = P.Pacer(P.MemoryStore(), 24, clock, jitter=0)
        for _ in range(18):
            p.acquire("prime")
        t = clock.now()
        self.assertFalse(p.acquire("prime", until=t + 10))  # the 19th priming of the minute waits 17.5 s
        self.assertTrue(p.acquire("check", until=t + 10))  # a check goes after the 2.5 s gap

    def test_a_waiting_check_goes_before_every_priming(self):
        clock = FakeClock()
        store = P.MemoryStore()
        a, b = P.Pacer(store, 24, clock, jitter=0), P.Pacer(store, 24, clock, jitter=0)
        a.acquire("prime")
        self.assertFalse(b.acquire("check", until=clock.now() + 1))  # it must wait 2.5 s: it says so
        self.assertTrue(store.state["checks"])
        self.assertFalse(a.acquire("prime", until=clock.now() + 3))  # that turn is the check's
        self.assertTrue(b.acquire("check"))
        self.assertTrue(a.acquire("prime"))

    def test_the_budget_is_shared_by_processes_through_the_night_folder(self):
        tmp = scratch(self)
        code = ("import sys; sys.path.insert(0, sys.argv[1]); import pacing as P, probe\n"
                "p = P.Pacer(P.FileStore(sys.argv[2], 'devin'), 600, probe.Clock(), jitter=0)\n"
                "for _ in range(5): p.acquire('prime')\n")
        procs = [subprocess.Popen([sys.executable, "-c", code, os.path.join(ROOT, "harness"), tmp]) for _ in range(3)]
        for pr in procs:
            self.assertEqual(pr.wait(timeout=60), 0)
        with open(os.path.join(tmp, "devin.json")) as f:
            times = sorted(json.load(f)["times"])
        self.assertEqual(len(times), 15)  # every process's requests in the one shared record
        self.assertGreaterEqual(min(b - a for a, b in zip(times, times[1:])), 0.1 - 0.01)  # 60 / 600 s apart
        self.assertEqual(os.stat(os.path.join(tmp, "devin.json")).st_mode & 0o777, 0o600)

    def test_a_run_keeps_to_the_budget_and_its_checks_are_not_held_by_its_primings(self):
        clock = FakeClock()
        pacer = P.Pacer(P.MemoryStore(), 6, clock, jitter=0)  # a small budget: the primings must queue
        times = []

        def pace(kind, until=None):
            ok = pacer.acquire(kind, until)
            if ok:
                times.append(clock.now())
            return ok
        c = FakeClient(clock, ttl=36000, took=1)
        events = []
        probe.run_probe(c, ages=[150, 300, 450], labels=["2.5m", "5m", "7.5m"], replicas=3, words=10, salt="t",
                        log=events.append, clock=clock, pace=pace)
        self.assertEqual(events[-1]["event"], "done")
        self.assertEqual(len(times), c.requests)
        self.assertLessEqual(P.busiest_minute(times), 6)
        self.assertFalse([e for e in events if e.get("event") == "check" and e["late"]])

    def test_devin_runs_get_the_budget_codex_and_smoke_runs_none(self):
        dv = night.command(night.ALL_STEPS["DV1"], "2099-01-01", launch_id="L", delay=0)
        self.assertEqual(dv[dv.index("--pace-rpm") + 1], "24")
        self.assertTrue(dv[dv.index("--pace-dir") + 1].endswith("night-2099-01-01/pacing"))
        self.assertNotIn("--pace-rpm", night.command(night.ALL_STEPS["CX1"], "2099-01-01", launch_id="L"))
        self.assertNotIn("--pace-rpm", night.command(night.ALL_STEPS["S3"], "2099-01-01"))
        a = probe.parser().parse_args(dv[2:])
        self.assertEqual(a.pace_rpm, 24)
        with mock.patch.dict(night.PACE, {}), mock.patch.object(night, "dry_run_go", lambda *a, **k: None):
            night.main(["--date", "2099-01-01", "--pace", "devin=12", "--dry-run", "devin"])
            dv = night.command(night.ALL_STEPS["DV1"], "2099-01-01", launch_id="L")
            self.assertEqual(dv[dv.index("--pace-rpm") + 1], "12")
        with self.assertRaises(SystemExit):
            night.main(["--date", "2099-01-01", "--pace", "devin=fast", "--dry-run", "devin"])

    def test_the_probe_s_start_line_records_the_budget(self):
        argv = night.command(night.ALL_STEPS["DV1"], "2099-01-01", launch_id="L")[2:]
        with redirect_stdout(StringIO()) as out:
            probe.main([*argv, "--dry-run"])
        start = json.loads(out.getvalue().splitlines()[0])
        self.assertEqual(start["pacing"], {"rpm": 24, "reserve_for_checks": 6})
        self.assertIn("paced: at most 24 devin requests a minute", out.getvalue())

    def test_the_dry_run_plans_the_time_with_pacing(self):
        out = []
        ends = night.plan_report(night.runs_of(["DV1,DV2,DV3"]), out=out.append)
        end, requests = ends["devin"]
        self.assertEqual(requests, 3 * 87)
        self.assertTrue(2 * 3600 < end < 3 * 3600, end)
        text = "\n".join(out)
        self.assertIn("paced at 24 a minute", text)
        self.assertIn("no check late", text)


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
                         [("prime", 0, None), ("check", None, False), ("prime", 1, None), ("check", None, True)])
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


# --- 4. the model ids, before the go ------------------------------------------------------------------------------

class ModelIds(unittest.TestCase):
    def test_dv12_is_deepseek_v4_pro_high_and_every_run_is_in_the_checked_lists(self):
        self.assertEqual(night.ALL_STEPS["DV12"]["model"], "deepseek-v4-pro-high")
        for s in night.ALL_STEPS.values():
            with self.subTest(run=s["id"]):
                self.assertIn(s["model"], M.checked(s["harness"]))
        self.assertNotIn("deepseek-v4-pro-low", M.checked("devin"))

    def test_an_unknown_id_is_refused_by_name_in_the_dry_run_and_the_go(self):
        def lister(client):
            return {"glm-5-3-low"} if client == "devin" else {"gpt-6.2-sol"}
        with mock.patch.object(night, "dry_run", side_effect=AssertionError("planned")), \
                self.assertRaisesRegex(SystemExit, r"DV1 \(claude-opus-5-5-low\)"):
            night.dry_run_go(["DV1,DV9"], "2099-01-01", out=lambda *_: None, lister=lister)
        with mock.patch.object(night, "guard"), mock.patch.object(night, "launch") as launch, \
                self.assertRaisesRegex(SystemExit, r"--go: refused: .*CX3 \(gpt-6.1-sol\)"):
            night.go_clients(["CX1,CX3"], "2099-01-01", popen=lambda *a, **k: None, out=lambda *_: None,
                             lister=lister)
        launch.assert_not_called()
        with mock.patch.dict(night.ALL_STEPS["DV12"], model="deepseek-v4-pro-low"), \
                self.assertRaisesRegex(SystemExit, r"DV12 \(deepseek-v4-pro-low\)"):
            night.check_ids([night.ALL_STEPS["DV12"]], "--dry-run", out=lambda *_: None)

    def test_the_dry_run_runs_no_client_to_list_and_the_go_reads_the_client_s_own(self):
        with mock.patch.dict(os.environ, {"GROUNDTRUTH_MODEL_LIST": ""}), \
                mock.patch.object(M, "codex_listed", side_effect=AssertionError("a client was run")), \
                mock.patch.object(M, "devin_listed", side_effect=AssertionError("a client was run")):
            for client in ("codex", "devin"):
                ids, src, own = M.known_ids(client, live=False)
                self.assertFalse(own)
                self.assertIn("checked list", src)
        with mock.patch.dict(os.environ, {"GROUNDTRUTH_MODEL_LIST": ""}), \
                mock.patch.object(M, "codex_listed", return_value={"gpt-6-luna"}):
            ids, _, own = M.known_ids("codex", live=True)
            self.assertEqual((ids, own), ({"gpt-6-luna"}, True))
        with mock.patch.dict(os.environ, {"GROUNDTRUTH_MODEL_LIST": ""}), \
                mock.patch.object(M, "devin_listed", side_effect=M.ListError("no Devin login")):
            ids, src, own = M.known_ids("devin", live=True)
            self.assertFalse(own)
            self.assertIn("no Devin login", src)
            self.assertIn("deepseek-v4-pro-high", ids)

    def test_codex_lists_offline_without_the_network(self):
        seen = {}

        def run(argv, **kw):
            seen.update(argv=argv, env=kw["env"])
            return SimpleNamespace(returncode=0, stdout=json.dumps({"models": [{"slug": "gpt-6-luna"},
                                                                               {"slug": "gpt-6.2-sol"}]}))
        with mock.patch.object(M.shutil, "which", return_value="/x/codex"), mock.patch.object(C, "CONFINED", True):
            self.assertEqual(M.codex_listed(run=run), {"gpt-6-luna", "gpt-6.2-sol"})
        self.assertIn("--bundled", seen["argv"])
        self.assertIn("(deny network*)", seen["argv"][2])
        self.assertNotEqual(seen["env"]["CODEX_HOME"], os.path.expanduser("~/.codex"))
        self.assertFalse(os.path.exists(seen["env"]["HOME"]))  # the throwaway folder is gone

    def test_devin_s_list_is_never_asked_without_its_login(self):
        tmp = scratch(self)
        os.chmod(tmp, 0o700)
        os.mkdir(os.path.join(tmp, "devin-cli"), 0o700)
        run = mock.Mock(side_effect=AssertionError("the client was run"))
        with mock.patch.object(C, "CONFINED", False), self.assertRaisesRegex(M.ListError, "no Devin login"):
            M.devin_listed(tmp, run=run)
        run.assert_not_called()

    def test_devin_s_json_list_read_flat_or_by_family(self):
        flat = [{"id": "glm-5-3-low", "label": "GLM 5.3 Low"}, {"id": "deepseek-v4-pro-high"}]
        family = {"families": [{"name": "DeepSeek", "models": [{"id": "deepseek-v4-pro", "levels": ["high", "max"]}]}]}
        self.assertTrue({"glm-5-3-low", "deepseek-v4-pro-high"} <= M.ids_in(flat))
        found = M.ids_in(family)
        self.assertIn("deepseek-v4-pro-high", found)
        self.assertNotIn("deepseek-v4-pro-low", found)


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
        self.assertIn("--pace-rpm", dv12)
        self.assertEqual(R2.mode(os.path.join(night.night_dir(DATE), "pacing")), 0o700)
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
