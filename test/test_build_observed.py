"""scripts/build_observed.py: removed_by_proxy (a field the client sent that the proxy removes before the provider).

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


if __name__ == "__main__":
    unittest.main()
