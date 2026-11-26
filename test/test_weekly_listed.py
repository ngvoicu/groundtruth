"""The weekly night on discovery's real listed.json (test/fixtures/listed-2026-11-25.json, the first file published on
GitHub's main, commit f47a137): its rows have `reasoning.levels`, no `efforts`, no `release_date`, no `first_seen`,
and Devin's ids are base ids. Nothing is sent: fixtures only.

    python3 -m unittest discover -s test -p "test_*.py"
"""
import datetime as dt
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "harness"))
import listed_schema as S  # noqa: E402
import plan as P  # noqa: E402
import weekly as W  # noqa: E402
import asks as A  # noqa: E402
from test_weekly_night import Fake, NightCase, bucharest, entry, fixture_site  # noqa: E402

DATE = "2026-11-30"
with open(os.path.join(HERE, "fixtures", "listed-2026-11-25.json")) as f:
    LISTED = json.load(f)


def lab(provider, model, release, canonical):
    e = entry(provider, model, release=release)
    e["canonical_id"] = canonical
    return e


def site(*entries):
    return {"dataset": "fixture", "entries": {f"{e['provider']}/{e['model']}": e for e in entries}}


# The dates providers.dev gave on 2026-11-25 (dataset 740666cccfa41224) for a few of the listed models.
SITE = site(
    lab("openai", "gpt-6.2-sol", "2026-11-17", "openai/gpt-6.2-sol"),
    lab("openai", "gpt-6.2-astra", "2026-11-17", "openai/gpt-6.2-astra"),
    lab("anthropic", "claude-fable-5-2", "2026-11-09", "anthropic/claude-fable-5-2"),
    lab("openrouter", "google/gemini-3.5-flash", "2026-05-19", "google/gemini-3.5-flash"),  # only through OpenRouter
    lab("deepseek", "deepseek-v4-pro", "2026-10-30", "deepseek/deepseek-v4-pro"),
    lab("openrouter", "deepseek/deepseek-v4-pro", "2026-11-01", "deepseek/deepseek-v4-pro"),  # the lab's wins
    lab("nvidia", "nemotron-3-5-super", "2026-11-02", "nvidia/nemotron-3-5-super"),
    lab("cognition", "swe-2", "2026-11-03", "cognition/swe-2"),
)


def build(values=None, listed=LISTED, s=SITE):
    with tempfile.TemporaryDirectory() as t:
        return P.build(DATE, {"client_kinds": {}, "cache": [], "limits": []}, s, values, listed, root=t)


def item(plan, route, model, q="cache"):
    return next(i for i in plan["items"] if i["key"] == f"{route}|{model}|{q}")


class TheRealFile(unittest.TestCase):
    def test_the_fixture_is_the_published_shape(self):
        self.assertEqual(S.validate(LISTED), [])
        rows = [m for p in LISTED["providers"].values() for m in p["models"]]
        self.assertFalse(any(k in m for m in rows for k in ("efforts", "release_date", "first_seen")))
        self.assertEqual({p: len(v["models"]) for p, v in LISTED["providers"].items()},
                         {"claude-subscription": 15, "devin": 60, "openai-codex": 10})

    def test_offered_reads_the_levels_from_reasoning(self):
        offers, notes = P.offered(SITE, LISTED)
        self.assertEqual(notes, [])
        devin = {r["model"]: r for r in offers["devin"]}
        self.assertEqual(len(devin), 60)
        self.assertEqual(devin["deepseek-v4-pro"]["efforts"], ["high", "max"])
        self.assertEqual(devin["nemotron-3-5-super"]["efforts"], ["none", "medium", "high"])
        self.assertEqual(devin["claude-opus-4-6"]["efforts"], [])  # the list states no reasoning
        self.assertEqual([r["model"] for r in offers["codex-subscription"]][:2], ["gpt-5.6-luna", "gpt-5.6-sol"])
        self.assertTrue(all(r["from"] == "listed" for r in offers["devin"] + offers["codex-subscription"]))

    def test_the_devin_id_a_run_asks_for(self):
        offers, _ = P.offered(SITE, LISTED)
        levels = {r["model"]: r["efforts"] for r in offers["devin"]}
        want = {"deepseek-v4-pro": "deepseek-v4-pro-high",  # no `low` on Devin (2026-11-23): its lowest
                "nemotron-3-5-super": "nemotron-3-5-super-none", "swe-2": "swe-2-medium",
                "gpt-6-2-sol": "gpt-6-2-sol-low", "gemini-4-hydrogen": "gemini-4-hydrogen-low",
                "claude-opus-4-6": "claude-opus-4-6"}
        for model, ask in want.items():
            self.assertEqual(W.devin_model(model, levels[model]), ask, model)
        # The first night's own choices agree with the list (harness/night.py's DEVIN).
        for _, first, _ in W.N.DEVIN:
            base = P.base_id(first)
            if base in levels:
                self.assertEqual(W.devin_model(base, levels[base]), first, first)
        self.assertEqual(W.devin_model("glm-5-3", None), "glm-5-3-low")  # no listed.json: the first night's

    def test_a_login_run_asks_for_the_listed_level(self):
        plan = build({"first_seen": {}})
        runs, _ = W.login_runs(plan, "devin", values={"devin|deepseek-v4-pro|cache", "devin|swe-2|cache"})
        asked = {r["model"]: r["ask_model"] for r in runs}
        self.assertEqual(asked, {"deepseek-v4-pro": "deepseek-v4-pro-high", "swe-2": "swe-2-medium"})


class Dates(unittest.TestCase):
    def test_a_login_id_takes_the_lab_s_date_even_through_openrouter(self):
        plan = build()
        self.assertEqual(item(plan, "devin", "gpt-6-2-sol")["release"], "2026-11-17")
        self.assertEqual(item(plan, "devin", "gpt-6-2-sol")["release_basis"], "lab release")
        self.assertEqual(item(plan, "codex-subscription", "gpt-6.2-sol")["release"], "2026-11-17")
        g = item(plan, "devin", "gemini-3-5-flash")
        self.assertEqual((g["release"], g["state"]), ("2026-05-19", P.TOO_OLD))
        self.assertEqual(item(plan, "devin", "deepseek-v4-pro")["release"], "2026-10-30")

    def test_without_any_date_a_model_is_not_measured_and_is_named(self):
        plan = build({})
        swe = item(plan, "devin", "swe-1-6")
        self.assertEqual((swe["release_basis"], swe["release"], swe["state"]), (P.NO_DATE, None, P.UNDATED))
        self.assertIn("swe-1-6", plan["newly_seen"]["devin"])
        self.assertIn(("devin", "swe-1-6"), plan["undated"])
        self.assertNotIn("devin|swe-1-6|cache", [i["key"] for i in plan["planned"]])

    def test_the_baseline_records_the_models_listed_before_discovery(self):
        values = {"first_seen": {"devin": {"swe-2": "2026-11-22"}}}
        added = P.record_baseline(values, build(values))
        self.assertGreater(added, 0)
        self.assertIsNone(values["first_seen"]["devin"]["swe-1-6"])
        self.assertIsNone(values["first_seen"]["devin"]["claude-opus-4-6"])
        self.assertEqual(values["first_seen"]["devin"]["swe-2"], "2026-11-22")  # kept
        self.assertNotIn("gpt-6-2-sol", values["first_seen"]["devin"])  # it has a date: not baseline
        plan = build(values)
        swe = item(plan, "devin", "swe-1-6")
        self.assertEqual((swe["state"], swe["release"], swe["release_basis"], swe["fresh"]),
                         (P.UNDATED, None, P.NO_DATE, False))
        self.assertNotIn("swe-1-6", plan["newly_seen"].get("devin", {}))
        # A model discovery lists for the first time later, with no date anywhere: not measured either.
        later = json.loads(json.dumps(LISTED))
        later["providers"]["devin"]["models"].append({"id": "swe-3", "name": "SWE-3"})
        fresh = item(build(values, later), "devin", "swe-3")
        self.assertEqual((fresh["state"], fresh["release_basis"], fresh["fresh"]), (P.UNDATED, P.NO_DATE, True))
        # The publication keeps the nulls.
        kept = P.values_file({"client_kinds": {}, "cache": []}, SITE, values, today=DATE,
                             first_seen={"devin": {"swe-1-6": DATE, "swe-3": DATE}})
        self.assertIsNone(kept["first_seen"]["devin"]["swe-1-6"])
        self.assertEqual(kept["first_seen"]["devin"]["swe-3"], DATE)

    def test_the_committed_values_file_holds_the_baseline(self):
        with open(os.path.join(ROOT, "plan", "values.json")) as f:
            values = json.load(f)
        for route, model in (("devin", "swe-1-6"), ("devin", "claude-opus-4-6"), ("devin", "gpt-5-4-mini"),
                             ("codex-subscription", "gpt-5.6-terra")):
            self.assertIn(model, values["first_seen"][route])
            self.assertIsNone(values["first_seen"][route][model])
        plan = build(values)
        self.assertEqual(item(plan, "devin", "swe-1-6")["state"], P.UNDATED)
        self.assertEqual(item(plan, "devin", "swe-2")["first_seen"], "2026-11-22")


class DryNight(unittest.TestCase):
    def test_a_dry_night_on_the_real_file_sends_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as root:
            with open(os.path.join(home, "listed.json"), "w") as f:
                json.dump(LISTED, f)
            w = Fake(W.at(DATE, 0, dt.time(23, 0)), SITE)
            out = []
            n = W.Night(DATE, w, home, dry=True, out=out.append, root=root)
            n.run()
            self.assertEqual(os.listdir(home), ["listed.json"])
            self.assertEqual(os.listdir(root), [])
            sent = {c[0] for c in w.calls} & {"start", "window", "key_check", "login_status", "smoke", "read_keys",
                                               "untouched", "keep_awake"}
            self.assertEqual(sent, set())
            self.assertIn("would run discovery first", "\n".join(out))
            devin = n.parts["devin"]["planned"]
            self.assertLessEqual(devin, W.LOGIN_CAP)


class Asleep(NightCase):
    """The Mac asleep at 23:00, or the job run late: never silent, never over a night that did start."""

    def test_a_missed_job_run_later_in_the_week_is_last_monday_s_night(self):
        tz = bucharest(0, 23).tzinfo
        self.assertEqual(W.last_monday(dt.datetime(2026, 12, 1, 14, 0, tzinfo=tz)), DATE)  # Tuesday afternoon
        self.assertEqual(W.last_monday(dt.datetime(2026, 12, 3, 9, 0, tzinfo=tz)), DATE)   # Thursday
        self.assertEqual(W.last_monday(dt.datetime(2026, 12, 7, 8, 0, tzinfo=tz)), DATE)   # next Monday morning
        self.assertEqual(W.last_monday(dt.datetime(2026, 12, 7, 13, 0, tzinfo=tz)), "2026-12-07")
        fake = Fake(dt.datetime(2026, 12, 1, 14, 0, tzinfo=tz), fixture_site())
        self.night(fake)
        self.assertEqual(fake.started(), [])
        self.assertEqual(len(self.asks("night-not-started")), 1)
        self.assertTrue(fake.notes)

    def test_a_late_start_never_overwrites_a_night_that_started(self):
        self.night(Fake(bucharest(0, 23), fixture_site(codex=1, devin=1)))
        path = os.path.join(self.home, f"night-{DATE}", "state.json")
        with open(path) as f:
            before = f.read()
        late = self.night(Fake(bucharest(1, 4), fixture_site()))
        with open(path) as f:
            self.assertEqual(f.read(), before)
        self.assertEqual(self.asks("night-not-started"), [])
        self.assertIn("started already", "\n".join(late.lines))

    def test_the_by_hand_start_under_today_s_date_closes_the_ask(self):
        self.night(Fake(bucharest(1, 8), fixture_site()))
        ask = self.asks("night-not-started")[0]
        self.assertIn("--date <today> --go night", ask["command"])
        tuesday = "2026-12-01"
        n = self.night(Fake(W.at(tuesday, 0, dt.time(9, 0)), fixture_site(codex=1, devin=1)), date=tuesday)
        self.assertEqual(self.asks("night-not-started"), [])
        self.assertEqual(n.ledger.week, DATE)  # the same week's money

    def test_a_signed_out_client_stops_its_part_only(self):
        fake = Fake(bucharest(0, 23), fixture_site(codex=2, devin=2), logins={"devin": ["expired"]})
        n = self.night(fake)
        self.assertTrue(n.parts["devin"]["status"].startswith("not started: login expired"))
        self.assertEqual(fake.started("dv-"), [])
        self.assertEqual(len(fake.started("cx-")), 2)
        self.assertEqual([a["subject"] for a in self.asks("login-expired")], ["devin"])


class NothingWithoutGo(unittest.TestCase):
    def test_check_sends_nothing_without_go(self):
        import contextlib
        import io
        with tempfile.TemporaryDirectory() as home:
            os.environ["GROUNDTRUTH_CLIENT_HOME"] = home
            try:
                orig = W.World
                W.World = None  # any use of the world would fail
                for what in ("keys", "logins"):
                    buf = io.StringIO()
                    with contextlib.redirect_stdout(buf):
                        W.main(["check", what])
                    self.assertIn("nothing sent without --go", buf.getvalue())
            finally:
                W.World = orig
                del os.environ["GROUNDTRUTH_CLIENT_HOME"]
            self.assertEqual(os.listdir(home), [])

    def test_the_night_s_discovery_never_publishes(self):
        seen = []

        class Done:
            returncode, stdout = 0, ""
        orig = W.subprocess.run
        W.subprocess.run = lambda argv, **kw: seen.append((argv, kw)) or Done()
        try:
            with tempfile.TemporaryDirectory() as home:
                self.assertIsNone(W.World(home).discover())
        finally:
            W.subprocess.run = orig
        argv, kw = seen[0]
        self.assertTrue(argv[-1].endswith("discover.py"))
        self.assertNotIn("--publish", argv)
        self.assertEqual(kw["env"]["GROUNDTRUTH_CLIENT_HOME"], home)

    def test_the_launchd_agent_is_the_one_caller_with_go(self):
        with open(os.path.join(ROOT, "scripts", "launchd", "dev.providers.groundtruth.weekly-night.plist")) as f:
            text = f.read()
        self.assertIn("<string>__MODE__</string>", text)
        self.assertIn("<string>Standard</string>", text)
        self.assertIn("wakeorpoweron M 23:01:00", text)


if __name__ == "__main__":
    unittest.main()
