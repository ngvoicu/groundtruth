"""harness/probe.py: the loop against a fake client and a fake clock (no client is run, nothing is sent).

    python3 -m unittest discover -s test -p "test_*.py"
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "harness"))
import clients as C  # noqa: E402
import probe  # noqa: E402

SHARED, BLOCK = 18000, 7000  # the client's own prompt, and a sample's block


class FakeClock:
    def __init__(self):
        self.t = 1_000_000.0

    def now(self):
        return self.t

    def sleep(self, seconds):
        if seconds > 0:
            self.t += seconds


class FakeClient:
    """A client whose cache of a sample's block lives `ttl` seconds from the start of its priming. Every request
    takes `took` seconds. Hooks: fail(handle) for a check that fails, refuse_prime(n), calls(handle), ttls(n)."""

    def __init__(self, clock, ttl, took=5.0, cumulative=False):
        self.clock, self.ttl, self.took, self.cumulative = clock, ttl, took, cumulative
        self.primed, self.requests, self.resumes = {}, 0, []
        self.fail, self.refuse_prime, self.calls, self.write_ttl, self.prime_took = set(), {}, {}, {}, {}

    def start(self, prompt):
        n = self.requests
        self.requests += 1
        if n in self.refuse_prime:
            raise C.Refused(self.refuse_prime[n], "You've hit your usage limit")
        handle = f"s{n}"
        self.primed[handle] = self.clock.now()
        self.clock.t += self.prime_took.get(n, self.took)
        total = SHARED + (0 if prompt == probe.OK_PROMPT else BLOCK)
        u = {"total": total, "cached": SHARED if n else 0, "write": total - SHARED, "calls": 1}
        if n in self.write_ttl:
            u["write_" + self.write_ttl[n]] = BLOCK
        return handle, u

    def resume(self, handle, prompt):
        self.requests += 1
        self.resumes.append(handle)
        if handle in self.fail:
            raise C.ClientError("connection reset")
        warm = self.clock.now() - self.primed[handle] < self.ttl
        self.clock.t += self.took
        u = {"total": SHARED + BLOCK + 20, "cached": SHARED + (BLOCK if warm else 0), "write": 20 if warm else BLOCK + 20,
             "calls": self.calls.get(handle, 1)}
        return u


def go(client, clock, ages=("2.5m", "5m", "7.5m"), replicas=1):
    events = []
    secs = [probe.parse_age(a) for a in ages]
    reason = probe.run_probe(client, ages=secs, labels=list(ages), replicas=replicas, words=10, salt="t",
                             log=events.append, clock=clock)
    return reason, events


def checks(events):
    return [(e["age"], e["warm"]) for e in events if e["event"] == "check"]


class Loop(unittest.TestCase):
    def test_a_cache_of_6_minutes_gives_warm_warm_cold(self):
        clock = FakeClock()
        reason, ev = go(FakeClient(clock, ttl=360), clock)
        self.assertIsNone(reason)
        self.assertEqual(checks(ev), [("control", True), ("2.5m", True), ("5m", True), ("7.5m", False)])
        self.assertEqual(ev[-1]["event"], "done")

    def test_the_control_comes_first_and_a_miss_ends_after_three_requests(self):
        clock = FakeClock()
        c = FakeClient(clock, ttl=10)
        reason, ev = go(c, clock)
        self.assertEqual(reason, "no-observable-cache")
        self.assertEqual(c.requests, 3)  # baseline, the control's priming, its check
        self.assertEqual([e["event"] for e in ev], ["baseline", "prime", "check", "stop"])
        self.assertEqual(ev[-1]["reason"], "no-observable-cache")

    def test_the_control_is_checked_before_any_other_priming(self):
        clock = FakeClock()
        reason, ev = go(FakeClient(clock, ttl=3600), clock)
        kinds = [(e["event"], e.get("age")) for e in ev]
        self.assertEqual(kinds[:3], [("baseline", None), ("prime", "control"), ("check", "control")])
        self.assertEqual(ev[2]["ageSec"], 30.0)

    def test_a_failed_check_is_not_sent_again(self):
        clock = FakeClock()
        c = FakeClient(clock, ttl=3600)
        c.fail.add("s5")  # request numbers: baseline 0, control 1, its check 2, then 7.5m 3, 5m 4, 2.5m 5
        reason, ev = go(c, clock)
        self.assertIsNone(reason)
        self.assertEqual(c.resumes.count("s5"), 1)
        failed = [e for e in ev if e["event"] == "check-failed"]
        self.assertEqual([(e["age"], e["handle"]) for e in failed], [("2.5m", "s5")])
        self.assertEqual([a for a, _ in checks(ev)], ["control", "5m", "7.5m"])

    def test_a_quota_refusal_while_priming_ends_the_run_unchecked(self):
        clock = FakeClock()
        c = FakeClient(clock, ttl=3600)
        c.refuse_prime[4] = "quota"  # after the control's check (request 3), the second sample's priming
        reason, ev = go(c, clock)
        self.assertEqual(reason, "quota")
        self.assertEqual(checks(ev), [("control", True)])  # the sample primed before the refusal is not checked
        self.assertEqual(ev[-1]["event"], "stop")
        self.assertEqual(c.requests, 5)
        self.assertEqual(len([e for e in ev if e["event"] == "retry"]), 0)

    def test_a_quota_refusal_on_a_check_ends_the_run(self):
        clock = FakeClock()
        c = FakeClient(clock, ttl=3600)
        orig = c.resume

        def resume(handle, prompt):
            if handle == "s3":
                c.requests += 1
                raise C.Refused("quota", "usage limit")
            return orig(handle, prompt)
        c.resume = resume
        reason, ev = go(c, clock)
        self.assertEqual(reason, "quota")
        self.assertNotIn("7.5m", [a for a, _ in checks(ev)])

    def test_a_two_request_check_is_not_counted(self):
        clock = FakeClock()
        c = FakeClient(clock, ttl=3600)
        c.calls["s4"] = 2
        reason, ev = go(c, clock)
        invalid = [e for e in ev if e["event"] == "check-invalid"]
        self.assertEqual([e["age"] for e in invalid], ["5m"])
        self.assertNotIn("5m", [a for a, _ in checks(ev)])

    def test_a_check_with_no_count_of_requests_is_not_counted(self):
        clock = FakeClock()
        c = FakeClient(clock, ttl=3600)
        c.calls["s4"] = None
        reason, ev = go(c, clock)
        self.assertEqual([e["age"] for e in ev if e["event"] == "check-invalid"], ["5m"])

    def test_a_late_check_is_flagged(self):
        clock = FakeClock()
        c = FakeClient(clock, ttl=36000)
        c.prime_took[4] = 600  # the 2.5m sample's priming blocks the loop for 10 minutes; the 5m check waits behind it
        reason, ev = go(c, clock, ages=("2.5m", "5m"))
        late = {e["age"]: e["late"] for e in ev if e["event"] == "check"}
        self.assertTrue(late["5m"])
        self.assertTrue(late["2.5m"])
        self.assertFalse(late["control"])

    def test_ages_count_from_the_start_of_the_priming(self):
        clock = FakeClock()
        c = FakeClient(clock, ttl=3600, took=20.0)
        reason, ev = go(c, clock, ages=("2.5m",))
        two = next(e for e in ev if e["event"] == "check" and e["age"] == "2.5m")
        self.assertEqual(two["realAgeSec"], 150)

    def test_a_change_of_written_lifetime_ends_the_run(self):
        clock = FakeClock()
        c = FakeClient(clock, ttl=3600)
        c.write_ttl.update({1: "1h", 3: "1h", 4: "5m"})
        reason, ev = go(c, clock)
        self.assertEqual(reason, "tier-changed")

    def test_a_cumulative_client_is_read_as_the_difference(self):
        clock = FakeClock()
        c = FakeClient(clock, ttl=3600, cumulative=True)
        orig = c.resume

        def resume(handle, prompt):  # Codex: the thread's running total, the priming included
            u = orig(handle, prompt)
            return {**u, "total": u["total"] + SHARED + BLOCK, "cached": u["cached"] + SHARED, "write": u["write"] + BLOCK}
        c.resume = resume
        reason, ev = go(c, clock, ages=("2.5m",))
        control = next(e for e in ev if e["event"] == "check" and e["age"] == "control")
        self.assertTrue(control["warm"])
        self.assertEqual(control["usage"]["cached"], SHARED + BLOCK)
        self.assertEqual(control["usage"]["raw"]["cached"], 2 * SHARED + BLOCK)


class Main(unittest.TestCase):
    def test_an_own_client_needs_its_state_folder(self):
        for harness in ("claude", "codex", "devin", "muse"):
            with self.subTest(harness=harness), self.assertRaisesRegex(SystemExit, "client-home"):
                probe.main(["--harness", harness, "--model", "m", "--label", "X", "--out", "/nonexistent/out", "--client-home", ""])

    def test_the_dry_run_records_the_isolation_and_sends_nothing(self):
        import io
        import json
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            probe.main(["--harness", "claude", "--model", "m", "--label", "X", "--out", "/nonexistent/out", "--dry-run",
                        "--client-env", "CLAUDE_CODE_PROMPT_CACHE_TTL=5m"])
        start = json.loads(buf.getvalue().splitlines()[0])
        self.assertEqual(start["isolation"], {"home": "dedicated", "work": "temporary"})
        self.assertEqual(start["client_env"], {"CLAUDE_CODE_PROMPT_CACHE_TTL": "5m"})
        self.assertNotIn("/", "".join(start["command"]["prime"]).replace("<", "").replace(">", ""))
        self.assertIn("nothing sent", buf.getvalue())
        self.assertFalse(os.path.exists("/nonexistent/out"))


class Fillers(unittest.TestCase):
    def test_each_sample_has_its_own_block(self):
        for filler in probe.FILLERS:
            a, b = probe.prime_prompt("x-1", 600, filler), probe.prime_prompt("x-2", 600, filler)
            self.assertNotEqual(a, b)
            self.assertNotIn("x-2", a)
        self.assertIn("1. Entry 1 of list x-1", probe.prime_prompt("x-1", 600, "list"))

    def test_custom_ages_join_the_start_of_the_ladder(self):
        ages, labels = probe.ages_of("std", "10m,15m")
        self.assertEqual(labels, ["2.5m", "5m", "7.5m", "10m", "15m"])


if __name__ == "__main__":
    unittest.main()
