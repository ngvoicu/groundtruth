"""harness/weekly.py (step G3) and harness/asks.py (step G4): the unattended night with fake clients, a fake world and
the real ledger in a temporary folder. Nothing is sent, no client is run, no notification is shown.

    python3 -m unittest discover -s test -p "test_*.py"
"""
import datetime as dt
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "harness"))
import asks as A  # noqa: E402
import ledger as L  # noqa: E402
import plan as P  # noqa: E402
import weekly as W  # noqa: E402

DATE = "2026-11-30"


def bucharest(day, hh, mm=0):
    return W.at(DATE, day, dt.time(hh, mm))


def entry(provider, model, release="2026-11-20", price_in=0.1, price_out=0.4, context=None):
    return {"provider": provider, "model": model, "type": "chat", "release_date": release, "canonical_id": None,
            "price_in": price_in, "price_out": price_out, "price_write": None, "context": context, "input": None,
            "cache": {"documented": None, "status": None, "pi": None, "pi_standing": None},
            "window": {"documented": context, "status": None, "pi": None, "pi_standing": None},
            "output": {"documented": None, "status": None, "pi": None, "pi_standing": None, "unavailable": True}}


def fixture_site(codex=8, devin=3, keys=(("openrouter", "a/cheap", 0.1), ("openrouter", "a/cheap2", 0.2))):
    entries = [entry("openai-codex", f"gpt-c{n}", release=f"2026-11-{10 + n:02d}") for n in range(codex)]
    entries += [entry("devin", f"m-{n}", release=f"2026-11-{10 + n:02d}") for n in range(devin)]
    entries += [entry(p, m, price_in=price) for p_route, m, price in keys
                for p in [P.ROUTES[p_route]["provider"]]]
    return {"dataset": "fixture", "entries": {f"{e['provider']}/{e['model']}": e for e in entries}}


class Fake:
    """The world, faked: a clock that moves only when the night sleeps; clients whose runs end as told."""

    def __init__(self, now, site, logins=None, keys=None, key_status=None, smoke=None, outcomes=None, windows=None,
                 spend=None):
        self.t, self._site = now, site
        self.calls, self.notes, self.polls = [], [], {}
        self.logins = {k: list(v) for k, v in (logins or {}).items()}
        self.keys = keys if keys is not None else {r: "k-" + r for r in P.KEY_ROUTES}
        self.key_status = key_status or {}
        self.smoke_ = smoke or {}
        self.outcomes = outcomes or {}
        self.windows_ = windows or {}
        self.spend = spend or {}
        self.locked = set()

    def now(self):
        return self.t

    def sleep(self, s):
        self.t += dt.timedelta(seconds=s)

    def notify(self, text):
        self.notes.append(text)

    def keep_awake(self):
        self.calls.append(("keep_awake",))

    def site(self):
        self.calls.append(("site",))
        return self._site

    def untouched(self, date, mode):
        self.calls.append(("untouched", mode))
        return None

    def login_status(self, part):
        self.calls.append(("login_status", part))
        seq = self.logins.get(part) or [None]
        return seq.pop(0) if len(seq) > 1 else seq[0]

    def read_keys(self):
        self.calls.append(("read_keys",))
        return self.keys

    def key_check(self, route, key):
        self.calls.append(("key_check", route))
        return self.key_status.get(route, 200)

    def smoke(self, part, date):
        self.calls.append(("smoke", part))
        return self.smoke_.get(part, [])

    def lock_part(self, date, part, launch_id):
        if part in self.locked:
            return None
        self.locked.add(part)
        return {"runs": {}}

    def start(self, run, date, launch_id, lock, key=None):
        self.calls.append(("start", run["label"]))
        return run["label"]

    def poll(self, run):
        n = self.polls[run["label"]] = self.polls.get(run["label"], 0) + 1
        after, res = self.outcomes.get(run["label"], (1, {"outcome": "done"}))
        if after is None or n < after:
            return None
        res = dict(res)
        if run["part"] == "keys":
            res.setdefault("usd", self.spend.get(run["label"], 0.05))
        return res

    def stop(self, run, date):
        self.calls.append(("stop", run["label"]))

    def stop_part(self, date, part):
        self.calls.append(("stop_part", part))

    def price(self, v):
        return None

    def window(self, v, key, date):
        self.calls.append(("window", v["label"]))
        return self.windows_.get(v["key"], {"outcome": "refused as expected", "status": 400})

    def audit(self, date):
        self.calls.append(("audit",))
        return True

    def new_value(self, run):
        return "-"

    def requests(self, run):
        return 0

    def result_file(self, run, date):
        return f"results/night-{date}/{run['label']}.json"

    def started(self, prefix=""):
        return [c[1] for c in self.calls if c[0] == "start" and c[1].startswith(prefix)]


class NightCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = os.path.join(self.tmp.name, "repo")
        self.home = os.path.join(self.tmp.name, "G")
        os.makedirs(self.root)
        os.makedirs(self.home, mode=0o700)

    def tearDown(self):
        self.tmp.cleanup()

    def night(self, fake, date=DATE, **kw):
        lines = []
        n = W.Night(date, fake, self.home, out=lines.append, root=self.root, **kw)
        n.lines = lines
        n.state_out = n.run()
        return n

    def asks(self, kind=None):
        return A.Asks(os.path.join(self.home, "asks")).open_of(kind)

    def report(self, date=DATE):
        with open(os.path.join(self.root, "results", f"night-{date}", "REPORT.md")) as f:
            return f.read()


class Caps(NightCase):
    def test_a_login_s_part_never_starts_a_seventh_run(self):
        fake = Fake(bucharest(0, 23), fixture_site(codex=9))
        n = self.night(fake, only=["codex"])
        self.assertEqual(len(fake.started("cx-")), 6)
        self.assertEqual(n.parts["codex"]["planned"], 6)
        self.assertEqual(len(n.left["codex"]), 3)
        self.assertIn("3 planned values were left for next week", self.report())

    def test_long_runs_are_started_first_and_are_among_the_six(self):
        site = fixture_site(codex=7)
        with open(os.path.join(self.root, "observed.json"), "w") as f:
            json.dump({"client_kinds": {"cliproxyapi": "proxy"}, "cache": [
                {"route": "codex-subscription", "model": "gpt-c1", "client": "cliproxyapi", "date": "2026-11-20",
                 "all_warm_through_s": 7200}]}, f)
        fake = Fake(bucharest(0, 23), site)
        self.night(fake, only=["codex"])
        self.assertEqual(fake.started("cx-")[0], "cx-gpt-c1")
        self.assertEqual(len(fake.started("cx-")), 6)

    def test_the_api_key_part_never_starts_a_run_that_does_not_fit_the_money_left(self):
        keys = tuple(("openrouter", f"a/m{n}", 0.5) for n in range(8))  # worst case $0.37 each
        fake = Fake(bucharest(0, 23), fixture_site(0, 0, keys), outcomes={})
        n = self.night(fake, only=["keys"], week_cap=1.0)
        est = P.estimate_usd(entry("openrouter", "x", price_in=0.5, price_out=0.4))
        started = fake.started("or-a-m")
        caches = [s for s in started]
        self.assertTrue(caches)
        self.assertLessEqual(len(caches) * est, 1.0 + 1e-9)
        self.assertEqual(len(self.asks("money-spent")), 1)
        self.assertTrue(n.parts["keys"]["status"].startswith("stopped"))
        led = L.Ledger(os.path.join(self.home, "ledger"), DATE, 1.0)
        self.assertLessEqual(led.used(), 1.0)

    def test_a_run_over_two_dollars_is_not_started_and_asks_the_rest_goes_on(self):
        keys = (("openrouter", "a/dear", 10.0), ("openrouter", "a/cheap", 0.1))
        fake = Fake(bucharest(0, 23), fixture_site(0, 0, keys))
        self.night(fake, only=["keys"])
        self.assertNotIn("or-a-dear", fake.started())
        self.assertIn("or-a-cheap", fake.started())
        subjects = {a["subject"] for a in self.asks("run-over-cap")}
        self.assertEqual(subjects, {"openrouter|a/dear|cache"})  # a window check is never held to the run ceiling
        self.assertEqual([a["subject"] for a in self.asks("window-over-week")], ["openrouter|a/dear|window"])
        ask = next(a for a in self.asks("run-over-cap") if a["subject"] == "openrouter|a/dear|cache")
        self.assertIn("--value openrouter:a/dear:cache --run-cap", ask["command"])

    def test_the_week_s_money_reached_during_the_night_stops_the_api_key_part(self):
        keys = tuple(("openrouter", f"a/m{n}", 0.1) for n in range(4))
        spend = {"or-a-m0": 10.5, "or-a-m1": 0.2}
        fake = Fake(bucharest(0, 23), fixture_site(0, 0, keys), spend=spend,
                    outcomes={"or-a-m0": (1, {"outcome": "done"}), "or-a-m1": (5, {"outcome": "done"}),
                              "or-a-m2": (5, {"outcome": "done"}), "or-a-m3": (5, {"outcome": "done"})})
        n = self.night(fake, only=["keys"])
        self.assertEqual(len(self.asks("money-spent")), 1)
        self.assertTrue(any(c == ("stop", "or-a-m1") for c in fake.calls), fake.calls)
        self.assertTrue(n.parts["keys"]["status"].startswith("stopped"))

    def test_the_provider_s_own_limit_402_stops_the_api_key_part(self):
        keys = (("openrouter", "a/m0", 0.1), ("openrouter", "a/m1", 0.1))
        fake = Fake(bucharest(0, 23), fixture_site(0, 0, keys),
                    outcomes={"or-a-m0": (1, {"outcome": "money", "status": 402}),
                              "or-a-m1": (None, {"outcome": "done"})})
        self.night(fake, only=["keys"])
        self.assertEqual(len(self.asks("money-spent")), 1)
        self.assertIn(("stop", "or-a-m1"), fake.calls)

    def test_a_night_with_nothing_to_measure_ends_early_and_never_fills_a_cap(self):
        fake = Fake(bucharest(0, 23), fixture_site(0, 0, ()))
        n = self.night(fake)
        self.assertEqual(fake.started(), [])
        self.assertEqual({p["status"] for p in n.parts.values()}, {"nothing to measure"})
        self.assertNotIn(("smoke", "codex"), fake.calls)


class WindowChecks(NightCase):
    """The owner's decision of 2026-11-22, "A": a window check is not held to the $2 a run; its worst case (answered
    instead of refused) must fit what the week has left, newest model first; a refused one is charged $0."""

    def site(self, *checks):
        # A window check of 1.2 million words: its worst case is 1.2 x the input price.
        return fixture_site(0, 0, ()) | {"entries": {f"openrouter/{m}": entry("openrouter", m, release=r, price_in=p)
                                                     for m, r, p in checks}}

    def run_windows(self, checks, **kw):
        fake = Fake(bucharest(0, 23), self.site(*checks), **kw)
        self.night(fake, only=["keys"], values={f"openrouter|{m}|window" for m, _, _ in checks})
        return fake, [c[1] for c in fake.calls if c[0] == "window"]

    def test_a_check_of_five_dollars_is_sent_while_the_week_has_ten_left(self):
        fake, sent = self.run_windows([("a/five", "2026-11-20", 5 / 1.2)])
        self.assertEqual(sent, ["or-a-five-window"])
        self.assertEqual(self.asks(), [])

    def test_a_check_of_twelve_dollars_is_never_sent(self):
        fake, sent = self.run_windows([("a/twelve", "2026-11-20", 10.0)])
        self.assertEqual(sent, [])
        ask = self.asks("window-over-week")[0]
        self.assertIn("worst case $12.00 does not fit the $10.00 left this week", ask["first_line"])
        self.assertIn("--value openrouter:a/twelve:window --week-cap", ask["command"])
        self.assertEqual(self.asks("run-over-cap"), [])

    def test_two_that_together_pass_ten_only_the_first_newest_is_sent(self):
        fake, sent = self.run_windows([("a/older", "2026-11-10", 5 / 1.2), ("a/newer", "2026-11-20", 6 / 1.2)])
        self.assertEqual(sent, ["or-a-newer-window"])
        ask = self.asks("window-over-week")[0]
        self.assertEqual(ask["subject"], "openrouter|a/older|window")
        self.assertIn("does not fit the $4.00 left", ask["first_line"])

    def test_a_refused_check_is_charged_nothing_an_answered_one_what_it_cost(self):
        self.run_windows([("a/five", "2026-11-20", 5 / 1.2)])
        led = L.Ledger(os.path.join(self.home, "ledger"), DATE)
        self.assertEqual(led.used(), 0.0)
        self.assertEqual(led.reserved(), 0.0)
        self.assertEqual(led.left(), 10.0)
        spent = [r for r in led.rows if r["kind"] == "spent"]
        self.assertEqual([(r["label"], r["usd"]) for r in spent], [("or-a-five-window", 0.0)])
        self.tearDown()
        self.setUp()
        self.run_windows([("a/five", "2026-11-20", 5 / 1.2)],
                         windows={"openrouter|a/five|window": {"outcome": "answered", "status": 200, "usd": 4.2}})
        self.assertAlmostEqual(L.Ledger(os.path.join(self.home, "ledger"), DATE).used(), 4.2)

    def test_the_worst_case_of_a_sent_check_holds_room_for_the_night_s_cache_runs(self):
        site = self.site(("a/five", "2026-11-20", 7 / 1.2))
        site["entries"]["openrouter/a/cheap"] = entry("openrouter", "a/cheap", release="2026-11-01", price_in=0.1)
        fake = Fake(bucharest(0, 23), site)
        self.night(fake, only=["keys"], week_cap=7.01,
                   values={"openrouter|a/five|window", "openrouter|a/cheap|cache"})
        self.assertIn(("window", "or-a-five-window"), fake.calls)
        self.assertNotIn("or-a-cheap", fake.started())  # $7 of $7.01 held by the check: the run does not fit
        self.assertEqual(len(self.asks("money-spent")), 1)

    def test_a_cache_run_keeps_the_two_dollar_ceiling(self):
        self.assertEqual(L.Ledger(self.home, DATE, dry=True).admit("x", "openrouter", "m", 2.5), "over-run-cap")
        self.assertEqual(L.Ledger(self.home, DATE, dry=True).admit("x", "openrouter", "m", 2.5, window=True), "ok")


class TheAsks(NightCase):
    def test_an_expired_login_stops_only_its_part(self):
        fake = Fake(bucharest(0, 23), fixture_site(codex=2, devin=2), logins={"devin": ["expired"]})
        n = self.night(fake)
        self.assertEqual(fake.started("dv-"), [])
        self.assertEqual(len(fake.started("cx-")), 2)
        self.assertTrue(fake.started("or-"))
        self.assertEqual(n.parts["devin"]["status"], "not started: login expired")
        ask = self.asks("login-expired")[0]
        self.assertEqual(ask["command"], f"python3 harness/night.py --date {DATE} login devin   # 2 minutes, a browser "
                                         "opens")
        self.assertIn("Log in again to devin", fake.notes[0])

    def test_a_burst_of_asks_is_one_notification(self):
        keys = tuple(("openrouter", f"a/dear{n}", 10.0) for n in range(3))
        fake = Fake(bucharest(0, 23), fixture_site(0, 0, keys))
        self.night(fake, only=["keys"])
        self.assertEqual(len(self.asks("run-over-cap")), 3)
        self.assertEqual(len(self.asks("window-over-week")), 3)
        self.assertTrue(fake.notes[0].startswith("6 new asks; the first: "), fake.notes)  # the money's pass, at once
        self.assertEqual(len(fake.notes), 2)
        self.assertIn("6 new", fake.notes[-1])

    def test_a_login_that_expires_between_two_runs(self):
        fake = Fake(bucharest(0, 23), fixture_site(codex=0, devin=3), logins={"devin": [None, "expired"]})
        n = self.night(fake, only=["devin"])
        self.assertEqual(len(fake.started("dv-")), 1)
        self.assertEqual(n.parts["devin"]["status"], "stopped: login expired")
        self.assertIn("between two runs", self.asks("login-expired")[0]["happened"])

    def test_a_login_refused_during_a_run(self):
        fake = Fake(bucharest(0, 23), fixture_site(codex=0, devin=2),
                    outcomes={"dv-m-0-low": (1, {"outcome": "login"})})
        self.night(fake, only=["devin"])
        self.assertEqual(len(self.asks("login-expired")), 1)
        self.assertIn(("stop_part", "devin"), fake.calls)

    def test_a_refused_key_stops_only_its_route(self):
        keys = (("openrouter", "a/x", 0.1), ("openai-api", "gpt-k", 0.1))
        fake = Fake(bucharest(0, 23), fixture_site(0, 0, keys), key_status={"openai-api": 401})
        self.night(fake, only=["keys"])
        self.assertIn("or-a-x", fake.started())
        self.assertNotIn("oa-gpt-k", fake.started())
        ask = self.asks("key-refused")[0]
        self.assertEqual(ask["subject"], "openai-api")
        self.assertIn("OPENAI_API_KEY", ask["happened"])
        self.assertIn("weekly.py check keys", ask["command"])

    def test_a_missing_key_is_an_ask_too(self):
        keys = (("anthropic-api", "claude-k", 0.1),)
        fake = Fake(bucharest(0, 23), fixture_site(0, 0, keys), keys={})
        self.night(fake, only=["keys"])
        self.assertEqual(fake.started(), [])
        self.assertIn("no key", self.asks("key-refused")[0]["first_line"])

    def test_a_plan_s_limit_reached(self):
        fake = Fake(bucharest(0, 23), fixture_site(codex=4, devin=0),
                    outcomes={"cx-gpt-c3": (1, {"outcome": "quota"})})
        n = self.night(fake, only=["codex"])
        ask = self.asks("plan-limit")[0]
        self.assertIn("after 4 of 4 runs", ask["first_line"])
        self.assertIn("--only codex", ask["command"])
        self.assertIn(("stop_part", "codex"), fake.calls)
        self.assertTrue(n.parts["codex"]["status"].startswith("stopped"))

    def test_a_vendor_refusing_twice_in_a_row_stops_the_route_once_does_not(self):
        keys = tuple(("openrouter", f"a/m{n}", 0.1) for n in range(3)) + (("openai-api", "gpt-k", 0.1),)
        fake = Fake(bucharest(0, 23), fixture_site(0, 0, keys),
                    outcomes={"or-a-m0": (1, {"outcome": "refused", "kind": "HTTP 400"}),
                              "or-a-m1": (2, {"outcome": "refused", "kind": "HTTP 400"}),
                              "or-a-m2": (3, {"outcome": "done"})})
        with mock_parallel(1):
            self.night(fake, only=["keys"])
        ask = self.asks("vendor-refuses")[0]
        self.assertEqual(ask["subject"], "openrouter")
        self.assertNotIn("or-a-m2", fake.started())
        self.assertIn("oa-gpt-k", fake.started())
        once = Fake(bucharest(0, 23), fixture_site(0, 0, keys[:2]),
                    outcomes={"or-a-m0": (1, {"outcome": "refused", "kind": "HTTP 400"})})
        self.tearDown()
        self.setUp()
        self.night(once, only=["keys"])
        self.assertEqual(self.asks("vendor-refuses"), [])

    def test_a_window_request_answered_ends_the_window_list(self):
        keys = (("openrouter", "a/w1", 0.1), ("openrouter", "a/w2", 0.2))
        fake = Fake(bucharest(0, 23), fixture_site(0, 0, keys),
                    windows={"openrouter|a/w1|window": {"outcome": "answered", "status": 200, "usd": 0.12}})
        self.night(fake, only=["keys"])
        windows = [c[1] for c in fake.calls if c[0] == "window"]
        self.assertEqual(windows, ["or-a-w1-window"])
        ask = self.asks("window-answered")[0]
        self.assertIn("$0.12", ask["first_line"])
        led = L.Ledger(os.path.join(self.home, "ledger"), DATE)
        self.assertAlmostEqual(led.by_route()["openrouter"], 0.12 + 0.1, places=6)  # the window and two cache runs

    def test_discovery_stale_asks_and_stops_nothing(self):
        with open(os.path.join(self.root, "listed.json"), "w") as f:
            json.dump({"providers": {"devin": {"date": "2026-11-25", "models": ["m-0"]},
                                     "openai-codex": {"date": "2026-11-29", "models": ["gpt-c0"]}}}, f)
        fake = Fake(bucharest(0, 23), fixture_site(codex=1, devin=1))
        n = self.night(fake)
        self.assertEqual([a["subject"] for a in self.asks("discovery-stale")], ["devin"])
        self.assertEqual(n.parts["devin"]["status"], "done")

    def test_the_night_after_three_does_not_start_and_asks(self):
        fake = Fake(bucharest(1, 3, 5), fixture_site())
        self.night(fake)
        self.assertEqual(fake.started(), [])
        self.assertNotIn(("site",), fake.calls)
        with open(os.path.join(self.home, f"night-{DATE}", "state.json")) as f:
            state = json.load(f)
        self.assertEqual((state["started"], state["reason"]), (False, "too late"))
        ask = self.asks("night-not-started")[0]
        self.assertEqual(ask["command"], f"python3 harness/weekly.py --date {DATE} --go night   # starts it by hand "
                                         "(a second start of a night is refused)")
        self.assertIn("Tue", ask["happened"])

    def test_a_start_after_one_starts_no_long_run(self):
        with open(os.path.join(self.root, "observed.json"), "w") as f:
            json.dump({"client_kinds": {"cliproxyapi": "proxy"}, "cache": [
                {"route": "codex-subscription", "model": "gpt-c1", "client": "cliproxyapi", "date": "2026-11-20",
                 "all_warm_through_s": 7200}]}, f)
        fake = Fake(bucharest(1, 1, 30), fixture_site(codex=3))
        n = self.night(fake, only=["codex"])
        self.assertNotIn("cx-gpt-c1", fake.started())
        self.assertEqual(len(fake.started("cx-")), 2)
        self.assertTrue(any("no `long` run" in line for line in n.lines))

    def test_an_unsteady_value_asks(self):
        with open(os.path.join(self.root, "observed.json"), "w") as f:
            json.dump({"client_kinds": {"devin-cli": "own_client"}, "cache": [
                {"route": "devin", "model": "m-0", "client": "devin-cli", "date": f"2026-11-0{n}",
                 "all_warm_through_s": v} for n, v in ((1, 150), (2, 300), (3, 900))]}, f)
        fake = Fake(bucharest(0, 23), fixture_site(codex=0, devin=1))
        self.night(fake, only=["devin"])
        ask = self.asks("unsteady-value")[0]
        self.assertIn("150, 300, 900", ask["happened"])

    def test_a_failed_smoke_run_stops_its_client_s_part(self):
        fake = Fake(bucharest(0, 23), fixture_site(codex=2, devin=1), smoke={"codex": ["smoke-codex: no results"]})
        n = self.night(fake, only=["codex", "devin"])
        self.assertEqual(fake.started("cx-"), [])
        self.assertTrue(fake.started("dv-"))
        self.assertEqual(n.parts["codex"]["status"], "not started: smoke failed")
        self.assertEqual(len(self.asks("smoke-failed")), 1)

    def test_a_run_still_alive_at_the_end_gets_its_stop_mark(self):
        fake = Fake(bucharest(0, 23), fixture_site(codex=1, devin=0), outcomes={"cx-gpt-c0": (None, {})})
        n = self.night(fake, only=["codex"])
        self.assertIn(("stop", "cx-gpt-c0"), fake.calls)
        self.assertGreaterEqual(fake.t, bucharest(1, 11, 30))
        self.assertLess(fake.t, bucharest(1, 11, 32))
        self.assertEqual(n.started_runs[0]["outcome"], "stopped at the deadline")


class Night(NightCase):
    def test_dry_run_sends_nothing_and_writes_nothing(self):
        fake = Fake(bucharest(0, 23), fixture_site(codex=8, devin=2,
                                                   keys=(("openrouter", "a/cheap", 0.1), ("openrouter", "a/dear", 9))))
        n = self.night(fake, dry=True)
        self.assertEqual({c[0] for c in fake.calls}, {"site"})
        self.assertEqual(fake.notes, [])
        self.assertEqual(os.listdir(self.home), [])
        self.assertEqual(os.listdir(self.root), [])
        text = n.state_out["dry_report"]
        self.assertIn("## codex: 6 of at most 6 cache runs", text)
        self.assertIn("Left for later Mondays by the cap", text)
        self.assertIn("`a/cheap`", text)
        self.assertIn("a/dear` cache: worst case $2.35, above the run ceiling", text)
        self.assertIn("Nothing was sent", text)

    def test_a_second_start_of_the_same_night_is_refused(self):
        self.night(Fake(bucharest(0, 23), fixture_site(codex=1, devin=0)), only=["codex"])
        with self.assertRaises(SystemExit) as e:
            self.night(Fake(bucharest(0, 23, 5), fixture_site(codex=1, devin=0)), only=["codex"])
        self.assertIn("a second start of the same night is refused", str(e.exception))

    def test_the_end_writes_the_report_the_runs_and_the_state_and_notifies_once(self):
        fake = Fake(bucharest(0, 23), fixture_site(codex=2, devin=1))
        self.night(fake)
        report = self.report()
        self.assertTrue(report.startswith(f"# The night of {DATE}\n\n## Open asks\n\nNone."))
        for part in ("codex", "devin", "keys"):
            self.assertIn(f"| {part} | done |", report)
        with open(os.path.join(self.root, "results", f"night-{DATE}", "runs.json")) as f:
            runs = json.load(f)["runs"]
        self.assertEqual({r["route"] for r in runs}, {"codex-subscription", "devin", "openrouter"})
        self.assertTrue(os.path.exists(os.path.join(self.home, f"night-{DATE}", "state.json")))
        self.assertTrue(os.path.exists(os.path.join(self.root, "results", f"night-{DATE}", "PLAN.md")))
        self.assertEqual(len(fake.notes), 1)
        self.assertIn(("untouched", "save"), fake.calls)
        self.assertIn(("untouched", "report"), fake.calls)
        self.assertIn(("audit",), fake.calls)
        self.assertNotIn(self.home, report)

    def test_the_night_date(self):
        self.assertEqual(W.night_date(bucharest(0, 23)), DATE)
        self.assertEqual(W.night_date(bucharest(1, 2)), DATE)
        self.assertIsNone(W.night_date(bucharest(1, 13)))
        self.assertIsNone(W.night_date(bucharest(2, 1)))

    def test_devin_ids_carry_their_effort(self):
        self.assertEqual(W.devin_model("nemotron-3-5-super"), "nemotron-3-5-super-none")
        self.assertEqual(W.devin_model("swe-2"), "swe-2-medium")
        self.assertEqual(W.devin_model("new-model"), "new-model-low")
        self.assertEqual(W.devin_model("x", ["medium", "high"]), "x-medium")

    def test_the_first_night_s_launch_ids_and_locks_are_reused(self):
        # A login part's runs are harness/probe.py's, under the first night's lock and stop mark: night.py status and
        # stop work for the weekly night too, and a run looks for the mark before each client call.
        import probe
        self.assertTrue(probe.LAUNCH_ID.fullmatch(f"{DATE}-codex-0123456789ab"))
        self.assertTrue(probe.LAUNCH_ID.fullmatch(f"{DATE}-devin-0123456789ab"))


class mock_parallel:
    def __init__(self, n):
        self.n = n

    def __enter__(self):
        self.old, W.API_PARALLEL = W.API_PARALLEL, self.n

    def __exit__(self, *a):
        W.API_PARALLEL = self.old


class AsksOverNights(NightCase):
    def test_every_row_of_the_table_gives_an_ask_with_its_exact_command(self):
        facts = {"part": "devin", "date": DATE, "route": "openrouter", "variable": "OPENROUTER_API_KEY",
                 "status": "HTTP 401", "ran": 2, "planned": 6, "spent": 10.0, "cap": 10.0, "left_unmeasured": 3,
                 "model": "a/x", "quantity": "cache", "estimate": 2.5, "refusal": "HTTP 400", "usd": 3.0,
                 "words": 1200000, "provider": "devin", "days": 4, "reason": "late", "values": [1, 2, 3],
                 "problems": ["x"], "left": 4.0}
        asks = A.Asks(os.path.join(self.home, "asks"), today=DATE)
        self.assertEqual(len(A.TABLE_ROWS), 10)
        for kind in A.KINDS:
            ask = asks.open(kind, f"s-{kind}", **facts)
            self.assertTrue(ask["first_line"] and ask["command"] and ask["happened"] and ask["not_done"], kind)
            with open(os.path.join(self.home, "asks", "open", ask["id"] + ".md")) as f:
                text = f.read()
            self.assertIn(ask["command"], text)
            self.assertEqual(oct(os.stat(os.path.join(self.home, "asks", "open", ask["id"] + ".md")).st_mode & 0o777),
                             "0o600")

    def test_an_ask_stays_open_over_two_nights_at_the_top_of_every_report_then_its_check_closes_it(self):
        site = fixture_site(codex=1, devin=1, keys=())
        first = Fake(bucharest(0, 23), site, logins={"devin": ["expired"]})
        self.night(first)
        self.assertEqual(len(first.notes), 2)  # the ask, at once; the night's end
        later = "2026-12-07"
        second = Fake(W.at(later, 0, dt.time(23)), site, logins={"devin": ["expired"]})
        self.night(second, date=later)
        ask = self.asks("login-expired")[0]
        self.assertEqual(ask["nights"], [DATE, later])
        self.assertEqual(ask["opened"], DATE)
        self.assertEqual(len(second.notes), 1)  # not notified again: only the night's end
        report = self.report(later)
        top = report.split("## Parts")[0]
        self.assertIn("Log in again to devin", top)
        self.assertIn(f"open since {DATE}", top)
        third_date = "2026-12-14"
        third = Fake(W.at(third_date, 0, dt.time(23)), site)
        self.night(third, date=third_date)
        self.assertEqual(self.asks("login-expired"), [])
        closed = os.listdir(os.path.join(self.home, "asks", "closed"))
        self.assertEqual(closed, [f"login-expired--devin--{third_date}.json"])
        self.assertNotIn("Log in again", self.report(third_date).split("## Parts")[0])

    def test_nobody_closes_an_ask_by_hand(self):
        self.assertFalse(hasattr(A.Asks, "close"))
        self.assertFalse(any(name in A.Asks.__dict__ for name in ("dismiss", "remove", "delete")))

    def test_an_ask_holds_nothing_private(self):
        asks = A.Asks(os.path.join(self.home, "asks"), today=DATE)
        ask = asks.open("key-refused", "openrouter", route="openrouter", variable="OPENROUTER_API_KEY", status="HTTP 401")
        text = json.dumps(ask) + A.render_one(ask)
        self.assertNotIn(self.home, text)
        self.assertNotIn("/Users/", text)
        self.assertIn("$G/keys.env", text)

    def test_the_morning_status_says_when_the_night_did_not_start(self):
        lines = []
        self.assertIsNone(W.status(DATE, self.home, out=lines.append))
        self.assertIn("the night did not start", lines[0])
        self.assertIn("pmset -g log", lines[0])


class Ledger(unittest.TestCase):
    def test_the_ledger(self):
        with tempfile.TemporaryDirectory() as t:
            led = L.Ledger(t, DATE, 10.0, 2.0)
            self.assertEqual(led.week, "2026-11-30")
            self.assertEqual(L.week_of("2026-12-03"), "2026-11-30")
            self.assertEqual(led.admit("a", "openrouter", "m", 2.5), "over-run-cap")
            self.assertEqual(led.admit("a", "openrouter", "m", None), "no-price")
            self.assertEqual(led.admit("a", "openrouter", "m", 1.5), "ok")
            self.assertAlmostEqual(led.left(), 8.5)
            led.settle("a", "openrouter", "m", 0.4, reported=0.5)
            self.assertAlmostEqual(led.left(), 9.5)
            led.admit("b", "openrouter", "m", 1.0)
            led.release("b")
            self.assertAlmostEqual(led.left(), 9.5)
            again = L.Ledger(t, "2026-12-02", 10.0)  # the same week, read back from its file
            self.assertAlmostEqual(again.left(), 9.5)
            self.assertEqual(oct(os.stat(again.path).st_mode & 0o777), "0o600")
            for i in range(4):
                self.assertEqual(again.admit(f"c{i}", "openrouter", "m", 2.0), "ok")
            self.assertEqual(again.admit("d", "openrouter", "m", 1.5), "ok")
            self.assertEqual(again.admit("e", "openrouter", "m", 0.1), "over-week")

    def test_usage_costs_as_on_18_november(self):
        with tempfile.TemporaryDirectory() as t:
            path = os.path.join(t, "u.jsonl")
            with open(path, "w") as f:
                f.write(json.dumps({"usage": {"input_tokens": 3000, "output_tokens": 10, "cost": 0.004,
                                              "input_tokens_details": {"cached_tokens": 2000}}}) + "\n")
                f.write(json.dumps({"status": 400}) + "\n")
            usd, rep, n = L.usage_cost(path, {"in": 1.0, "read": 0.1, "out": 4.0})
            self.assertAlmostEqual(usd, (1000 * 1.0 + 2000 * 0.1 + 10 * 4.0) / 1e6)
            self.assertAlmostEqual(rep, 0.004)
            self.assertEqual(n, 2)


class Launchd(unittest.TestCase):
    """The agent and its installer: written for the owner's OK, never installed by a test (a target folder of its
    own, no launchctl)."""

    PLIST = os.path.join(ROOT, "scripts", "launchd", "dev.providers.groundtruth.weekly-night.plist")
    INSTALL = os.path.join(ROOT, "scripts", "install-weekly-night.sh")

    def test_the_template_says_monday_at_23_and_go(self):
        import plistlib
        with open(self.PLIST, "rb") as f:
            p = plistlib.load(f)
        self.assertEqual(p["StartCalendarInterval"], {"Weekday": 1, "Hour": 23, "Minute": 0})
        self.assertEqual(p["ProgramArguments"][1:], ["-B", "harness/weekly.py", "__MODE__", "night"])
        self.assertFalse(p["RunAtLoad"])

    def test_the_installer_refuses_without_the_owner_s_ok_and_fills_the_template_in(self):
        with tempfile.TemporaryDirectory() as t:
            home = os.path.join(t, "G")
            os.mkdir(home, 0o700)
            target = os.path.join(t, "agents")
            env = dict(os.environ, GROUNDTRUTH_CLIENT_HOME=home)
            r = subprocess.run([self.INSTALL, "--target", target], env=env, capture_output=True, text=True)
            self.assertEqual(r.returncode, 1)
            self.assertIn("owner's OK", r.stderr)
            self.assertFalse(os.path.exists(target))
            r = subprocess.run([self.INSTALL, "--owner-ok", "--target", target, "--dry-run-nights"], env=env,
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            import plistlib
            with open(os.path.join(target, "dev.providers.groundtruth.weekly-night.plist"), "rb") as f:
                p = plistlib.load(f)
            self.assertEqual(p["ProgramArguments"][3], "--dry-run")
            self.assertEqual(p["WorkingDirectory"], os.path.realpath(ROOT))
            self.assertEqual(p["EnvironmentVariables"]["GROUNDTRUTH_CLIENT_HOME"], home)
            os.chmod(home, 0o755)
            r = subprocess.run([self.INSTALL, "--owner-ok", "--target", target], env=env, capture_output=True,
                               text=True)
            self.assertEqual(r.returncode, 1)
            self.assertIn("not 700", r.stderr)


if __name__ == "__main__":
    unittest.main()


class RealWorldWithoutRequests(unittest.TestCase):
    """The parts of the real World that send nothing."""

    def test_the_keys_file_is_read_only_at_mode_600(self):
        with tempfile.TemporaryDirectory() as t:
            os.chmod(t, 0o700)
            w = W.World(t)
            self.assertEqual(w.read_keys(), {})
            path = os.path.join(t, "keys.env")
            with open(path, "w") as f:
                f.write('OPENROUTER_API_KEY="or-x"\nOPENAI_API_KEY=oa-y\n')
            os.chmod(path, 0o644)
            self.assertEqual(w.read_keys(), {})
            os.chmod(path, 0o600)
            self.assertEqual(w.read_keys(), {"openrouter": "or-x", "openai-api": "oa-y", "anthropic-api": None})

    def test_a_probe_run_s_outcome(self):
        self.assertEqual(W.login_outcome([{"event": "start"}, {"event": "done"}]), {"outcome": "done"})
        self.assertEqual(W.login_outcome([{"event": "start"}, {"event": "stop", "reason": "quota"}])["outcome"], "quota")
        self.assertEqual(W.login_outcome([{"event": "start"}, {"event": "check-failed", "kind": "login"},
                                          {"event": "stop", "reason": "baseline-failed"}])["outcome"], "login")
        self.assertEqual(W.login_outcome([{"event": "start"}, {"event": "check-failed", "kind": "exit-nonzero"},
                                          {"event": "stop", "reason": "control-failed"}])["outcome"], "refused")
        self.assertEqual(W.login_outcome(None)["outcome"], "failed")
