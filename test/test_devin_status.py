"""The Devin CLI's multi-line status for a browser (subscription) login: accepted when it holds only the lines Devin
prints; refused for a login via an API key, a token, a PAT or a personal access, a label naming one, or any other
line. Every value here is made up."""
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "harness"))
import clients as C  # noqa: E402

REAL_SHAPE = """Logged in (via Devin).

Credentials:
  File:              <folder>/data/devin/credentials.toml
  API server:        https://server.example.test
  Devin webapp:      https://app.example.test
  Devin API:         https://api.example.test

User:
  Name:              Ada Fixture
  Email:             <e-mail>
  User ID:           user-00000000-0000-0000-0000-000000000000

Account:
  Tier:              fixture
  Plan:              Pro
  Team ID:           team-fixture-0000
  Team membership:   member
  Enterprise:        no
  Telemetry:         enabled

Team settings:
  Allowed models:    all
  MCP servers:       none
  Sandbox:           disabled
  Fetched at:        2000-01-01 00:00:00 UTC
"""


class DevinMultiLineStatus(unittest.TestCase):
    def setUp(self):
        self.devin = C.Devin("m")

    def why(self, out, err=""):
        return C.login_ok(self.devin, 0, out, err)

    def test_the_real_shape_is_accepted(self):
        self.assertIsNone(self.why(REAL_SHAPE))
        self.assertIsNone(self.why("\x1b[1m" + REAL_SHAPE.replace("\n", "\x1b[0m\n", 1)))  # styled
        self.assertIsNone(self.why(REAL_SHAPE.replace("Logged in (via Devin).", "Logged in (via browser)")))
        self.assertIsNone(self.why(REAL_SHAPE.replace("Logged in (via Devin).", "Logged in as fixture")))

    def test_a_login_via_an_api_key_a_token_a_pat_or_a_personal_access_is_refused(self):
        for via in ("API key", "api key", "token", "PAT", "personal access", "WINDSURF_API_KEY"):
            with self.subTest(via=via):
                why = self.why(REAL_SHAPE.replace("(via Devin)", f"(via {via})"))
                self.assertIsNotNone(why)
                self.assertIn("mentions an API", why)

    def test_a_label_naming_a_key_a_token_a_pat_or_a_personal_access_is_refused(self):
        for line in ("  Token:             fixture", "  API key:           fixture", "  Access token: x",
                     "  PAT:               fixture", "  Personal access:   fixture", "Token:"):
            with self.subTest(line=line):
                why = self.why(REAL_SHAPE.replace("User:\n", f"User:\n{line}\n"))
                self.assertIsNotNone(why)
                self.assertIn("label naming a key", why)

    def test_an_unknown_line_is_refused(self):
        for line in ("  Organisation:      fixture", "Workspace fixture", "Logged in", "  Session: x",
                     "Credentials: something"):
            with self.subTest(line=line):
                why = self.why(REAL_SHAPE.replace("Account:\n", f"Account:\n{line}\n"))
                self.assertIsNotNone(why)
                self.assertIn("not one Devin prints", why)
        self.assertIsNotNone(self.why(REAL_SHAPE, "Not logged in"))

    def test_the_login_line_must_come_first(self):
        body = REAL_SHAPE.split("\n", 1)[1]
        self.assertIsNotNone(self.why(body))
        self.assertIsNotNone(self.why(body + "Logged in (via Devin).\n"))

    def test_a_mention_hidden_in_escape_sequences_is_refused(self):
        hidden = REAL_SHAPE.replace("  Plan:", "  \x1b]8;;http://x/token\x07Plan\x1b]8;;\x07:")
        self.assertIn("hides a mention", self.why(hidden))

    def test_the_refusal_shows_the_cleaned_status(self):
        why = self.why("\x1b[1m" + REAL_SHAPE.replace("(via Devin)", "(via API key)"))
        self.assertIn('"Logged in (via API key).\\n\\nCredentials:', why)

    def test_login_and_probe_read_it_through_the_same_check(self):
        # night.py `login devin` and the probe (state_folder) both call login_status, which calls login_ok.
        with tempfile.TemporaryDirectory() as t, mock.patch.object(C, "CONFINED", False):
            env = {"HOME": t, "TMPDIR": t}
            self.assertIsNone(C.login_status(self.devin, t, env=env, run=lambda a, **k: (0, REAL_SHAPE, "")))
            bad = REAL_SHAPE.replace("User:\n", "User:\n  Token: x\n")
            self.assertIn("label naming a key", C.login_status(self.devin, t, env=env, run=lambda a, **k: (0, bad, "")))
        here = os.path.join(os.path.dirname(__file__), "..", "harness")
        with open(os.path.join(here, "night.py")) as f:
            self.assertIn("C.login_status(client, real, env, status_run)", f.read())
        with open(os.path.join(here, "probe.py")) as f:
            self.assertIn("C.state_folder(client, a.client_home, ROOT, run=run)", f.read())


if __name__ == "__main__":
    unittest.main()
