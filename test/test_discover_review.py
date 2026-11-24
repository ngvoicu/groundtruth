"""The review of discovery's first version (step G1): one class per finding, built from the reviewer's cases. Each
test fails on that version (831afc3) and passes now. Nothing leaves this Mac: fake Provimux servers on free loopback
ports, local bare repositories for GitHub, and every outgoing connection recorded.

    python3 -m unittest discover -s test -p "test_*.py"
"""
import contextlib
import fcntl
import http.server
import io
import json
import os
import plistlib
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


def load(path):
    with open(path) as f:
        return json.load(f)


def read(path):
    with open(path) as f:
        return f.read()


def dump(doc, path):
    with open(path, "w") as f:
        json.dump(doc, f)


def row(provider, entries, label=None, email=None, name=None, held=True, disabled=False):
    """A login row as Provimux 8.1.1-pmx.2 writes it with view=live (the reviewer's `row`)."""
    return {"auth_index": None, "provider": provider, "login": {"name": name, "email": email, "label": label},
            "disabled": disabled, "source": "live" if held else "built-in",
            "live": {"supported": True, "held": held, "expired": False,
                     "fetched_at": "2026-11-24T12:00:00Z" if held else None, "from_cache": False, "fetching": False,
                     "listed_models": len(entries) if held else None, "last_failure": None},
            "registered_models": len(entries), "learned_models": 0, "models": None,
            "live_list": entries if held else None}


def answer_of(*rows):
    return {"options": {"live_lists": True}, "logins": list(rows)}


class Server:
    """A local HTTP server that answers every GET with `respond(handler)` and records the requests."""

    def __init__(self, respond):
        self.requests = []
        outer = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                outer.requests.append({"path": self.path, "auth": self.headers.get("Authorization")})
                status, headers, body = respond(self)
                self.send_response(status)
                for k, v in headers.items():
                    self.send_header(k, v)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


def provimux(answer):
    return Server(lambda h: (200, {"Content-Type": "application/json"}, json.dumps(answer).encode()))


class Case(unittest.TestCase):
    def setUp(self):
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        for name in ("GROUNDTRUTH_CLIENT_HOME", "CPA_BASE_URL", "CPA_MGMT_KEY", "http_proxy", "HTTP_PROXY",
                     "https_proxy", "HTTPS_PROXY", "all_proxy", "ALL_PROXY", "no_proxy", "NO_PROXY"):
            os.environ.pop(name, None)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = self.tmp.name
        self.out = os.path.join(self.dir, "listed.json")
        self.log = os.path.join(self.dir, "discovery.log")

    def run_with(self, argv, **kw):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code, words = D.run(D.parser().parse_args(argv), **kw)
        return code, words

    def from_answer(self, answer, *extra):
        path = os.path.join(self.dir, "answer.json")
        dump(answer, path)
        return self.run_with(["--answer", path, "--out", self.out, "--log", self.log, "--date", TODAY, *extra])

    def yesterday(self):
        with open(self.out, "w") as f:
            f.write(read(YESTERDAY))


# --- finding 1: identity ---------------------------------------------------------------------------------------------

class Finding1Identity(Case):
    def test_a_model_whose_name_holds_a_login_s_label_is_dropped_and_the_value_never_logged(self):
        # The reviewer's privacy case: labels "Ada" (3 characters: not an identity value) and "Cedar".
        answer = answer_of(row("devin", [{"id": "m-one", "display_name": "Ada"}], label="Ada"),
                           row("claude", [{"id": "model-team-cedar", "display_name": "Cedar Preview"},
                                          {"id": "claude-plain", "display_name": "Plain"}], label="Cedar"))
        code, words = self.from_answer(answer)
        self.assertEqual(code, 0, words)
        text = read(self.out).lower()
        self.assertNotIn("cedar", text)
        self.assertEqual([m["id"] for m in load(self.out)["providers"]["claude-subscription"]["models"]],
                         ["claude-plain"])
        self.assertEqual(load(self.out)["providers"]["devin"]["models"][0]["id"], "m-one")
        self.assertIn("left out a model whose id or name holds an identity value", read(self.log))
        self.assertNotIn("Cedar", read(self.log))

    def test_e_mails_file_names_and_auth_index_drop_their_models_without_case(self):
        r = row("codex", [{"id": "gpt-ada-lovelace"}, {"id": "gpt-b", "display_name": "Codex-Team-Acme preview"},
                          {"id": "gpt-c", "display_name": "x 7f21c0d9e8b4a356"}, {"id": "gpt-plain"}],
                email="ada-lovelace" + "@" + "example.org", name="codex-team-acme.json")
        r["auth_index"] = "7F21C0D9E8B4A356"
        code, words = self.from_answer(answer_of(r))
        self.assertEqual(code, 0, words)
        self.assertEqual([m["id"] for m in load(self.out)["providers"]["openai-codex"]["models"]], ["gpt-plain"])

    def test_a_label_that_is_a_service_s_name_drops_nothing(self):
        # The reviewer's innocent label: a Devin login labelled "Devin". 831afc3 refused the whole file.
        code, words = self.from_answer(answer_of(row("devin", [{"id": "fixture-model", "display_name": "Devin SWE"}],
                                                     label="Devin")))
        self.assertEqual(code, 0, words)
        self.assertEqual(load(self.out)["providers"]["devin"]["models"][0]["id"], "fixture-model")

    def key_case(self, key, entry):
        answer = answer_of(row("codex", [entry, {"id": "gpt-plain"}]))
        server = provimux(answer)
        self.addCleanup(server.close)
        code, words = self.run_with(["--base-url", f"http://127.0.0.1:{server.port}", "--out", self.out,
                                     "--log", self.log, "--date", TODAY])
        self.assertEqual(code, 0, words)
        self.assertEqual(server.requests[0]["auth"], "Bearer " + key)
        self.assertNotIn(key.lower(), read(self.out).lower())
        self.assertNotIn(key, read(self.log) + words)
        self.assertEqual([m["id"] for m in load(self.out)["providers"]["openai-codex"]["models"]], ["gpt-plain"])

    def test_the_key_from_cpa_mgmt_key_drops_the_model_that_carries_it(self):
        key = "demo-key.unit-only-74"  # the reviewer's key-as-data case
        os.environ["CPA_MGMT_KEY"] = key
        self.key_case(key, {"id": "demo-model", "display_name": key})

    def test_the_key_from_the_key_file_drops_the_model_that_carries_it(self):
        home = os.path.join(self.dir, "home")
        os.makedirs(os.path.join(home, ".cli-proxy-api"))
        key = "file-key.unit-only-91"
        with open(os.path.join(home, ".cli-proxy-api", "keys.txt"), "w") as f:
            f.write(f"OTHER=1\nMGMT_KEY={key}\n")
        os.environ["HOME"] = home
        self.key_case(key, {"id": "model-" + key, "display_name": "A model"})


# --- finding 2: the key never leaves loopback ------------------------------------------------------------------------

class Finding2Loopback(Case):
    def test_a_redirect_is_refused_and_the_key_goes_nowhere_else(self):
        elsewhere = Server(lambda h: (200, {}, b'{"logins": []}'))
        self.addCleanup(elsewhere.close)
        redirecting = Server(lambda h: (302, {"Location": f"http://127.0.0.1:{elsewhere.port}/stolen"}, b""))
        self.addCleanup(redirecting.close)
        code, words = self.run_with(["--base-url", f"http://127.0.0.1:{redirecting.port}", "--out", self.out,
                                     "--log", self.log, "--date", TODAY], key_finder=lambda: "redirect-key-123456")
        self.assertEqual(code, 1)
        self.assertIn("HTTP 302", words)
        self.assertEqual(elsewhere.requests, [])

    def test_no_proxy_is_used_whatever_the_environment_says(self):
        proxy = Server(lambda h: (200, {}, b'{"logins": []}'))
        self.addCleanup(proxy.close)
        target = provimux(load(ANSWER))
        self.addCleanup(target.close)
        os.environ["http_proxy"] = os.environ["HTTP_PROXY"] = f"http://127.0.0.1:{proxy.port}"
        # urllib's default opener reads the proxies once and keeps them: start it afresh, as a new process would.
        import urllib.request
        urllib.request.install_opener(None)
        self.addCleanup(urllib.request.install_opener, None)
        code, words = self.run_with(["--base-url", f"http://127.0.0.1:{target.port}", "--out", self.out,
                                     "--log", self.log, "--date", TODAY], key_finder=lambda: "proxy-key-1234567")
        self.assertEqual(code, 0, words)
        self.assertEqual(proxy.requests, [])
        self.assertEqual(len(target.requests), 1)


# --- findings 3, 4 and 5: publish from discovery's own clone ---------------------------------------------------------

class Findings345Publish(Case):
    def git(self, repo, *args, check=True):
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        r = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, env=env)
        if check:
            self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip()

    def setUp(self):
        super().setUp()
        self.home = os.path.join(self.dir, "G")
        os.mkdir(self.home, 0o700)
        os.environ["GROUNDTRUTH_CLIENT_HOME"] = self.home
        # GitHub: a bare repository whose main holds yesterday's listed.json.
        self.github = os.path.join(self.dir, "github.git")
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", self.github], check=True)
        seed = os.path.join(self.dir, "seed")
        subprocess.run(["git", "clone", "-q", self.github, seed], check=True, capture_output=True)
        self.identity(seed)
        with open(os.path.join(seed, "listed.json"), "w") as f:
            f.write(read(YESTERDAY))
        with open(os.path.join(seed, "README.md"), "w") as f:
            f.write("groundtruth\n")
        self.git(seed, "add", "-A")
        self.git(seed, "commit", "-q", "-m", "start")
        self.git(seed, "push", "-q", "origin", "HEAD:main")
        # The owner's main checkout: dirty, with a night's unaudited file. Discovery must never touch it.
        self.main = os.path.join(self.dir, "main-checkout")
        subprocess.run(["git", "clone", "-q", self.github, self.main], check=True, capture_output=True)
        with open(os.path.join(self.main, "operator.txt"), "w") as f:
            f.write("work in progress\n")
        os.makedirs(os.path.join(self.main, "results", "night-2026-11-23"))
        with open(os.path.join(self.main, "results", "night-2026-11-23", "measure.jsonl"), "w") as f:
            f.write("{}\n")
        self.git(self.main, "add", "operator.txt")
        self.scan = [sys.executable, "-c", "print('1 files scanned: CLEAN')"]

    def identity(self, repo):
        self.git(repo, "config", "user.name", "someone else")
        self.git(repo, "config", "user.email", "office@providers.dev")

    def publish(self, *extra, answer=ANSWER, scan=None):
        cwd = os.getcwd()
        os.chdir(self.main)
        try:
            return self.run_with(["--answer", answer, "--log", self.log, "--date", TODAY, "--publish",
                                  "--upstream-url", self.github, *extra], scan=scan or self.scan)
        finally:
            os.chdir(cwd)

    def github_file(self):
        return json.loads(self.git(self.github, "show", "main:listed.json"))

    def test_it_commits_listed_json_alone_in_its_own_clone_as_discovery_and_pushes_github_only(self):
        before = self.git(self.main, "status", "--porcelain")
        head = self.git(self.main, "rev-parse", "HEAD")
        code, words = self.publish()
        self.assertEqual(code, 0, words)
        self.assertEqual(self.git(self.github, "log", "-1", "--format=%an <%ae>|%cn <%ce>|%s"),
                         "groundtruth discovery <office@providers.dev>|groundtruth discovery <office@providers.dev>|"
                         f"discovery: listed.json of {TODAY}")
        self.assertEqual(self.git(self.github, "show", "--name-only", "--format=", "main"), "listed.json")
        self.assertEqual(self.github_file()["providers"]["devin"]["date"], TODAY)
        clone = os.path.join(self.home, "discovery-repo")
        self.assertEqual(self.git(clone, "remote"), "upstream")
        # The main checkout is exactly as it was: same HEAD, same status, no listed.json written there.
        self.assertEqual(self.git(self.main, "status", "--porcelain"), before)
        self.assertEqual(self.git(self.main, "rev-parse", "HEAD"), head)
        self.assertEqual(json.loads(read(os.path.join(self.main, "listed.json"))), load(YESTERDAY))
        # The same day again: equal to GitHub's, no commit.
        code, words = self.publish()
        self.assertEqual(code, 0, words)
        self.assertIn("(unchanged)", words)
        self.assertEqual(self.git(self.github, "rev-list", "--count", "main"), "2")

    def test_a_stranded_local_state_of_the_clone_is_never_published(self):
        self.publish()
        clone = os.path.join(self.home, "discovery-repo")
        # A failed day left a local commit and a draft in the clone.
        with open(os.path.join(clone, "draft.txt"), "w") as f:
            f.write("draft\n")
        self.git(clone, "-c", "user.name=x", "-c", "user.email=office@providers.dev", "commit", "-q",
                 "--allow-empty", "-m", "stranded")
        with open(os.path.join(clone, "untracked.json"), "w") as f:
            f.write("{}\n")
        answer = load(ANSWER)
        for r in answer["logins"]:
            if r["provider"] == "codex":
                r["live_list"].append({"id": "gpt-6.3-new", "display_name": None, "context": None, "output": None,
                                       "input_modalities": [], "output_modalities": [], "reasoning_levels": []})
        path = os.path.join(self.dir, "answer2.json")
        dump(answer, path)
        code, words = self.publish(answer=path)
        self.assertEqual(code, 0, words)
        log = self.git(self.github, "log", "--format=%s", "main")
        self.assertNotIn("stranded", log)
        self.assertEqual(self.git(self.github, "show", "--name-only", "--format=", "main"), "listed.json")
        self.assertFalse(os.path.exists(os.path.join(clone, "untracked.json")))

    def test_out_is_refused_with_publish(self):
        code, words = self.publish("--out", os.path.join(self.dir, "x.json"))
        self.assertEqual(code, 1)
        self.assertIn("--out is refused", words)
        self.assertEqual(self.git(self.github, "rev-list", "--count", "main"), "1")

    def test_a_refused_push_is_redone_once_from_a_fresh_fetch(self):
        other = os.path.join(self.dir, "other")
        subprocess.run(["git", "clone", "-q", self.github, other], check=True, capture_output=True)
        self.identity(other)
        real, pushes = D.git, []

        def racing(repo, *args):
            if args[:1] == ("push",):
                pushes.append(args)
                if len(pushes) == 1:  # someone else pushes to GitHub just before discovery's first push
                    with open(os.path.join(other, "README.md"), "a") as f:
                        f.write("more\n")
                    self.git(other, "commit", "-qam", "meanwhile")
                    self.git(other, "push", "-q", "origin", "HEAD:main")
            return real(repo, *args)
        with mock.patch.object(D, "git", racing):
            code, words = self.publish()
        self.assertEqual(code, 0, words)
        self.assertEqual(len(pushes), 2)
        self.assertEqual(self.git(self.github, "log", "--format=%s", "main").splitlines()[:2],
                         [f"discovery: listed.json of {TODAY}", "meanwhile"])
        self.assertNotIn("--force", " ".join(" ".join(p) for p in pushes))

    def test_a_second_refusal_is_exit_1_and_nothing_reaches_github(self):
        real = D.git

        def refused(repo, *args):
            if args[:1] == ("push",):
                return subprocess.CompletedProcess(args, 1, "", "! [rejected] HEAD -> main (fetch first)")
            return real(repo, *args)
        with mock.patch.object(D, "git", refused):
            code, words = self.publish()
        self.assertEqual(code, 1)
        self.assertIn("refused twice", words)
        self.assertEqual(self.git(self.github, "rev-list", "--count", "main"), "1")

    def test_a_scan_finding_stops_the_commit(self):
        code, words = self.publish(scan=[sys.executable, "-c", "import sys; print('x: an e-mail'); sys.exit(1)"])
        self.assertEqual(code, 1)
        self.assertIn("scan_secrets.py found something", words)
        self.assertEqual(self.git(self.github, "rev-list", "--count", "main"), "1")

    def test_a_second_run_exits_at_once_while_the_first_holds_the_lock(self):
        with open(os.path.join(self.home, "discovery.lock"), "a+") as held:
            fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
            code, words = self.publish()
        self.assertEqual(code, 1)
        self.assertIn("another discovery run", words)
        self.assertFalse(os.path.exists(os.path.join(self.home, "discovery-repo")))

    def test_each_write_uses_a_temporary_file_of_its_own(self):
        seen = []
        real = os.replace

        def replace(src, dst):
            seen.append(src)
            return real(src, dst)
        with mock.patch.object(D.os, "replace", replace):
            D.write(self.out, "alpha\n")
            D.write(self.out, "bravo\n")
        self.assertEqual(len(set(seen)), 2)
        self.assertNotIn(self.out + ".tmp", seen)
        self.assertEqual(read(self.out), "bravo\n")


# --- finding 6: a partial day changes nothing ------------------------------------------------------------------------

class Finding6PartialDay(Case):
    def test_an_enabled_login_without_a_held_list_keeps_the_provider_s_part_and_date(self):
        # The reviewer's partial case: the second Devin login lost its list the next day.
        self.yesterday()
        answer = load(ANSWER)
        for r in answer["logins"]:
            if r["auth_index"] == "b39e04c6f1d7a218":
                r["live_list"] = None
                r["live"].update({"held": False, "fetched_at": None, "listed_models": None})
        code, words = self.from_answer(answer)
        self.assertEqual(code, 0, words)
        self.assertEqual(load(self.out)["providers"]["devin"], load(YESTERDAY)["providers"]["devin"])
        self.assertIn("devin: 1 of 2 enabled logins have no live list today", read(self.log))
        self.assertEqual(load(self.out)["providers"]["claude-subscription"]["date"], TODAY)  # complete: rebuilt

    def test_an_enabled_login_that_is_not_asked_at_all_also_keeps_the_part(self):
        self.yesterday()
        answer = load(ANSWER)
        for r in answer["logins"]:
            if r["auth_index"] == "c4a5f8e2d1b09376":
                r["disabled"] = False  # enabled, no list
        self.from_answer(answer)
        self.assertEqual(load(self.out)["providers"]["devin"], load(YESTERDAY)["providers"]["devin"])


# --- finding 7: refuse what the site refuses -------------------------------------------------------------------------

class Finding7SiteLimits(Case):
    def test_a_number_beyond_the_safe_integers_is_not_written(self):
        # The reviewer's safe-integer case: 2^53 passed G1 and the site refused the file.
        code, words = self.from_answer(answer_of(row("devin", [{"id": "fixture-model", "context": 2 ** 53}])))
        self.assertEqual(code, 0, words)
        self.assertNotIn("context_window", load(self.out)["providers"]["devin"]["models"][0])
        doc = load(YESTERDAY)
        doc["providers"]["devin"]["models"][0]["context_window"] = 2 ** 53
        self.assertTrue(any("2^53" in e for e in S.validate(doc)))
        doc["providers"]["devin"]["models"][0]["context_window"] = 2 ** 53 - 1
        self.assertEqual(S.validate(doc), [])

    def test_a_file_over_the_site_s_size_limit_is_not_written(self):
        self.yesterday()
        before = read(self.out)
        with mock.patch.object(S, "MAX_BYTES", 2000):
            code, words = self.from_answer(load(ANSWER))
        self.assertEqual(code, 1)
        self.assertIn("more than 8 MiB", words)
        self.assertEqual(read(self.out), before)

    def test_the_schema_command_refuses_an_oversized_file_and_an_empty_one(self):
        doc = load(YESTERDAY)
        doc["providers"]["devin"]["models"] = [{"id": f"m-{i}", "name": "A model name " * 4} for i in range(200000)]
        dump(doc, self.out)
        r = subprocess.run([sys.executable, os.path.join(ROOT, "harness", "listed_schema.py"), self.out],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertIn("more than 8 MiB", r.stdout)
        self.assertNotEqual(S.validate({"schema": 1, "providers": {}}), [])

    def test_the_shrink_guard_compares_with_github_s_file_not_a_local_copy(self):
        home = os.path.join(self.dir, "G")
        os.mkdir(home, 0o700)
        os.environ["GROUNDTRUTH_CLIENT_HOME"] = home
        github = os.path.join(self.dir, "github.git")
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", github], check=True)
        seed = os.path.join(self.dir, "seed")
        subprocess.run(["git", "clone", "-q", github, seed], check=True, capture_output=True)
        big = load(YESTERDAY)
        big["providers"]["devin"]["models"] = [{"id": f"m-{n}"} for n in range(40)]
        with open(os.path.join(seed, "listed.json"), "w") as f:
            f.write(D.text_of(big))
        for args in (("add", "-A"), ("-c", "user.name=x", "-c", "user.email=office@providers.dev", "commit", "-qm",
                                     "s"), ("push", "-q", "origin", "HEAD:main")):
            subprocess.run(["git", "-C", seed, *args], check=True, capture_output=True)
        # A small local file would let today's 14 models through; GitHub's 46 do not.
        self.yesterday()
        code, words = self.run_with(["--answer", ANSWER, "--log", self.log, "--date", TODAY, "--publish",
                                     "--upstream-url", github], scan=[sys.executable, "-c", "pass"])
        self.assertEqual(code, 1)
        self.assertIn("lost more than 40 %", words)
        r = subprocess.run(["git", "-C", github, "rev-list", "--count", "main"], capture_output=True, text=True)
        self.assertEqual(r.stdout.strip(), "1")


# --- finding 8: Copilot is not discovered for now --------------------------------------------------------------------

class Finding8Copilot(Case):
    def test_copilot_s_list_is_not_written(self):
        # Provimux's Copilot list holds the account's embedding and disabled models too.
        answer = answer_of(row("copilot", [{"id": "gpt-4.1"}, {"id": "text-embedding-3-small"},
                                           {"id": "disabled-model"}]),
                           row("claude", [{"id": "claude-plain"}]))
        code, words = self.from_answer(answer)
        self.assertEqual(code, 0, words)
        self.assertEqual(sorted(load(self.out)["providers"]), ["claude-subscription"])

    def test_the_reason_and_the_provimux_lines_are_in_the_doc(self):
        doc = read(os.path.join(ROOT, "docs", "discovery.md"))
        self.assertIn("sdk/cliproxy/provimux_live_copilot.go", doc)
        self.assertIn("sdk/auth/provimux_antigravity_models.go", doc)


# --- finding 9: the Monday handoff -----------------------------------------------------------------------------------

class Finding9Monday(unittest.TestCase):
    def test_the_weekly_night_s_first_step_is_written_down(self):
        doc = read(os.path.join(ROOT, "docs", "discovery.md"))
        self.assertIn("must run\n`python3 harness/discover.py --publish` as its first step, before planning", doc)


# --- finding 10: the installer ---------------------------------------------------------------------------------------

class Finding10Installer(unittest.TestCase):
    LABEL = "dev.providers.groundtruth.discovery"
    INSTALL = os.path.join(ROOT, "scripts", "install-discovery.sh")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = os.path.join(self.tmp.name, "G")
        os.mkdir(self.home, 0o700)
        self.target = os.path.join(self.tmp.name, "agents")
        os.mkdir(self.target)
        self.plist = os.path.join(self.target, self.LABEL + ".plist")
        with open(self.plist, "w") as f:
            f.write("an installed agent\n")
        self.env = dict(os.environ, GROUNDTRUTH_CLIENT_HOME=self.home)

    def install(self, *args):
        return subprocess.run([self.INSTALL, "--target", self.target, *args], env=self.env, capture_output=True,
                              text=True)

    def test_print_changes_nothing_whatever_else_is_given(self):
        for args in (("--print", "--uninstall"), ("--print", "--uninstall", "--owner-ok"),
                     ("--print", "--owner-ok", "--publish")):
            r = self.install(*args)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(read(self.plist), "an installed agent\n", args)

    def test_uninstall_needs_the_owner_s_ok(self):
        r = self.install("--uninstall")
        self.assertEqual(r.returncode, 1)
        self.assertTrue(os.path.exists(self.plist))
        r = self.install("--uninstall", "--owner-ok")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(os.path.exists(self.plist))

    def test_without_publish_the_agent_writes_in_its_own_folder_never_the_checkout(self):
        r = self.install("--owner-ok")
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(self.plist, "rb") as f:
            p = plistlib.load(f)
        self.assertEqual(p["ProgramArguments"][2:], ["harness/discover.py", "--out",
                                                     os.path.join(self.home, "listed.json")])


if __name__ == "__main__":
    unittest.main()
