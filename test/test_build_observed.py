"""scripts/build_observed.py: removed_by_proxy (a field the client sent that the proxy removes before the provider), the
ladder rule of 14 November, and a chain's control (every run's own control, counted once).

    python3 -m unittest discover -s test -p "test_*.py"
"""
import importlib.util
import json
import os
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("build_observed", os.path.join(HERE, "..", "scripts", "build_observed.py"))
bo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bo)


def run_file(body_extra):
    return {"probeVersion": "0.3.3", "label": "T", "model": "m", "startedAt": "2026-11-17T16:27:48.000Z",
            "status": "completed", "control": {"warm": True},
            "request": {"bodyExtra": body_extra},
            "checks": [{"targetAgeMs": 150000, "actualAgeMs": 150500, "warm": True}]}


class RemovedByProxy(unittest.TestCase):
    def build(self, body_extra, **run):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, "results"))
            with open(os.path.join(root, "results", "T.json"), "w") as f:
                json.dump(run_file(body_extra), f)
            bo.ROOT = root
            entry = {"id": "x/T", "file": "results/T.json", "route": "codex-subscription", "client": "cliproxyapi",
                     "model": "m", **run}
            return bo.build_cache({"runs": [entry]})[0]

    def test_a_sent_field_must_be_in_options(self):
        with self.assertRaisesRegex(SystemExit, "must say so"):
            self.build({"prompt_cache_retention": "24h"}, options={})

    def test_in_options_as_before(self):
        e = self.build({"prompt_cache_retention": "24h"}, options={"prompt_cache_retention": "24h"})
        self.assertEqual(e["options"], {"prompt_cache_retention": "24h"})
        self.assertNotIn("removed_by_proxy", e)

    def test_removed_by_proxy_keeps_it_out_of_options_and_in_the_entry(self):
        e = self.build({"prompt_cache_retention": "24h"}, options={},
                       removed_by_proxy={"prompt_cache_retention": "24h"}, note="the proxy deletes it: proof")
        self.assertEqual(e["options"], {})
        self.assertEqual(e["removed_by_proxy"], {"prompt_cache_retention": "24h"})

    def test_removed_by_proxy_needs_a_note(self):
        with self.assertRaisesRegex(SystemExit, "needs a note"):
            self.build({"prompt_cache_retention": "24h"}, options={}, removed_by_proxy={"prompt_cache_retention": "24h"})

    def test_removed_by_proxy_only_names_what_was_sent(self):
        # Another value than the one sent: the sent field is accounted for nowhere.
        with self.assertRaisesRegex(SystemExit, "must say so"):
            self.build({"prompt_cache_retention": "24h"}, options={}, removed_by_proxy={"prompt_cache_retention": "12h"}, note="n")
        # A field the run did not send.
        with self.assertRaisesRegex(SystemExit, "does not record as sent"):
            self.build({"prompt_cache_retention": "24h"}, options={"prompt_cache_retention": "24h"},
                       removed_by_proxy={"prompt_cache_options": {"ttl": "12h"}}, note="n")
        with self.assertRaisesRegex(SystemExit, "also in its options"):
            self.build({"prompt_cache_retention": "24h"}, options={"prompt_cache_retention": "24h"},
                       removed_by_proxy={"prompt_cache_retention": "24h"}, note="n")


class Ladder(unittest.TestCase):
    def build(self, control_warm, checks):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, "results"))
            f = {**run_file(None), "control": {"warm": control_warm}, "checks": checks}
            with open(os.path.join(root, "results", "T.json"), "w") as out:
                json.dump(f, out)
            bo.ROOT = root
            return bo.build_cache({"runs": [{"id": "x/T", "file": "results/T.json", "route": "antigravity",
                                             "client": "cliproxyapi", "model": "m"}]})[0]

    def test_a_missed_control_is_published_without_ages(self):
        e = self.build(False, [])
        self.assertEqual(e["control"], {"warm": 0, "total": 1})
        self.assertEqual(e["checks"], [])

    def test_a_hit_control_still_needs_2_5_minutes_first(self):
        with self.assertRaisesRegex(SystemExit, "2.5 minutes"):
            self.build(True, [])
        with self.assertRaisesRegex(SystemExit, "2.5 minutes"):
            self.build(True, [{"targetAgeMs": 300000, "actualAgeMs": 300500, "warm": True}])


def check(age_s, warm):
    return {"targetAgeMs": age_s * 1000, "actualAgeMs": age_s * 1000 + 500, "warm": warm}


class ChainControl(unittest.TestCase):
    """A run that continues another carries every control of the chain, each run's own counted once."""

    def build(self, runs):
        # runs: [(label, started, control_warm or None, checks, continues)]
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, "results"))
            manifest = []
            for label, started, control, checks, continues in runs:
                f = {**run_file(None), "label": label, "startedAt": started, "checks": checks}
                if control is None:
                    del f["control"]
                else:
                    f["control"] = {"warm": control}
                with open(os.path.join(root, "results", f"{label}.json"), "w") as out:
                    json.dump(f, out)
                entry = {"id": f"x/{label}", "file": f"results/{label}.json", "route": "codex-subscription",
                         "client": "cliproxyapi", "model": "m"}
                if continues:
                    entry["continues"] = f"x/{continues}"
                manifest.append(entry)
            bo.ROOT = root
            return {e["id"].split("/")[1]: e for e in bo.build_cache({"runs": manifest})}

    def test_all_hit_three_runs(self):
        e = self.build([("A", "2026-11-17T10:00:00.000Z", True, [check(150, True)], None),
                        ("B", "2026-11-17T11:00:00.000Z", True, [check(150, True)], "A"),
                        ("C", "2026-11-17T12:00:00.000Z", True, [check(300, True)], "B")])
        self.assertEqual(e["A"]["control"], {"warm": 1, "total": 1})
        self.assertEqual(e["B"]["control"], {"warm": 2, "total": 2})
        self.assertEqual(e["C"]["control"], {"warm": 3, "total": 3})  # A's counted once, not again through B
        self.assertEqual(e["C"]["checks"], [{"age": "2.5m", "age_s": 150, "warm": 2, "total": 2},
                                            {"age": "5m", "age_s": 300, "warm": 1, "total": 1}])

    def test_mixed_outcome_is_kept(self):
        # LC4 / CL4: the first run's control hit, the continuation's missed and it has no check.
        e = self.build([("A", "2026-11-17T10:00:00.000Z", True, [check(150, False), check(150, True)], None),
                        ("B", "2026-11-17T14:00:00.000Z", False, [], "A")])
        self.assertEqual(e["B"]["control"], {"warm": 1, "total": 2})
        self.assertEqual(e["B"]["checks"], [{"age": "2.5m", "age_s": 150, "warm": 1, "total": 2}])
        self.assertIsNone(e["B"]["all_warm_through_s"])
        self.assertEqual(e["A"]["control"], {"warm": 1, "total": 1})  # the earlier run keeps its own

    def test_the_only_control_missed(self):
        # The earlier run recorded no control (before 14 November); the continuation's control missed.
        e = self.build([("A", "2026-11-10T10:00:00.000Z", None, [check(300, True)], None),
                        ("B", "2026-11-17T14:00:00.000Z", False, [], "A")])
        self.assertEqual(e["A"]["control"], {"warm": 0, "total": 0})
        self.assertEqual(e["B"]["control"], {"warm": 0, "total": 1})


def harness_file(controls, ages):
    rows = [{"event": "start", "harness": "pi", "at": "2026-11-17T10:00:00Z"}]
    rows += [{"event": "check", "age": "control", "warm": w} for w in controls]
    rows += [{"event": "check", "age": a, "warm": True} for a in ages]
    return "".join(json.dumps(r) + "\n" for r in rows)


class MixedControlLadder(unittest.TestCase):
    """The ladder rule reads a run's own control: only a run whose every control missed may end without ages."""

    def build(self, controls, ages):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, "results"))
            with open(os.path.join(root, "results", "H.jsonl"), "w") as out:
                out.write(harness_file(controls, ages))
            bo.ROOT = root
            return bo.build_cache({"runs": [{"id": "x/H", "file": "results/H.jsonl", "route": "antigravity",
                                             "model": "m"}]})[0]

    def test_mixed_control_without_ages_is_refused(self):
        with self.assertRaisesRegex(SystemExit, "2.5 minutes"):
            self.build([True, False], [])

    def test_mixed_control_with_the_ladder_is_published_as_recorded(self):
        e = self.build([True, False], ["2.5m", "5m"])
        self.assertEqual(e["control"], {"warm": 1, "total": 2})

    def test_every_control_missed_without_ages_is_accepted(self):
        e = self.build([False, False], [])
        self.assertEqual(e["control"], {"warm": 0, "total": 2})


def own_file(harness="claude", date="2026-11-23", cached=18000, w1=0, w5=0, client_env=None, isolation=True, version="2.1.330"):
    start = {"event": "start", "harness": harness, "client": bo.HARNESS_CLIENT[harness], "at": f"{date}T10:00:00Z",
             "effort": "low", "client_version": version}
    if isolation:
        start["isolation"] = {"home": "dedicated", "work": "temporary"}
    if client_env:
        start["client_env"] = client_env
    usage = {"total": 29000, "cached": cached, "write": 11000, "calls": 1, "write_1h": w1, "write_5m": w5}
    rows = [start, {"event": "baseline", "usage": usage}, {"event": "prime", "age": "control", "usage": usage},
            {"event": "check", "age": "control", "warm": bool(cached), "usage": usage},
            {"event": "check-invalid", "age": "2.5m", "usage": usage},
            {"event": "check", "age": "2.5m", "warm": bool(cached), "usage": usage}]
    return "".join(json.dumps(r) + "\n" for r in rows)


class OwnClients(unittest.TestCase):
    """The kinds and the refusals of docs/own-clients.md, section 3."""

    def build(self, text, route="claude-subscription", **run):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, "results"))
            with open(os.path.join(root, "results", "H.jsonl"), "w") as out:
                out.write(text)
            bo.ROOT = root
            return bo.build_cache({"runs": [{"id": "x/H", "file": "results/H.jsonl", "route": route, "model": "m", **run}]})[0]

    def test_every_client_and_route_has_a_kind(self):
        bo.check_kinds()
        self.assertEqual(set(bo.CLIENT_KINDS), set(bo.CLIENTS))
        self.assertEqual(set(bo.ROUTE_KINDS), set(bo.ROUTES))
        self.assertEqual(set(bo.CLIENT_KINDS.values()), {"direct", "own_client", "proxy"})
        self.assertEqual(set(bo.ROUTE_KINDS.values()), {"api_key", "login"})
        self.assertTrue(all(isinstance(v, str) for v in bo.CLIENTS.values()))  # clients stays a map of texts
        saved = dict(bo.CLIENTS)
        try:
            bo.CLIENTS["new-client"] = "a client without a kind"
            with self.assertRaisesRegex(SystemExit, "needs a kind"):
                bo.check_kinds()
        finally:
            bo.CLIENTS.clear()
            bo.CLIENTS.update(saved)

    def test_an_own_client_on_another_vendors_route_is_refused(self):
        with self.assertRaisesRegex(SystemExit, "own client of claude-subscription"):
            self.build(own_file(w1=11000), route="devin")
        with self.assertRaisesRegex(SystemExit, "own client of"):
            bo.check_limit({"route": "codex-subscription", "client": "devin-cli", "model": "m", "context": 1000}, "row")
        with self.assertRaisesRegex(SystemExit, "own client of"):
            bo.check_own_route("known", "claude-code", "anthropic-api")

    def test_a_run_with_no_cached_token_in_any_reply_is_refused(self):
        with self.assertRaisesRegex(SystemExit, "goes in excluded"):
            self.build(own_file(cached=0, w1=11000))

    def test_a_proxy_run_with_no_cached_token_is_not_this_rule(self):
        e = self.build(own_file(harness="pi", cached=0, isolation=False), route="devin")
        self.assertEqual(e["client"], "pi+cliproxyapi")

    def test_the_written_ttl_is_recorded_and_checked_against_the_options(self):
        e = self.build(own_file(w1=11000))
        self.assertEqual((e["written_ttl"], e["client_version"]), ("1h", "2.1.330"))
        self.assertNotIn("ttl", e["options"])
        with self.assertRaisesRegex(SystemExit, "replies wrote 1h"):
            self.build(own_file(w1=11000), options={"ttl": "5m"})
        with self.assertRaisesRegex(SystemExit, "more than one lifetime"):
            self.build(own_file(w1=11000, w5=200))

    def test_a_ttl_the_run_set_must_be_in_the_options(self):
        env = {"CLAUDE_CODE_PROMPT_CACHE_TTL": "5m"}
        with self.assertRaisesRegex(SystemExit, "options must say ttl 5m"):
            self.build(own_file(w5=11000, client_env=env))
        e = self.build(own_file(w5=11000, client_env=env), options={"ttl": "5m"})
        self.assertEqual((e["options"]["ttl"], e["written_ttl"]), ("5m", "5m"))

    def test_a_new_own_client_run_must_record_its_isolation(self):
        with self.assertRaisesRegex(SystemExit, "isolation"):
            self.build(own_file(w1=11000, isolation=False))
        e = self.build(own_file(harness="codex", date="2026-11-07", isolation=False), route="codex-subscription")
        self.assertNotIn("written_ttl", e)  # an older run: no isolation recorded, accepted as before

    def test_check_invalid_rows_are_not_checks(self):
        e = self.build(own_file(w1=11000))
        self.assertEqual(e["checks"], [{"age": "2.5m", "age_s": 150, "warm": 1, "total": 1}])

    def test_an_own_client_limits_row_needs_the_providers_refusal(self):
        row = {"route": "claude-subscription", "client": "claude-code", "model": "m", "input_accepted": 900000}
        with self.assertRaisesRegex(SystemExit, "needs context or input_refused"):
            bo.check_limit(row, "row")
        bo.check_limit({**row, "context": 1000000}, "row")
        bo.check_limit({**row, "input_refused": 1003000}, "row")
        bo.check_limit({**row, "client": "cliproxyapi"}, "row")  # a proxy row as before

    def test_the_maps_are_in_the_output(self):
        bo.ROOT = os.path.join(HERE, "..")
        out = bo.build()
        self.assertEqual(out["client_kinds"], bo.CLIENT_KINDS)
        self.assertEqual(out["route_kinds"], bo.ROUTE_KINDS)
        self.assertEqual(out["schema"], 1)
        known = [k for k in out["known"] if k["client"] == "claude-code"]
        self.assertEqual(sorted(k["ttl_s"] for k in known), [300, 3600])


if __name__ == "__main__":
    unittest.main()
