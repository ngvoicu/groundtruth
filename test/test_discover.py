"""harness/discover.py and harness/listed_schema.py (step G1, Provimux's model-lists.md 9.1 and 10): discovery of each
login's offered models into listed.json, from a saved Provimux answer or a fake Provimux on a free local port. Nothing
is sent anywhere else: every connection a test opens is recorded and checked.

    python3 -m unittest discover -s test -p "test_*.py"
"""
import contextlib
import copy
import http.server
import io
import json
import os
import plistlib
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "harness"))
import discover as D  # noqa: E402
import listed_schema as S  # noqa: E402

FIX = os.path.join(HERE, "fixtures", "discovery")
ANSWER = os.path.join(FIX, "provimux-model-lists-live.json")
YESTERDAY = os.path.join(FIX, "listed-yesterday.json")
TODAY = "2026-11-24"
KEY = "test-management-key-0123456789"


def load(path):
    with open(path) as f:
        return json.load(f)


def read(path):
    with open(path) as f:
        return f.read()


def dump(doc, path):
    with open(path, "w") as f:
        json.dump(doc, f)


class Connections:
    """Records every outgoing connection; refuses any that is not to the allowed local port."""

    def __init__(self, allowed_port=None):
        self.allowed, self.seen = allowed_port, []

    @contextlib.contextmanager
    def watching(self):
        real = socket.socket.connect

        def connect(sock, address):
            self.seen.append(address)
            if self.allowed is None or address[1] != self.allowed or address[0] not in ("127.0.0.1", "::1"):
                raise ConnectionRefusedError("the test allows no such connection")
            return real(sock, address)
        socket.socket.connect = connect
        try:
            yield self
        finally:
            socket.socket.connect = real


class FakeProvimux:
    """A Provimux on a free port of 127.0.0.1 that answers the fixture (or a status) and records each request."""

    def __init__(self, body=None, status=200):
        self.requests = []
        outer = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                outer.requests.append({"path": self.path, "auth": self.headers.get("Authorization")})
                data = json.dumps(body if body is not None else load(ANSWER)).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()


class Base(unittest.TestCase):
    def setUp(self):
        # Never the Mac's own night folder, Provimux address or key.
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        for name in ("GROUNDTRUTH_CLIENT_HOME", "CPA_BASE_URL", "CPA_MGMT_KEY"):
            os.environ.pop(name, None)
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        self.out = os.path.join(self.dir, "listed.json")
        self.log = os.path.join(self.dir, "discovery.log")

    def tearDown(self):
        self.tmp.cleanup()

    def yesterday(self):
        with open(self.out, "w") as f:
            f.write(D.text_of(load(YESTERDAY)))

    def args(self, *extra, answer=ANSWER, base=None):
        argv = ["--out", self.out, "--log", self.log, "--date", TODAY]
        if answer:
            argv += ["--answer", answer]
        if base:
            argv += ["--base-url", base]
        return D.parser().parse_args(argv + list(extra))

    def run_quiet(self, args, **kw):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code, words = D.run(args, **kw)
        return code, words, err.getvalue()

    def written(self):
        return load(self.out)


class FromTheAnswer(Base):
    def test_two_logins_of_one_type_are_joined_and_named_by_devin_s_own_ids(self):
        self.yesterday()
        code, words, _ = self.run_quiet(self.args())
        self.assertEqual(code, 0, words)
        devin = self.written()["providers"]["devin"]
        self.assertEqual((devin["date"], devin["client"]), (TODAY, "provimux"))
        # login a: argon, neon, swe-2; login b: opus, argon, swe-2. The union, by Devin's ids (no devin/ prefix).
        self.assertEqual([m["id"] for m in devin["models"]], ["claude-opus-5-5", "gemini-4-argon", "gemini-4-neon", "swe-2"])
        argon = devin["models"][1]
        self.assertEqual(argon, {"id": "gemini-4-argon", "name": "Gemini 4 Argon", "context_window": 1048576,
                                 "max_output": 65536, "input_modalities": ["text", "image"],
                                 "reasoning": {"levels": ["low", "medium", "high"]}})
        # The two logins state swe-2's window differently: neither is written; what they agree on is.
        swe = devin["models"][3]
        self.assertNotIn("context_window", swe)
        self.assertEqual(swe["reasoning"], {"levels": ["low", "high", "max-fast"]})
        self.assertIn("swe-2 context_window", read(self.log))

    def test_each_login_type_goes_to_its_listing_and_the_others_are_not_written(self):
        code, _, _ = self.run_quiet(self.args())
        self.assertEqual(code, 0)
        providers = self.written()["providers"]
        # No earlier file: only the types with a held live list today. Gemini keys and Vertex have no listed listing.
        self.assertEqual(sorted(providers), ["claude-subscription", "devin", "openai-codex"])
        self.assertEqual(len(providers["openai-codex"]["models"]), 3)
        # A list that states no output limit or levels states nothing: no empty list, no zero.
        sol = providers["openai-codex"]["models"][0]
        self.assertNotIn("max_output", sol)
        self.assertNotIn("output_modalities", sol)

    def test_a_login_without_a_live_list_adds_nothing_and_its_provider_keeps_yesterday_s_part(self):
        self.yesterday()
        before = load(YESTERDAY)["providers"]
        code, _, _ = self.run_quiet(self.args())
        self.assertEqual(code, 0)
        after = self.written()["providers"]
        # Meta's only login has no live list (a 503): its part and date are yesterday's, unchanged.
        self.assertEqual(after["meta-subscription"], before["meta-subscription"])
        # Devin's third login is disabled (and has no list): it does not count; the part is the two others', today's.
        self.assertEqual(after["devin"]["date"], TODAY)
        self.assertIn("meta-subscription: 1 of 1 enabled logins have no live list today", read(self.log))

    def test_a_list_provimux_no_longer_holds_is_not_read(self):
        answer = load(ANSWER)
        for row in answer["logins"]:
            if row["provider"] == "claude":
                row["live"]["held"], row["live"]["expired"] = False, True
        path = os.path.join(self.dir, "answer.json")
        dump(answer, path)
        self.run_quiet(self.args(answer=path))
        self.assertNotIn("claude-subscription", self.written()["providers"])

    def test_a_list_older_than_the_part_already_written_keeps_the_part(self):
        later = load(YESTERDAY)
        later["providers"]["devin"]["date"] = "2026-11-25"
        with open(self.out, "w") as f:
            f.write(D.text_of(later))
        self.run_quiet(self.args())
        self.assertEqual(self.written()["providers"]["devin"], later["providers"]["devin"])

    def test_the_part_s_date_is_the_oldest_of_the_joined_lists(self):
        answer = load(ANSWER)
        for row in answer["logins"]:
            if row["auth_index"] == "b39e04c6f1d7a218":
                row["live"]["fetched_at"] = "2026-11-22T23:59:00Z"
        path = os.path.join(self.dir, "answer.json")
        dump(answer, path)
        self.run_quiet(self.args(answer=path))
        self.assertEqual(self.written()["providers"]["devin"]["date"], "2026-11-22")

    def test_an_id_the_site_would_refuse_is_left_out_and_the_rest_is_written(self):
        answer = load(ANSWER)
        devin = next(r for r in answer["logins"] if r["auth_index"] == "a8d167b7d82c8c15")
        devin["live_list"].append({"id": "devin/Big-Model", "display_name": None, "context": None, "output": None,
                                   "input_modalities": [], "output_modalities": [], "reasoning_levels": []})
        path = os.path.join(self.dir, "answer.json")
        dump(answer, path)
        code, _, _ = self.run_quiet(self.args(answer=path))
        self.assertEqual(code, 0)
        self.assertNotIn("Big-Model", json.dumps(self.written()))
        self.assertIn("left out Big-Model: not a model id", read(self.log))

    def test_the_same_answer_twice_leaves_the_file_as_it_was(self):
        self.yesterday()
        self.run_quiet(self.args())
        first = read(self.out)
        code, words, _ = self.run_quiet(self.args())
        self.assertEqual((code, read(self.out)), (0, first))
        self.assertIn("(unchanged)", words)


class Ages(Base):
    def test_a_provider_older_than_three_days_is_an_ask_in_the_log_and_the_last_words(self):
        self.yesterday()
        code, words, _ = self.run_quiet(self.args())
        self.assertEqual(code, 0)
        log = read(self.log)
        for provider, days in (("antigravity", 5), ("meta-subscription", 1), ("devin", 0)):
            self.assertRegex(log, rf"age: {provider} {days} days?\b")
        ask = "ASK: discovery has no fresh list for antigravity: 5 days old (more than 3)"
        self.assertIn(ask, log)
        self.assertIn(ask, words)
        self.assertNotIn("ASK: discovery has no fresh list for meta-subscription", words)
        self.assertTrue(words.splitlines()[0].endswith("1 ask"))
        # The part is kept as it was: an ask, not a deletion.
        self.assertEqual(self.written()["providers"]["antigravity"]["date"], "2026-11-19")

    def test_three_days_is_not_yet_an_ask(self):
        self.yesterday()
        args = self.args()
        args.date = "2026-11-22"  # antigravity's part (11-19) is 3 days old
        _, words, _ = self.run_quiet(args)
        self.assertNotIn("ASK", words)

    def test_provimux_unreachable_keeps_the_file_and_still_reports_ages_and_asks(self):
        self.yesterday()
        before = read(self.out)
        with socket.socket() as s:  # a free port nobody listens on
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        conns = Connections(allowed_port=port)
        with conns.watching():
            code, words, _ = self.run_quiet(self.args(answer=None, base=f"http://127.0.0.1:{port}"),
                                            key_finder=lambda: KEY)
        self.assertEqual(code, 1)
        self.assertIn("Provimux could not be reached", words)
        self.assertIn("ASK: discovery has no fresh list for antigravity", words)
        self.assertEqual(read(self.out), before)


class Schema(unittest.TestCase):
    def good(self):
        return load(YESTERDAY)

    def test_the_fixtures_and_a_written_file_pass(self):
        self.assertEqual(S.validate(self.good()), [])

    def test_a_field_outside_the_schema_is_refused_at_every_level(self):
        cases = [
            lambda d: d.__setitem__("generated_by", "x"),
            lambda d: d["providers"]["devin"].__setitem__("logins", 2),
            lambda d: d["providers"]["devin"]["models"][0].__setitem__("first_seen", "2026-11-20"),
            lambda d: d["providers"]["devin"]["models"][0].__setitem__("reasoning", {"levels": ["low"], "effort": "x"}),
        ]
        for change in cases:
            doc = self.good()
            change(doc)
            errors = S.validate(doc)
            self.assertTrue(any("is not in the schema" in e for e in errors), errors)

    def test_identity_shapes_are_refused_wherever_they_are(self):
        for change in (
            lambda d: d["providers"]["devin"]["models"][0].__setitem__("email", "office@providers.dev"),
            lambda d: d["providers"]["devin"]["models"][0].__setitem__("name", "office@providers.dev"),
            lambda d: d["providers"]["devin"]["models"][0].__setitem__("id", "devin-login-b.json"),
            lambda d: d["providers"]["devin"]["models"][0].__setitem__("description", "token sk-abcdefabcdefabcdef"),
            lambda d: d["providers"]["devin"].__setitem__("client", "a8d167b7d82c8c15a8d167b7d82c8c15"),
        ):
            doc = self.good()
            change(doc)
            self.assertNotEqual(S.validate(doc), [])

    def test_other_shapes_are_refused(self):
        for change in (
            lambda d: d.__setitem__("schema", 2),
            lambda d: d["providers"]["devin"].__setitem__("models", []),
            lambda d: d["providers"]["devin"].__setitem__("date", "24.11.2026"),
            lambda d: d["providers"]["devin"]["models"].append({"id": "swe-2"}),
            lambda d: d["providers"]["devin"]["models"][0].__setitem__("context_window", 0),
            lambda d: d["providers"]["devin"]["models"][0].__setitem__("hidden", "no"),
            lambda d: d["providers"].__setitem__("Devin Login", d["providers"]["devin"]),
        ):
            doc = self.good()
            change(doc)
            self.assertNotEqual(S.validate(doc), [], doc)

    def test_the_command_ci_runs_refuses_a_bad_file_and_passes_a_good_or_absent_one(self):
        cmd = [sys.executable, os.path.join(ROOT, "harness", "listed_schema.py")]
        with tempfile.TemporaryDirectory() as t:
            path = os.path.join(t, "listed.json")
            self.assertEqual(subprocess.run(cmd + [path], capture_output=True).returncode, 0)  # absent
            dump(self.good(), path)
            self.assertEqual(subprocess.run(cmd + [path], capture_output=True).returncode, 0)
            doc = self.good()
            doc["providers"]["devin"]["models"][0]["account"] = "login-b"
            dump(doc, path)
            r = subprocess.run(cmd + [path], capture_output=True, text=True)
            self.assertEqual(r.returncode, 1)
            self.assertIn("field 'account' is not in the schema", r.stdout)

    def test_ci_and_the_commit_hook_run_it(self):
        self.assertIn("python3 harness/listed_schema.py listed.json",
                      read(os.path.join(ROOT, ".github", "workflows", "ci.yml")))
        self.assertIn('(cd "$tmp" && python3 harness/listed_schema.py listed.json)', read(os.path.join(ROOT, "scripts", "pre-commit")))

    def test_discovery_does_not_write_over_a_file_that_fails_its_schema(self):
        with tempfile.TemporaryDirectory() as t:
            out = os.path.join(t, "listed.json")
            doc = self.good()
            doc["providers"]["devin"]["models"][0]["first_seen"] = "2026-11-20"
            dump(doc, out)
            before = read(out)
            args = D.parser().parse_args(["--answer", ANSWER, "--out", out, "--log", os.path.join(t, "l"),
                                          "--date", TODAY])
            with contextlib.redirect_stderr(io.StringIO()):
                code, words = D.run(args)
            self.assertEqual(code, 1)
            self.assertIn("does not pass its schema", words)
            self.assertEqual(read(out), before)


class Identity(Base):
    def identity_values(self):
        values = set()
        for row in load(ANSWER)["logins"]:
            values.add(row["auth_index"])
            values.update(v for v in row["login"].values() if v)
        return values

    def test_no_identity_field_of_the_answer_is_ever_written(self):
        self.yesterday()
        self.run_quiet(self.args())
        text = read(self.out)
        for value in self.identity_values():
            self.assertNotIn(value, text)
        for word in ("auth_index", "login", "email", "label", "registered_models", "learned_models", "fetched_at",
                     "last_failure", "disabled", "source"):
            self.assertNotIn(f'"{word}"', text)

    def test_identity_smuggled_into_a_vendor_s_entry_is_not_written(self):
        answer = load(ANSWER)
        row = next(r for r in answer["logins"] if r["provider"] == "claude")
        entry = row["live_list"][0]
        entry.update({"email": "office@providers.dev", "account_id": "acct-123456", "owner": "login-b"})
        row["live_list"][1]["display_name"] = "office@providers.dev"
        row["live_list"][2]["input_modalities"] = ["text", "devin-login-b.json"]
        path = os.path.join(self.dir, "answer.json")
        dump(answer, path)
        code, _, _ = self.run_quiet(self.args(answer=path))
        self.assertEqual(code, 0)
        text = read(self.out)
        for value in ("office@providers.dev", "acct-123456", "login-b", "devin-login-b.json", "account_id"):
            self.assertNotIn(value, text)
        # The entry whose name is an e-mail of the answer is dropped whole; the others stay.
        ids = [m["id"] for m in self.written()["providers"]["claude-subscription"]["models"]]
        self.assertEqual(ids, ["claude-haiku-5-5", "claude-sonnet-5-5"])

    def test_a_label_found_in_a_model_s_name_drops_that_model_only(self):
        answer = load(ANSWER)
        row = next(r for r in answer["logins"] if r["provider"] == "claude")
        row["login"]["label"] = "Opus 5.5"
        path = os.path.join(self.dir, "answer.json")
        dump(answer, path)
        code, words, _ = self.run_quiet(self.args(answer=path))
        self.assertEqual(code, 0, words)
        ids = [m["id"] for m in self.written()["providers"]["claude-subscription"]["models"]]
        self.assertEqual(ids, ["claude-haiku-5-5", "claude-sonnet-5-5"])
        self.assertIn("left out a model whose id or name holds an identity value (not shown)", read(self.log))
        self.assertNotIn("Opus 5.5", read(self.log))

    def test_the_management_key_is_never_printed_or_logged(self):
        with FakeProvimux() as fake:
            out, err = io.StringIO(), io.StringIO()
            with Connections(fake.port).watching(), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code, words = D.run(self.args(answer=None, base=f"http://127.0.0.1:{fake.port}"),
                                    key_finder=lambda: KEY)
        self.assertEqual(code, 0, words)
        for text in (out.getvalue(), err.getvalue(), words, read(self.log), read(self.out)):
            self.assertNotIn(KEY, text)


class NothingSentAnywhereElse(Base):
    def test_one_local_request_to_provimux_and_no_other_connection(self):
        with FakeProvimux() as fake:
            conns = Connections(allowed_port=fake.port)
            with conns.watching():
                code, words, _ = self.run_quiet(self.args(answer=None, base=f"http://127.0.0.1:{fake.port}"),
                                                key_finder=lambda: KEY)
        self.assertEqual(code, 0, words)
        self.assertEqual(conns.seen, [("127.0.0.1", fake.port)])
        self.assertEqual(fake.requests, [{"path": "/v8/management/provimux/model-lists?view=live",
                                          "auth": "Bearer " + KEY}])
        self.assertEqual(sorted(self.written()["providers"]), ["claude-subscription", "devin", "openai-codex"])

    def test_a_host_that_is_not_this_mac_is_refused_before_any_connection(self):
        for base in ("https://api.x.ai", "http://192.168.1.10:8317", "http://provimux.example:8317",
                     "file:///etc/hosts"):
            conns = Connections()
            with conns.watching():
                code, words, _ = self.run_quiet(self.args(answer=None, base=base), key_finder=lambda: KEY)
            self.assertEqual(code, 1, base)
            self.assertEqual(conns.seen, [], base)

    def test_a_saved_answer_opens_no_connection_and_reads_no_key(self):
        def no_key():
            raise AssertionError("a saved answer needs no key")
        conns = Connections()
        with conns.watching():
            code, _, _ = self.run_quiet(self.args(), key_finder=no_key)
        self.assertEqual((code, conns.seen), (0, []))

    def test_an_error_answer_is_reported_by_its_status_only(self):
        with FakeProvimux(body={"error": "secret-looking text office@providers.dev"}, status=401) as fake:
            with Connections(fake.port).watching():
                code, words, _ = self.run_quiet(self.args(answer=None, base=f"http://127.0.0.1:{fake.port}"),
                                                key_finder=lambda: KEY)
        self.assertEqual(code, 1)
        self.assertIn("HTTP 401", words)
        self.assertNotIn("secret-looking", words + read(self.log))

    def test_an_answer_without_view_live_is_refused(self):
        answer = load(ANSWER)
        for row in answer["logins"]:
            row.pop("live_list")
        path = os.path.join(self.dir, "answer.json")
        dump(answer, path)
        code, words, _ = self.run_quiet(self.args(answer=path))
        self.assertEqual(code, 1)
        self.assertIn("view=live", words)

    def test_the_command_has_no_vendor_address(self):
        source = read(os.path.join(ROOT, "harness", "discover.py"))
        for host in ("anthropic.com", "openai.com", "chatgpt.com", "codeium.com", "githubcopilot", "googleapis",
                     "meta.ai", "x.ai", "kimi.com", "providers.dev/api"):
            self.assertNotIn(host, source)


class Shrinking(Base):
    def test_a_file_providers_dev_would_refuse_as_shrunk_is_not_written(self):
        big = load(YESTERDAY)
        big["providers"]["devin"]["models"] = [{"id": f"m-{n}"} for n in range(40)]
        with open(self.out, "w") as f:
            f.write(D.text_of(big))
        before = read(self.out)
        code, words, _ = self.run_quiet(self.args())
        self.assertEqual(code, 1)
        self.assertIn("lost more than 40 %", words)
        self.assertEqual(read(self.out), before)


class Publish(Base):
    def test_without_publish_nothing_is_committed_and_the_default_file_is_the_current_folder_s(self):
        repo = os.path.join(self.dir, "repo")
        subprocess.run(["git", "init", "-q", "-b", "main", repo], check=True)
        cwd = os.getcwd()
        os.chdir(repo)
        try:
            args = D.parser().parse_args(["--answer", ANSWER, "--log", self.log, "--date", TODAY])
            code, _, _ = self.run_quiet(args)
        finally:
            os.chdir(cwd)
        self.assertEqual(code, 0)
        self.assertTrue(os.path.exists(os.path.join(repo, "listed.json")))
        r = subprocess.run(["git", "-C", repo, "log", "--oneline"], capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)  # no commit at all

    def test_the_real_scan_passes_on_a_written_file(self):
        self.yesterday()
        self.run_quiet(self.args())
        env = dict(os.environ, SCAN_CLIENT_KEYS=os.path.join(self.dir, "none"),
                   SCAN_KEYS_FILE=os.path.join(self.dir, "none"), SCAN_CONFIG=os.path.join(self.dir, "none"),
                   SCAN_LOGINS=os.path.join(self.dir, "none", "*.json"),
                   SCAN_FINGERPRINTS=os.path.join(self.dir, "none"))
        env.pop("GROUNDTRUTH_CLIENT_HOME", None)
        r = subprocess.run([sys.executable, os.path.join(ROOT, "harness", "scan_secrets.py"), self.out],
                           capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("CLEAN", r.stdout)


class Agent(unittest.TestCase):
    LABEL = "dev.providers.groundtruth.discovery"
    PLIST = os.path.join(ROOT, "scripts", "launchd", LABEL + ".plist")
    INSTALL = os.path.join(ROOT, "scripts", "install-discovery.sh")

    def test_the_template_runs_discovery_daily_at_22_30(self):
        with open(self.PLIST, "rb") as f:
            p = plistlib.load(f)
        self.assertEqual(p["Label"], self.LABEL)
        self.assertEqual(p["StartCalendarInterval"], {"Hour": 22, "Minute": 30})
        self.assertEqual(p["ProgramArguments"][1:], ["-B", "harness/discover.py", "__ARG1__", "__ARG2__"])
        self.assertFalse(p["RunAtLoad"])
        self.assertNotIn("CPA_MGMT_KEY", json.dumps(p["EnvironmentVariables"]))

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
            r = subprocess.run([self.INSTALL, "--print"], env=env, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(plistlib.loads(r.stdout.encode())["ProgramArguments"][2:],
                             ["harness/discover.py", "--out", os.path.join(home, "listed.json")])
            r = subprocess.run([self.INSTALL, "--owner-ok", "--publish", "--target", target], env=env,
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            with open(os.path.join(target, self.LABEL + ".plist"), "rb") as f:
                p = plistlib.load(f)
            self.assertEqual(p["ProgramArguments"][2:], ["harness/discover.py", "--publish"])
            self.assertEqual(p["WorkingDirectory"], os.path.realpath(ROOT))
            self.assertEqual(p["EnvironmentVariables"]["GROUNDTRUTH_CLIENT_HOME"], home)
            self.assertEqual(p["StandardOutPath"], os.path.join(home, "discovery.out.log"))
            self.assertEqual(p["StartCalendarInterval"], {"Hour": 22, "Minute": 30})


if __name__ == "__main__":
    unittest.main()
