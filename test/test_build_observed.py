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


if __name__ == "__main__":
    unittest.main()
