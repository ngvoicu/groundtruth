"""harness/agent_gateway.py (its readings of an answer, the labels it publishes) and its reader in
scripts/build_observed.py (counted checks only, the labels carried, the ladder rule and first_ages).

    python3 -m unittest discover -s test -p "test_*.py"
"""
import importlib.util
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "harness"))
import agent_gateway as ag  # noqa: E402

spec = importlib.util.spec_from_file_location("build_observed", os.path.join(HERE, "..", "scripts", "build_observed.py"))
bo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bo)

M1 = "a." + "k3v7qz2m5xw4hn6tb2rc"   # the README's example marker, built so that no file holds it whole
M2 = "a." + "p9q8r7s6t5u4v3w2x1y0"
KEY = "s." + "zz11yy22xx33ww44vv55"


class Answer(unittest.TestCase):
    def test_anthropic_stream(self):
        raw = "\n".join([
            'event: message_start',
            'data: {"type":"message_start","message":{"model":"claude-fable-5-2","usage":{"input_tokens":2,'
            '"cache_creation_input_tokens":915,"cache_read_input_tokens":6125,"output_tokens":1,'
            '"cache_creation":{"ephemeral_5m_input_tokens":0,"ephemeral_1h_input_tokens":915}}}}',
            'data: {"type":"message_delta","usage":{"output_tokens":4}}',
        ])
        model, usages, merged, types = ag.read_answer(raw)
        self.assertEqual(model, "claude-fable-5-2")
        self.assertEqual(merged, {"input": 7042, "cache_read": 6125, "cache_write": 915, "output": 4})
        self.assertEqual(len(usages), 2)
        self.assertIn("message_start", types)

    def test_responses_stream(self):
        raw = 'data: {"type":"response.completed","response":{"model":"gpt-6.2-sol","usage":{"input_tokens":2939,' \
              '"input_tokens_details":{"cached_tokens":2816},"output_tokens":5}}}'
        model, _, merged, _ = ag.read_answer(raw)
        self.assertEqual(model, "gpt-6.2-sol")
        self.assertEqual(merged, {"input": 2939, "cache_read": 2816, "cache_write": None, "output": 5})

    def test_chat_completions(self):
        raw = 'data: {"model":"m","usage":{"prompt_tokens":100,"prompt_tokens_details":{"cached_tokens":64},' \
              '"completion_tokens":3}}'
        self.assertEqual(ag.read_answer(raw)[2], {"input": 100, "cache_read": 64, "cache_write": None, "output": 3})

    def test_answering_model(self):
        self.assertTrue(ag.answered_by_model("claude-fable-5-2", "claude-fable-5-2"))
        self.assertTrue(ag.answered_by_model("gemini-4-hydrogen", "gemini-4-hydrogen-low"))
        self.assertTrue(ag.answered_by_model(None, "gpt-6.2-sol"))
        self.assertFalse(ag.answered_by_model("claude-opus-5", "claude-fable-5-2"))


def run_rows(checks, control=(True,), marker=M1, model="m", start_extra=None):
    """A run of agent_gateway as it writes it, with raw markers: checks are (target_s, age_s, warm, counted)."""
    acct = [{"provider": "codex", "kind": "oauth", "priority": -14, "account": marker},
            {"provider": "codex", "kind": "apikey", "priority": -25, "account": KEY}]
    rows = [{"kind": "start", "tool": "agent_gateway", "client": "pi+cliproxyapi", "t": "2026-11-27T14:45:00.000+00:00",
             "accounts": acct, "intended": [marker], "model": model, "thinking": "low", **(start_extra or {})}]

    def req(role, warm=None, counted=True, target=None, age=None):
        q = {"method": "POST", "path": "/v1/messages", "status": 200, "account": marker, "answer_model": model,
             "usage_raw": [{"event": "response.completed", "usage": {"input_tokens": 9, "attribution": {"items": {"msg_1": {}}}}}]}
        r = {"kind": "request", "role": role, "sample": "gt-x", "calls": 1, "account": marker, "answer_model": model,
             "requests": [q], "usage": {"input": 9, "cache_read": 9, "cache_write": None, "output": 1}}
        if role in ("check", "control"):
            r.update(target_age_s=target, age_s=age, warm=warm, counted=counted,
                     not_counted_because=[] if counted else ["check: answered by another account"])
        return r
    for w in control:
        rows.append(req("control", w, True, 30, 30.0))
    for target, age, warm, counted in checks:
        rows.append(req("check", warm, counted, target, age))
    rows.append({"kind": "end", "reason": "done"})
    return rows


class Publish(unittest.TestCase):
    def test_markers_become_labels_and_answer_ids_go(self):
        rows = run_rows([(150, 150.0, True, True)])
        labels = ag.account_labels(rows)
        self.assertEqual(labels, {M1: "codex-login-1", KEY: "codex-apikey-1"})
        out = [ag.public_row(r, labels) for r in rows]
        text = json.dumps(out)
        self.assertNotIn(M1, text)
        self.assertNotIn(KEY, text)
        self.assertNotIn("attribution", text)
        self.assertEqual(out[0]["intended"], ["codex-login-1"])

    def test_a_marker_left_is_refused(self):
        rows = run_rows([(150, 150.0, True, True)])
        with self.assertRaisesRegex(SystemExit, "still holds"):
            ag.public_row({**rows[1], "note": "answered by " + M2}, ag.account_labels(rows))

    def test_one_label_per_account_across_files(self):
        a, b = run_rows([], marker=M1), run_rows([], marker=M2)
        labels = ag.account_labels(a + b)
        self.assertEqual(labels[M1], "codex-login-1")
        self.assertEqual(labels[M2], "codex-login-2")


class Reader(unittest.TestCase):
    def build(self, rows, publish=True, **run):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, "results"))
            if publish:
                labels = ag.account_labels(rows)
                rows = [ag.public_row(r, labels) for r in rows]
            with open(os.path.join(root, "results", "R.jsonl"), "w") as f:
                f.write("".join(json.dumps(r) + "\n" for r in rows))
            bo.ROOT = root
            entry = {"id": "x/R", "file": "results/R.jsonl", "route": "codex-subscription", "client": "pi+cliproxyapi",
                     "model": "m", **run}
            return bo.build_cache({"runs": [entry]})[0]

    def test_counted_checks_only_and_the_label(self):
        e = self.build(run_rows([(150, 150.0, True, True), (150, 150.0, False, False), (300, 300.0, False, True)]))
        self.assertEqual(e["checks"], [{"age": "2.5m", "age_s": 150, "warm": 1, "total": 1},
                                       {"age": "5m", "age_s": 300, "warm": 0, "total": 1}])
        self.assertEqual(e["control"], {"warm": 1, "total": 1})
        self.assertEqual(e["answered_by"], ["codex-login-1"])
        self.assertEqual(e["not_counted"], 1)
        self.assertEqual(e["options"], {"reasoning": "low"})

    def test_a_late_check_is_left_out(self):
        e = self.build(run_rows([(150, 150.0, True, True), (150, 190.0, True, True)]))
        self.assertEqual(e["late_excluded"], 1)

    def test_a_raw_marker_is_refused(self):
        with self.assertRaisesRegex(SystemExit, "neutral label"):
            self.build(run_rows([(150, 150.0, True, True)]), publish=False)

    def test_the_ladder_holds_without_first_ages(self):
        with self.assertRaisesRegex(SystemExit, "2.5 minutes"):
            self.build(run_rows([(1500, 1500.0, True, True)]))

    def test_first_ages_publishes_the_ages_as_planned(self):
        e = self.build(run_rows([(1500, 1500.0, True, True)]), first_ages="around the documented 30 minutes")
        self.assertEqual(e["first_ages"], "around the documented 30 minutes")
        self.assertEqual(e["all_warm_through_s"], 1500)

    def test_first_ages_still_needs_a_control(self):
        with self.assertRaisesRegex(SystemExit, "needs a control"):
            self.build(run_rows([(1500, 1500.0, True, True)], control=()), first_ages="x")

    def test_the_logins_provider_part_of_a_gateway_id(self):
        rows = run_rows([(150, 150.0, True, True)], model="devin/swe-2-1", start_extra={"login": "devin"})
        self.assertEqual(self.build(rows, model="swe-2-1")["model"], "swe-2-1")
        with self.assertRaisesRegex(SystemExit, "a reroute"):
            self.build(rows, model="swe-2")
        other = run_rows([(150, 150.0, True, True)], model="other/swe-2-1", start_extra={"login": "devin"})
        with self.assertRaisesRegex(SystemExit, "a reroute"):
            self.build(other, model="swe-2-1")

    def test_first_ages_is_only_for_this_tool(self):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, "results"))
            with open(os.path.join(root, "results", "T.json"), "w") as f:
                json.dump({"probeVersion": "0.3.5", "startedAt": "2026-11-27T10:00:00.000Z", "control": {"warm": True},
                           "checks": [{"targetAgeMs": 1500000, "actualAgeMs": 1500000, "warm": True}]}, f)
            bo.ROOT = root
            with self.assertRaisesRegex(SystemExit, "only for runs of harness/agent_gateway.py"):
                bo.build_cache({"runs": [{"id": "x/T", "file": "results/T.json", "route": "codex-subscription",
                                          "client": "cliproxyapi", "model": "m", "first_ages": "x"}]})


if __name__ == "__main__":
    unittest.main()
