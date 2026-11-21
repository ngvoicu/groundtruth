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
                "claude": {"CLAUDE_CONFIG_DIR": home, "DISABLE_AUTOUPDATER": "1", "CLAUDE_CODE_MAX_RETRIES": "0"},
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


class StateFolder(unittest.TestCase):
    """The state folder: <client-home>/<client id>, never an everyday folder, outside the repository, logged in."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = self.tmp.name
        self.user = os.path.join(t, "user")              # stands for the home folder; the real one is never read
        self.repo = os.path.join(t, "repo")
        self.base = os.path.join(t, "client-home")
        for d in (self.user, self.repo, self.base, os.path.join(self.base, "claude-code"), os.path.join(self.base, "muse-code")):
            os.makedirs(d)
        self.calls = []

    def tearDown(self):
        self.tmp.cleanup()

    STATUS = {"claude": '{"loggedIn": true, "authMethod": "claude.ai", "apiProvider": "firstParty", "subscriptionType": "max"}',
              "codex": "Logged in using ChatGPT", "devin": "Logged in", "muse": ""}

    def run_ok(self, code, out=None):
        def run(argv, env, cwd, stdin, timeout):
            self.calls.append((argv, env))
            return code, out if out is not None else self.STATUS[argv[0]], ""
        return run

    def folder(self, client, base, code=0, env=None, out=None):
        return C.state_folder(client, base, self.repo, user_home=self.user, run=self.run_ok(code, out), env=env)

    def test_a_logged_in_folder_is_accepted_and_checked_in_its_own_environment(self):
        home = self.folder(C.Claude("m"), self.base)
        self.assertEqual(home, os.path.realpath(os.path.join(self.base, "claude-code")))
        argv, env = self.calls[0]
        self.assertEqual(argv, ["claude", "auth", "status", "--json"])
        self.assertEqual(env["CLAUDE_CONFIG_DIR"], home)

    def test_required_and_must_exist(self):
        with self.assertRaisesRegex(SystemExit, "required"):
            self.folder(C.Claude("m"), None)
        with self.assertRaisesRegex(SystemExit, "does not exist"):
            self.folder(C.Codex("m"), self.base)

    def test_not_logged_in(self):
        with self.assertRaisesRegex(SystemExit, "refused: the status command exited 1"):
            self.folder(C.Claude("m"), self.base, code=1)
        with self.assertRaisesRegex(SystemExit, "refused: not logged in"):
            self.folder(C.Claude("m"), self.base, out='{"loggedIn": false}')

    def test_never_the_everyday_folder(self):
        os.makedirs(os.path.join(self.user, ".claude", "claude-code"))
        with self.assertRaisesRegex(SystemExit, "everyday"):
            self.folder(C.Claude("m"), os.path.join(self.user, ".claude"))
        # any client's and pi's: a Codex state folder under ~/.pi is refused too (it was accepted)
        os.makedirs(os.path.join(self.user, ".pi", "codex-cli"))
        with self.assertRaisesRegex(SystemExit, "everyday"):
            self.folder(C.Codex("m"), os.path.join(self.user, ".pi"))
        os.makedirs(os.path.join(self.user, ".config", "muse-code"))
        with self.assertRaisesRegex(SystemExit, "everyday"):
            self.folder(C.Muse("m"), os.path.join(self.user, ".config"), env={"META_API_KEY": "k"})

    def test_never_inside_the_repository(self):
        os.makedirs(os.path.join(self.repo, "state", "claude-code"))
        with self.assertRaisesRegex(SystemExit, "repository"):
            self.folder(C.Claude("m"), os.path.join(self.repo, "state"))

    def test_muse_needs_its_key(self):
        with self.assertRaisesRegex(SystemExit, "META_API_KEY"):
            self.folder(C.Muse("m"), self.base, env={})
        self.assertTrue(self.folder(C.Muse("m"), self.base, env={"META_API_KEY": "k"}).endswith("muse-code"))


class StateFolderReview(StateFolder):
    """Review findings 1 and 2: links out of the state folder, a Git checkout, a relative path, an API-key login."""

    def test_a_link_that_leaves_the_state_folder_is_refused_at_any_depth(self):
        everyday = os.path.join(self.user, ".codex", "sessions")
        os.makedirs(everyday)
        os.makedirs(os.path.join(self.base, "codex-cli", "deep"))
        os.symlink(everyday, os.path.join(self.base, "codex-cli", "deep", "sessions"))
        with self.assertRaisesRegex(SystemExit, "links that leave it: deep/sessions"):
            self.folder(C.Codex("m"), self.base)
        # a link that stays inside is fine
        os.remove(os.path.join(self.base, "codex-cli", "deep", "sessions"))
        os.symlink(os.path.join(self.base, "codex-cli", "deep"), os.path.join(self.base, "codex-cli", "here"))
        os.makedirs(os.path.join(self.base, "codex-cli", "x"), exist_ok=True)
        self.assertTrue(self.folder(C.Codex("m"), self.base))

    def test_never_inside_a_git_checkout(self):
        other = os.path.join(self.tmp.name, "other-checkout")
        os.makedirs(os.path.join(other, ".git"))
        os.makedirs(os.path.join(other, "state", "codex-cli"))
        with self.assertRaisesRegex(SystemExit, "Git checkout"):
            self.folder(C.Codex("m"), os.path.join(other, "state"))

    def test_a_relative_path_is_made_absolute(self):
        os.makedirs(os.path.join(self.base, "codex-cli"))
        cwd = os.getcwd()
        try:
            os.chdir(self.tmp.name)
            home = self.folder(C.Codex("m"), "client-home")
        finally:
            os.chdir(cwd)
        self.assertTrue(os.path.isabs(home))
        self.assertEqual(home, os.path.realpath(os.path.join(self.base, "codex-cli")))

    def test_an_api_key_login_is_refused(self):
        # the statuses the review used
        os.makedirs(os.path.join(self.base, "codex-cli"))
        with self.assertRaisesRegex(SystemExit, "API key"):
            self.folder(C.Codex("m"), self.base, out="Logged in using an API key")
        with self.assertRaisesRegex(SystemExit, "not a Claude subscription"):
            self.folder(C.Claude("m"), self.base, out='{"loggedIn":true,"authMethod":"api_key"}')
        with self.assertRaisesRegex(SystemExit, "not a Claude subscription"):
            self.folder(C.Claude("m"), self.base, out='{"loggedIn":true,"authMethod":"console"}')
        with self.assertRaisesRegex(SystemExit, "not Anthropic"):
            self.folder(C.Claude("m"), self.base, out='{"loggedIn":true,"authMethod":"claude.ai","apiProvider":"bedrock"}')
        with self.assertRaisesRegex(SystemExit, "Logged in using ChatGPT"):
            self.folder(C.Codex("m"), self.base, out="")
        self.assertTrue(self.folder(C.Codex("m"), self.base))
        self.assertTrue(self.folder(C.Claude("m"), self.base))


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


def fx(harness, case):
    return load(os.path.join(FIXTURES, harness, case + ".json"))


class Failures(unittest.TestCase):
    """Review finding 5: a failed or repeated check never parses as one successful request."""

    def test_codex_two_completed_turns_are_two_calls(self):
        out = fx("codex", "prime")["stdout"] + fx("codex", "warm")["stdout"]
        self.assertEqual(C.Codex("m").parse(out, "", 0, {}).calls, 2)

    def test_usage_with_a_failure_is_a_failure(self):
        cases = (("codex", fx("codex", "warm")["stdout"] + '{"type":"turn.failed","error":{"message":"usage limit"}}\n', "You've hit your usage limit", {}),
                 ("devin", "", "429 quota exceeded", fx("devin", "warm")["files"]),
                 ("muse", fx("muse", "warm")["stdout"] + '{"payload_type":"run.error","payload":{"message":"429 quota exceeded"}}\n', "429 quota exceeded", {}))
        for harness, out, err, files in cases:
            with self.subTest(harness=harness), self.assertRaises(C.Refused) as e:
                C.CLIENTS[harness]("m").parse(out, err, 1, files)
            self.assertEqual(e.exception.kind, "quota")

    def test_a_non_zero_exit_with_usage_is_a_failure(self):
        for harness in ("codex", "muse"):
            with self.subTest(harness=harness), self.assertRaises((C.ClientError, C.Refused)):
                C.CLIENTS[harness]("m").parse(fx(harness, "warm")["stdout"], "", 1, {})

    def test_devin_a_failed_resume_with_the_primings_export_is_a_failure(self):
        old = fx("devin", "prime")["files"]
        with self.assertRaises((C.ClientError, C.Refused)):
            C.Devin("m").parse("", "429 quota exceeded", 1, old)
        # exit 0, but the export holds no turn for the prompt just sent
        with self.assertRaisesRegex(C.ClientError, "not the prompt just sent"):
            C.Devin("m").parse("", "", 0, old, expect={"prompt": "Reply with OK only.", "session": "surf-sleep"})
        with self.assertRaisesRegex(C.ClientError, "not of the resumed one"):
            C.Devin("m").parse("", "", 0, fx("devin", "warm")["files"], expect={"prompt": "<check>", "session": "other"})
        u = C.Devin("m").parse("", "", 0, fx("devin", "warm")["files"], expect={"prompt": "<check>", "session": "surf-sleep"})
        self.assertEqual(u.calls, 1)

    def test_claude_switches_its_own_retries_off_and_says_so(self):
        env = C.Claude("m").environment("/s", base=BASE)
        self.assertEqual(env["CLAUDE_CODE_MAX_RETRIES"], "0")
        self.assertIn("CLAUDE_CODE_MAX_RETRIES=0", C.Claude.retries_note)


class Redaction(unittest.TestCase):
    """Review finding 3 (the drivers' part): a client's output reaches a public file only redacted."""

    CANARY = "reviewonly_opaque_" + "A23" * 8
    # Built here, so that this file holds no home path and no e-mail address itself (the scan reads it too).
    HOME = "/" + "Users/someone"
    MAIL = "a.person" + "@" + "example.com"
    STATE = "/Volumes/measure/campaign/" + "muse-code"

    def session(self, tmp, run, keep=None):
        return C.Session(C.Muse("m"), env={"META_API_KEY": self.CANARY, "HOME": self.HOME},
                         io=tmp + "/io", work=tmp + "/work", run=run, home=self.STATE, keep=keep)

    def test_errors_lose_the_child_only_key_and_the_paths(self):
        def run(argv, env, cwd, stdin, timeout):
            return 1, "", ("context overflow; credential=" + self.CANARY + " state=" + self.STATE + " "
                           "home=" + self.HOME + "/x mail=" + self.MAIL)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(C.Refused) as e:
                self.session(tmp, run).start("p")
        text = e.exception.text
        for leak in (self.CANARY, "/Volumes/measure/campaign", self.HOME, self.MAIL):
            self.assertNotIn(leak, text)
        self.assertIn("<secret>", text)

    def test_the_kept_raw_output_is_redacted_and_an_unknown_usage_event_is_kept(self):
        def run(argv, env, cwd, stdin, timeout):
            return 0, '{"payload_type":"run.usage.v2","payload":{"calls":1,"key":"' + self.CANARY + '"}}\n', ""
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(C.ClientError, "usage-like events: .*run.usage.v2") as e:
                self.session(tmp, run, keep=tmp + "/keep").start("p")
            self.assertNotIn(self.CANARY, str(e.exception))
            kept = sorted(os.listdir(tmp + "/keep"))
            self.assertEqual(kept, ["001-start-stderr.txt", "001-start-stdout.txt"])
            with open(tmp + "/keep/001-start-stdout.txt") as f:
                text = f.read()
            self.assertIn("run.usage.v2", text)
            self.assertNotIn(self.CANARY, text)

    def test_devins_export_is_kept_for_the_smoke_run(self):
        f = fx("devin", "prime")

        def run(argv, env, cwd, stdin, timeout):
            with open(argv[argv.index("--export") + 1], "w") as out:
                out.write(f["files"]["export"].replace("<prompt>", "the prompt"))
            return 0, "OK", ""
        with tempfile.TemporaryDirectory() as tmp:
            s = C.Session(C.Devin("m"), env={}, io=tmp + "/io", work=tmp + "/work", run=run, keep=tmp + "/keep")
            s.start("the prompt")
            self.assertIn("001-start-export.txt", os.listdir(tmp + "/keep"))
            self.assertEqual(os.listdir(tmp + "/io"), [])


if __name__ == "__main__":
    unittest.main()
