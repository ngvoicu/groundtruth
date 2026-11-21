"""harness/client_limits.py: the walk through a client against a fake session (no client is run, nothing is sent).

    python3 -m unittest discover -s test -p "test_*.py"
"""
import io
import os
import sys
import unittest
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "harness"))
import client_limits as CL  # noqa: E402
import clients as C  # noqa: E402

OVERHEAD = 16000  # the client's own system prompt and tools


class FakeSession:
    """Accepts up to `window` tokens (one token per " hello" plus the overhead); above it raises the refusal `text`
    (with {tokens} filled in), or the refusal `kind`."""

    def __init__(self, window, text="Prompt is too long", kind="input"):
        self.window, self.text, self.kind, self.sent = window, text, kind, []

    def start(self, prompt):
        n = prompt.count(" hello")
        self.sent.append(n)
        tokens = n + OVERHEAD
        if tokens > self.window:
            e = C.Refused(self.kind, self.text.format(tokens=tokens))
            e.code = 1
            raise e
        return "s", C.Usage(total=tokens, cached=0, calls=1)


def walk(session, **kw):
    rows = []
    with redirect_stdout(io.StringIO()):
        CL.walk(session, "m", "claude-code", "2.1.330 (Claude Code)", rows.append, say=lambda *_: None, **kw)
    return rows


class Walk(unittest.TestCase):
    def test_a_named_window_is_confirmed_once_under_it(self):
        s = FakeSession(1_000_000, text="API Error: 400 prompt is too long: {tokens} tokens > 1000000 maximum")
        rows = walk(s)
        self.assertEqual([r["kind"] for r in rows], ["context", "small", "confirm"])
        self.assertEqual(rows[0]["status"], 400)
        self.assertEqual(rows[0]["exit"], 1)
        self.assertEqual(CL.L.named_limit(rows[0]["message"]), 1_000_000)
        self.assertEqual(rows[2]["status"], 200)
        self.assertEqual(rows[2]["promptTokens"], 999_000)
        for r in rows:
            self.assertEqual((r["client"], r["client_version"]), ("claude-code", "2.1.330 (Claude Code)"))
            self.assertIn("at", r)

    def test_no_named_window_walks_small_then_around_the_proxy_row(self):
        s = FakeSession(1_000_000)
        rows = walk(s, accepted=997_000, refused=1_003_000)
        self.assertEqual([(r["kind"], r["status"]) for r in rows],
                         [("context", "refused"), ("small", 200), ("small", 200), ("context", 200), ("context", "refused")])
        self.assertEqual(rows[3]["promptTokens"], 997_000)
        # the refused size converts exactly with the two small ones, as scripts/build_observed.py checks
        per = (rows[2]["promptTokens"] - rows[1]["promptTokens"]) / (rows[2]["n"] - rows[1]["n"])
        over = rows[1]["promptTokens"] - per * rows[1]["n"]
        self.assertEqual(per * rows[4]["n"] + over, 1_003_001)

    def test_a_client_cap_ends_the_walk_with_no_row(self):
        s = FakeSession(0, text="Input exceeds the maximum length of 1048576 characters.", kind="client-cap")
        self.assertEqual(walk(s), [])
        self.assertEqual(len(s.sent), 1)

    def test_a_quota_refusal_ends_the_walk_with_no_row(self):
        s = FakeSession(0, text="usage limit reached", kind="quota")
        self.assertEqual(walk(s), [])

    def test_an_answer_where_a_refusal_was_expected_ends_the_walk(self):
        s = FakeSession(10_000_000)
        rows = walk(s)
        self.assertEqual(len(rows), 1)
        self.assertEqual(s.sent, [CL.HI])

    def test_only_the_refusal(self):
        s = FakeSession(1_000_000)
        rows = walk(s, only_refusal=True)
        self.assertEqual([r["kind"] for r in rows], ["context"])
        self.assertEqual(s.sent, [CL.HI])

    def test_codex_is_refused_up_front(self):
        with self.assertRaisesRegex(SystemExit, "1,048,576"):
            CL.main(["--harness", "codex", "--model", "m", "--out", "/nonexistent/x.jsonl", "--dry-run"])

    def test_the_dry_run_sends_nothing(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            CL.main(["--harness", "claude", "--model", "m", "--out", "/nonexistent/x.jsonl", "--dry-run"])
        self.assertIn("nothing sent", buf.getvalue())
        self.assertFalse(os.path.exists("/nonexistent/x.jsonl"))


if __name__ == "__main__":
    unittest.main()
