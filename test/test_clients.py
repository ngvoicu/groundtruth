"""harness/clients.py: each client's output parsed from recorded fixtures (test/fixtures/clients/<harness>/<case>.json),
each command as docs/own-clients.md section 1 gives it, and each environment an allow-list. No client is run.

    python3 -m unittest discover -s test -p "test_*.py"
"""
import glob
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "harness"))
import clients as C  # noqa: E402

FIXTURES = os.path.join(HERE, "fixtures", "clients")
OWN = ("claude", "codex", "devin", "muse")
CASES = ("prime", "warm", "cold", "two-requests", "quota", "input")


def load(path):
    with open(path) as f:
        return json.load(f)


def fixtures():
    for path in sorted(glob.glob(os.path.join(FIXTURES, "*", "*.json"))):
        yield os.path.basename(os.path.dirname(path)), os.path.basename(path)[:-5], load(path)


class Parse(unittest.TestCase):
    def test_every_own_client_has_every_case(self):
        have = {(h, c) for h, c, _ in fixtures()}
        for h in OWN:
            for case in CASES:
                self.assertIn((h, case), have)

    def test_each_fixture_parses_as_expected(self):
        for harness, case, f in fixtures():
            with self.subTest(harness=harness, case=case):
                client = C.CLIENTS[harness]("m")
                if "refused" in f:
                    with self.assertRaises(C.Refused) as e:
                        client.parse(f["stdout"], f["stderr"], f["code"], f["files"])
                    self.assertEqual(e.exception.kind, f["refused"])
                elif f.get("error"):
                    with self.assertRaises(C.ClientError):
                        client.parse(f["stdout"], f["stderr"], f["code"], f["files"])
                else:
                    u = client.parse(f["stdout"], f["stderr"], f["code"], f["files"])
                    got = {k: v for k, v in u.__dict__.items() if v is not None}
                    want = dict(f["expect"])
                    if harness == "muse":
                        want.setdefault("write", None)
                        got.setdefault("write", None)
                    self.assertEqual(got, want)

    def test_a_named_window_survives_in_the_refusal(self):
        f = load((os.path.join(FIXTURES, "devin", "input.json")))
        with self.assertRaises(C.Refused) as e:
            C.Devin("m").parse(f["stdout"], f["stderr"], f["code"], f["files"])
        self.assertIn("1000000 maximum", e.exception.text)

    def test_no_output_is_an_error_not_a_zero(self):
        for harness in OWN:
            with self.subTest(harness=harness), self.assertRaises(C.ClientError):
                C.CLIENTS[harness]("m").parse("", "segmentation fault", 139, {})


class Commands(unittest.TestCase):
    P, E = "/io/prompt.txt", "/io/export.json"

    def test_claude(self):
        c = C.Claude("claude-haiku-5-5")
        tail = ["--strict-mcp-config", "--disable-slash-commands", "--permission-prompts", "none"]
        self.assertEqual(c.command(self.P, session="S"),
                         ["claude", "-p", "--output-format", "json", "--model", "claude-haiku-5-5", "--effort", "low",
                          "--session-id", "S", *tail])
        self.assertEqual(c.command(self.P, resume="S"),
                         ["claude", "-p", "--output-format", "json", "--model", "claude-haiku-5-5", "--effort", "low",
                          "--resume", "S", *tail])
        self.assertEqual(c.prompt_mode, "stdin")
        for argv in (c.command(self.P, session="S"), c.command(self.P, resume="S")):
            self.assertNotIn("--bare", argv)
            self.assertNotIn("--no-session-persistence", argv)
            self.assertNotIn("--mcp-config", argv)

    def test_codex(self):
        c = C.Codex("gpt-6-luna")
        cfg = ["-c", 'cli_auth_credentials_store="file"', "-c", 'model_reasoning_effort="low"']
        self.assertEqual(c.command(self.P), ["codex", "exec", "--json", "--skip-git-repo-check", "-m", "gpt-6-luna", *cfg,
                                             "-s", "read-only", "-"])
        self.assertEqual(c.command(self.P, resume="T"), ["codex", "exec", "resume", "T", "--json", "--skip-git-repo-check",
                                                         "-m", "gpt-6-luna", *cfg, "-"])
        self.assertTrue(c.cumulative)

    def test_devin(self):
        c = C.Devin("claude-haiku-5-5-low")
        files = {"export": (self.E, False)}
        self.assertEqual(c.command(self.P, files=files),
                         ["devin", "--process-model", "in-process", "--model", "claude-haiku-5-5-low", "--prompt-file", self.P,
                          "-p", "--respect-workspace-trust", "false", "--export", self.E])
        self.assertEqual(c.command(self.P, resume="surf-sleep", files=files),
                         ["devin", "--process-model", "in-process", "-r", "surf-sleep", "--prompt-file", self.P,
                          "-p", "--respect-workspace-trust", "false", "--export", self.E])

    def test_muse(self):
        c = C.Muse("muse-wonder-1.0")
        want = ["muse", "exec", "--json", "--model", "muse-wonder-1.0", "--reasoning-effort", "low", "--session-id", "U",
                "--prompt-file", self.P]
        self.assertEqual(c.command(self.P, session="U"), want)
        self.assertEqual(c.command(self.P, resume="U"), want)

    def test_a_run_may_set_only_what_the_client_allows(self):
        self.assertEqual(C.Claude("m", settings={"CLAUDE_CODE_PROMPT_CACHE_TTL": "5m"}).settings,
                         {"CLAUDE_CODE_PROMPT_CACHE_TTL": "5m"})
        with self.assertRaises(SystemExit):
            C.Claude("m", settings={"ANTHROPIC_BASE_URL": "http://x"})
        with self.assertRaises(SystemExit):
            C.Codex("m", settings={"CLAUDE_CODE_PROMPT_CACHE_TTL": "5m"})


# What the caller's shell may hold and no own client may get.
FORBIDDEN = {"ANTHROPIC_API_KEY": "a", "ANTHROPIC_AUTH_TOKEN": "a", "OPENAI_API_KEY": "a", "OPENROUTER_API_KEY": "a",
             "ANTHROPIC_BASE_URL": "http://x", "OPENAI_BASE_URL": "http://x", "HTTPS_PROXY": "http://x", "HTTP_PROXY": "http://x",
             "CLAUDE_CODE_PROMPT_CACHE_TTL": "5m", "FORCE_PROMPT_CACHING_5M": "1", "ENABLE_PROMPT_CACHING_1H": "1",
             "CLAUDE_CODE_OAUTH_TOKEN": "a", "CACHE_PROBE_KEY": "a", "CLAUDE_CONFIG_DIR": "/elsewhere", "CODEX_HOME": "/elsewhere",
             "XDG_CONFIG_HOME": "/elsewhere", "DEVIN_MODEL": "x", "DEVIN_PERMISSION_MODE": "dangerous"}
BASE = {"PATH": "/usr/bin", "HOME": "/h", "USER": "u", "LANG": "C", "TERM": "xterm", "TMPDIR": "/t", "SHELL": "/bin/zsh",
        **FORBIDDEN}


class Environment(unittest.TestCase):
    def test_only_the_allow_list_and_the_folder(self):
        with tempfile.TemporaryDirectory() as home:
            expected = {
                "claude": {"CLAUDE_CONFIG_DIR": home, "DISABLE_AUTOUPDATER": "1"},
                "codex": {"CODEX_HOME": home},
                "devin": {"XDG_CONFIG_HOME": home + "/config", "XDG_DATA_HOME": home + "/data", "XDG_STATE_HOME": home + "/state",
                          "XDG_CACHE_HOME": home + "/cache", "DEVIN_SESSIONS_DIR": home + "/sessions"},
                "muse": {"XDG_CONFIG_HOME": home + "/config", "XDG_DATA_HOME": home + "/data", "XDG_STATE_HOME": home + "/state",
                         "XDG_CACHE_HOME": home + "/cache", "MUSE_NO_AUTO_UPDATE": "1"},
            }
            allowed = {k: BASE[k] for k in C.ALLOW}
            for harness in OWN:
                with self.subTest(harness=harness):
                    env = C.CLIENTS[harness]("m").environment(home, base=BASE)
                    self.assertEqual(env, {**allowed, **expected[harness]})

    def test_muse_gets_its_key_and_nothing_else(self):
        env = C.Muse("m").environment("/s", base={**BASE, "META_API_KEY": "k"})
        self.assertEqual(env["META_API_KEY"], "k")
        for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "OPENAI_BASE_URL", "HTTPS_PROXY"):
            self.assertNotIn(k, env)
        self.assertNotIn("META_API_KEY", C.Claude("m").environment("/s", base={**BASE, "META_API_KEY": "k"}))

    def test_a_setting_the_run_makes_reaches_the_client(self):
        env = C.Claude("m", settings={"CLAUDE_CODE_PROMPT_CACHE_TTL": "5m"}).environment("/s", base={**BASE, "CLAUDE_CODE_PROMPT_CACHE_TTL": "1h"})
        self.assertEqual(env["CLAUDE_CODE_PROMPT_CACHE_TTL"], "5m")
        self.assertNotIn("CLAUDE_CODE_PROMPT_CACHE_TTL", C.Claude("m").environment("/s", base=BASE))


class SessionRuns(unittest.TestCase):
    """Session against a fake runner: the prompt reaches the client, the files are read and removed, the work folder
    stays empty."""

    def test_claude_prompt_on_stdin_and_handle(self):
        f = load((os.path.join(FIXTURES, "claude", "prime.json")))
        seen = {}

        def run(argv, env, cwd, stdin, timeout):
            seen.update(argv=argv, stdin=stdin.read(), cwd=cwd, env=env)
            return f["code"], f["stdout"], f["stderr"]
        with tempfile.TemporaryDirectory() as tmp:
            s = C.Session(C.Claude("claude-haiku-5-5"), env={"PATH": "/usr/bin"}, io=tmp + "/io", work=tmp + "/work", run=run)
            handle, u = s.start("the prompt")
            self.assertEqual(seen["stdin"], "the prompt")
            self.assertEqual(seen["cwd"], tmp + "/work")
            self.assertEqual(u.cached, 18000)
            self.assertEqual(handle, f["expect"]["handle"])
            self.assertEqual(os.listdir(tmp + "/io"), [])
            self.assertEqual(os.listdir(tmp + "/work"), [])
            self.assertEqual(s.plan(), ["claude", "-p", "--output-format", "json", "--model", "claude-haiku-5-5", "--effort",
                                        "low", "--session-id", "<session>", "--strict-mcp-config", "--disable-slash-commands",
                                        "--permission-prompts", "none", "<", "<prompt>"])

    def test_devin_export_read_and_removed(self):
        f = load((os.path.join(FIXTURES, "devin", "warm.json")))

        def run(argv, env, cwd, stdin, timeout):
            prompt = argv[argv.index("--prompt-file") + 1]
            with open(prompt) as p:
                self.assertEqual(p.read(), "check")
            with open(argv[argv.index("--export") + 1], "w") as out:
                out.write(f["files"]["export"])
            return 0, "OK", ""
        with tempfile.TemporaryDirectory() as tmp:
            s = C.Session(C.Devin("claude-haiku-5-5-low"), env={}, io=tmp + "/io", work=tmp + "/work", run=run)
            u = s.resume("surf-sleep", "check")
            self.assertEqual((u.cached, u.calls), (34470, 1))
            self.assertEqual(os.listdir(tmp + "/io"), [])
            self.assertEqual(s.plan(resume="surf-sleep"),
                             ["devin", "--process-model", "in-process", "-r", "<session>", "--prompt-file", "<prompt>", "-p",
                              "--respect-workspace-trust", "false", "--export", "<export>"])


if __name__ == "__main__":
    unittest.main()
