"""The second review of the own-client night (at 6653ca3), the findings that remain in the first night's scope, each
reproduced as the review did and closed. Every test here fails at 6653ca3. Nothing is sent and no real client is run;
the sandbox test runs /usr/bin/touch under sandbox-exec, in a temporary folder.

    python3 -m unittest discover -s test -p "test_*.py"
"""
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
# No client is run to list its models (harness/model_ids.py): the checked list, also in the children.
os.environ.setdefault("GROUNDTRUTH_MODEL_LIST", "checked")
sys.path.insert(0, os.path.join(HERE, "..", "harness"))
sys.path.insert(0, HERE)
import clients as C  # noqa: E402
import night  # noqa: E402
import probe  # noqa: E402
import scan_secrets as ss  # noqa: E402
from test_probe import FakeClient, FakeClock, go as loop  # noqa: E402

FIXTURES = os.path.join(HERE, "fixtures", "clients")
SCAN = os.path.join(HERE, "..", "harness", "scan_secrets.py")
DATE = "2099-06-19"
STATUS = {"claude": '{"loggedIn": true, "authMethod": "claude.ai", "apiProvider": "firstParty"}',
          "codex": "Logged in using ChatGPT", "devin": "Logged in", "muse": ""}


def fx(client, case):
    with open(os.path.join(FIXTURES, client, case + ".json")) as f:
        return json.load(f)


def write(path, text, mode=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)
    if mode is not None:
        os.chmod(path, mode)


def mode(path):
    return stat.S_IMODE(os.lstat(path).st_mode)


def status_run(argv, env, cwd, stdin, timeout):
    i = argv.index("--version") if "--version" in argv else None
    name = next(a for a in argv if a in STATUS)
    return (0, f"{name} 1.0", "") if i else (0, STATUS[name], "")


class Owner(unittest.TestCase):
    """A simulated owner: a home folder, a repository and <client-home> under a temporary folder (umask 022, as a shell
    has it), the sandbox off (tested apart)."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="gt-review2-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.user = os.path.join(self.tmp, "person")
        self.repo = os.path.join(self.tmp, "repo")
        os.makedirs(self.user)
        os.makedirs(os.path.join(self.repo, ".git"))
        mask = os.umask(0o022)
        self.addCleanup(os.umask, mask)
        # The fixture repository is no Git checkout: its commit-hook check (night.hook_problem) is tested apart.
        for p in (mock.patch.object(night, "hook_problem", return_value=None),
                  mock.patch.object(C, "CONFINED", False, create=True), mock.patch.object(night, "ROOT", self.repo),
                  mock.patch.object(probe, "ROOT", self.repo), mock.patch.object(ss, "remember")):
            p.start()
            self.addCleanup(p.stop)

    def client_home(self, base=None, folder_mode=0o700):
        base = base or os.path.join(self.user, "groundtruth-clients")
        os.makedirs(base, exist_ok=True)
        os.chmod(base, folder_mode)
        # Every driver's folder (Claude's and Muse's drivers stay in the tree, tested, though no night reaches them).
        for name in sorted({c.client_id for c in C.CLIENTS.values()}):
            os.makedirs(os.path.join(base, name), exist_ok=True)
            os.chmod(os.path.join(base, name), folder_mode)
        p = mock.patch.dict(os.environ, {"GROUNDTRUTH_CLIENT_HOME": base, "HOME": self.user})
        p.start()
        self.addCleanup(p.stop)
        return base

    def state(self, client, base):
        return C.state_folder(client, base, self.repo, user_home=self.user, run=status_run, env=client.environment(
            os.path.join(base, client.client_id)) | {"META_API_KEY": "k" * 20})


class Finding1Storage(Owner):
    """1: no state folder or captured output in a synced folder; login files 600, state folders 700; Codex's own
    helper links allowed by their exact pattern; every client under sandbox-exec."""

    SYNCED = ("Library/CloudStorage/Example/groundtruth-clients", "Library/Mobile Documents/com~apple~CloudDocs/g",
              "Dropbox/g", "Google Drive/g", "OneDrive - Personal/g", "Library/CloudStorage/OneDrive-Personal/g")

    def test_a_state_folder_in_a_synced_folder_is_refused_by_the_snapshot_and_by_every_run(self):
        for where in self.SYNCED:
            with self.subTest(where=where):
                base = self.client_home(os.path.join(self.user, where))
                with self.assertRaisesRegex(SystemExit, "sync"):
                    night.untouched(DATE, "save", user_home=self.user, lister=lambda: "", out=lambda *_: None)
                with self.assertRaisesRegex(SystemExit, "sync"):
                    self.state(C.Claude("m"), base)

    def test_captured_output_in_a_synced_folder_is_refused(self):
        base = self.client_home()
        synced = os.path.join(self.user, "Library", "CloudStorage", "Box", "raw")
        with self.assertRaisesRegex(SystemExit, "under <client-home>|sync"):
            probe.private_capture_folder(synced, base, self.repo, user_home=self.user)
        base2 = self.client_home(os.path.join(self.user, "Dropbox", "g"))
        with self.assertRaisesRegex(SystemExit, "sync"):
            probe.private_capture_folder(os.path.join(base2, "night-x", "raw", "S1"), base2, self.repo, user_home=self.user)
        self.assertFalse(os.path.exists(os.path.join(base2, "night-x")))

    def test_state_folders_must_be_700_and_login_files_600(self):
        # The review's case: 0755 folders, 0644 login files of Claude, Codex and Devin.
        base = self.client_home(folder_mode=0o755)
        with self.assertRaisesRegex(SystemExit, "mode 755"):
            night.untouched(DATE, "save", user_home=self.user, lister=lambda: "", out=lambda *_: None)
        with self.assertRaisesRegex(SystemExit, "mode 755"):
            self.state(C.Claude("m"), base)
        base = self.client_home()
        logins = {"claude": "claude-code/.credentials.json", "codex": "codex-cli/auth.json",
                  "devin": "devin-cli/config/devin/credentials.toml"}
        for h, rel in logins.items():
            write(os.path.join(base, rel), "fixture only", 0o644)
            with self.subTest(client=h), self.assertRaisesRegex(SystemExit, "login file .* mode 644"):
                self.state(C.CLIENTS[h]("m"), base)
            os.chmod(os.path.join(base, rel), 0o600)
            self.assertTrue(self.state(C.CLIENTS[h]("m"), base))
        night.untouched(DATE, "save", user_home=self.user, lister=lambda: "", out=lambda *_: None)
        self.assertEqual(mode(night.everyday_path(DATE)), 0o600)
        self.assertEqual(mode(night.night_dir(DATE)), 0o700)

    def test_codex_s_own_helper_links_are_allowed_by_exact_pattern_any_other_link_out_refused(self):
        base = self.client_home()
        exe_dir = os.path.join(self.tmp, "bin")
        os.makedirs(exe_dir)
        write(os.path.join(exe_dir, "codex"), "#!/bin/sh\n", 0o755)
        state = os.path.join(base, "codex-cli")
        helpers = os.path.join(state, "tmp", "arg0-macos", "codex-arg0gcUc1C")
        os.makedirs(helpers)
        for name in ("apply_patch", "applypatch"):
            os.symlink(os.path.join(exe_dir, "codex"), os.path.join(helpers, name))
        env = C.Codex("m").environment(state, base={"PATH": exe_dir + os.pathsep + "/usr/bin"})
        with mock.patch.dict(os.environ, {"PATH": exe_dir + os.pathsep + "/usr/bin"}):
            self.assertTrue(C.state_folder(C.Codex("m"), base, self.repo, user_home=self.user, run=status_run, env=env))
            night.untouched(DATE, "save", user_home=self.user, lister=lambda: "", out=lambda *_: None)
            # the same names pointing elsewhere, another name, another folder: refused
            for rel, target in (("tmp/arg0-macos/codex-arg0gcUc1C/rg", os.path.join(exe_dir, "codex")),
                                ("tmp/arg0-macos/codex-arg0XXXXXX/apply_patch", self.user),
                                ("sessions/apply_patch", os.path.join(exe_dir, "codex"))):
                p = os.path.join(state, rel)
                os.makedirs(os.path.dirname(p), exist_ok=True)
                os.symlink(target, p)
                with self.subTest(rel=rel), self.assertRaisesRegex(SystemExit, "links that leave it"):
                    C.state_folder(C.Codex("m"), base, self.repo, user_home=self.user, run=status_run, env=env)
                os.remove(p)
        os.remove(os.path.join(helpers, "apply_patch"))
        os.symlink(self.user, os.path.join(helpers, "apply_patch"))
        with self.assertRaisesRegex(SystemExit, "links that leave it"):
            C.state_folder(C.Codex("m"), base, self.repo, user_home=self.user, run=status_run, env=env)

    def test_the_morning_report_survives_a_file_rotated_during_the_walk(self):
        # The review's case: an everyday file removed while the walk passes it.
        self.client_home()
        write(os.path.join(self.user, ".pi", "agent", "rolling"), "fixture")
        night.untouched(DATE, "save", user_home=self.user, lister=lambda: "", out=lambda *_: None)
        real_walk = os.walk

        def rotating(top, *a, **kw):
            for root, dirs, names in real_walk(top, *a, **kw):
                if "rolling" in names:
                    os.unlink(os.path.join(root, "rolling"))
                yield root, dirs, names
        lines = []
        with mock.patch.object(night.os, "walk", side_effect=rotating):
            night.untouched(DATE, "report", user_home=self.user, lister=lambda: "", at="t", out=lines.append)
        with open(night.report_path(DATE, "t")) as f:
            text = f.read()
        self.assertIn("vanished during the walk: ~/.pi/agent/rolling", text)
        self.assertTrue(any("removed while the walk passed" in x for x in lines), lines)


@unittest.skipUnless(sys.platform == "darwin" and os.path.exists("/usr/bin/sandbox-exec"), "sandbox-exec is macOS's")
class Finding1Sandbox(unittest.TestCase):
    """1, the OS-level layer: a client process cannot write under the home folder outside its own folders."""

    def test_a_write_under_the_home_folder_is_denied_outside_the_allowed_folders(self):
        with tempfile.TemporaryDirectory() as t:
            t = os.path.realpath(t)
            home = os.path.join(t, "person")
            state, other = os.path.join(home, "g", "codex-cli"), os.path.join(home, ".codex")
            for d in (state, other):
                os.makedirs(d)
            argv = C.confine(["/usr/bin/touch", os.path.join(state, "ok")], {}, [state], user_home=home)
            self.assertEqual(argv[:2], [C.SANDBOX_EXEC, "-p"])
            self.assertEqual(subprocess.run(argv, capture_output=True).returncode, 0)
            denied = C.confine(["/usr/bin/touch", os.path.join(other, "no")], {}, [state], user_home=home)
            self.assertNotEqual(subprocess.run(denied, capture_output=True).returncode, 0)
            self.assertFalse(os.path.exists(os.path.join(other, "no")))
            # outside the home folder (the system's temporary folder) is left as it is
            self.assertEqual(subprocess.run(C.confine(["/usr/bin/touch", os.path.join(t, "x")], {}, [state],
                                                      user_home=home)).returncode, 0)

    def test_every_invocation_of_a_run_is_confined(self):
        seen = []

        def run(argv, env, cwd, stdin, timeout):
            seen.append(argv)
            f = fx("claude", "prime")
            return (0, "2.1.330 (Claude Code)", "") if argv[-1] == "--version" else (f["code"], f["stdout"], f["stderr"])
        with tempfile.TemporaryDirectory() as t:
            s = C.Session(C.Claude("m"), env={"HOME": t}, io=t + "/io", work=t + "/work", run=run, home=t,
                          writable=[t])
            s.start("p")
            C.Claude("m").version({}, run=run, writable=[t])
        self.assertTrue(all(a[0] == C.SANDBOX_EXEC for a in seen), seen)


class Finding2Provider(Owner):
    """2: Codex runs force the ChatGPT provider; a state folder whose config selects another is refused."""

    def test_the_command_forces_the_provider(self):
        for argv in (C.Codex("m").command("p"), C.Codex("m").command("p", resume="T"), C.Codex("m").login_command(),
                     night.LOGINS["codex"]):
            self.assertIn('model_provider="openai"', argv)
            self.assertEqual(argv[argv.index('model_provider="openai"') - 1], "-c")

    def test_a_config_selecting_another_provider_is_refused(self):
        base = self.client_home()
        cfg = os.path.join(base, "codex-cli", "config.toml")
        # The review's case.
        write(cfg, 'model_provider = "fixture"\n[model_providers.fixture]\nname = "fixture"\n'
                   'base_url = "https://example.invalid/v1"\nrequires_openai_auth = true\nwire_api = "responses"\n')
        with self.assertRaisesRegex(SystemExit, "model_provider"):
            self.state(C.Codex("m"), base)
        with self.assertRaisesRegex(SystemExit, "model_provider"):
            night.untouched(DATE, "save", user_home=self.user, lister=lambda: "", out=lambda *_: None)
        for text in ('profile = "work"\n', '[profiles.work]\nmodel_provider = "oss"\n', 'chatgpt_base_url = "http://x"\n',
                     "not toml [\n"):
            write(cfg, text)
            with self.subTest(text=text), self.assertRaises(SystemExit):
                self.state(C.Codex("m"), base)
        for text in ('model_provider = "openai"\nmodel = "gpt-6-luna"\n', ""):
            write(cfg, text)
            self.assertTrue(self.state(C.Codex("m"), base))


def git(root, *args):
    return subprocess.run(["git", "-C", root, *args], check=True, capture_output=True, text=True)


def scan(args, cwd):
    missing = os.path.join(cwd, "missing")
    env = {k: v for k, v in os.environ.items() if k not in ("CACHE_PROBE_KEY", "GROUNDTRUTH_CLIENT_HOME", "META_API_KEY")
           and not k.startswith("GIT_")}
    env.update(SCAN_CLIENT_KEYS=missing, SCAN_KEYS_FILE=missing, SCAN_CONFIG=missing, SCAN_LOGINS=missing + "/*.json",
               SCAN_FINGERPRINTS=missing + "/fingerprints.json")
    return subprocess.run([sys.executable, SCAN, *args], capture_output=True, text=True, env=env, cwd=cwd)


class Finding3Publication(Owner):
    """3: every client's login and session file names refused by both scans; a child-only value never reaches a
    public result."""

    NAMES = ("notes/credentials.toml", "notes/.credentials.json", "notes/auth.json", "x/session_index.jsonl",
             "x/123e4567-e89b-42d3-a456-426614174000.jsonl", "x/rollout-2026-11-23T01-00-00-abc.jsonl",
             "x/001-start-stdout.txt", "x/fingerprints.json")

    def test_both_scans_refuse_each_login_and_session_file_name(self):
        for rel in self.NAMES:
            with self.subTest(file=rel), tempfile.TemporaryDirectory() as t:
                root = os.path.join(t, "repo")
                git(t, "init", "-q", root)
                write(os.path.join(root, "README.md"), "a public file\n")
                write(os.path.join(root, rel), 'token = "fixture.devin.value"\n')
                git(root, "add", "-f", "README.md", rel)
                export = os.path.join(t, "export")
                git(root, "checkout-index", "-a", "--prefix=" + export + "/")
                for args in ([export], ["--git", root]):  # the pre-commit hook's two scans
                    r = scan(args, t)
                    self.assertEqual(r.returncode, 1, (args, r.stdout, r.stderr))
                    self.assertIn(os.path.basename(rel), r.stdout)

    def test_the_ignore_rules_cover_devins_login(self):
        with open(os.path.join(HERE, "..", ".gitignore")) as f:
            self.assertIn("**/credentials.toml", f.read().split())

    def test_a_child_only_value_in_a_usage_field_never_reaches_the_public_record(self):
        # The review's marker case: Muse Code puts the exact value of META_API_KEY in a structured usage field.
        marker = "review.fixture.value"
        base = self.client_home()
        shape = fx("muse", "warm")["stdout"].replace("muse-wonder-1.0", marker)

        def execution(argv, **kw):
            return (0, "fixture-version", "") if argv[-1] == "--version" else (0, shape, "")

        def two_events(h, *, log, **kw):
            _, u = h.start("ordinary fixture prompt")
            log({"event": "baseline", "usage": u})
            log({"event": "done"})
        out = os.path.join(self.repo, "results")
        with mock.patch.dict(os.environ, {"META_API_KEY": marker}), mock.patch.object(C, "_run", side_effect=execution), \
                mock.patch.object(probe, "run_probe", side_effect=two_events), redirect_stdout(io.StringIO()) as printed:
            probe.main(["--harness", "muse", "--model", "m", "--label", "S4", "--replicas", "0", "--out", out,
                        "--keep-raw", os.path.join(base, f"night-{DATE}", "raw", "S4")])
        with open(os.path.join(out, "S4.jsonl")) as f:
            public = f.read()
        self.assertNotIn(marker, public)
        self.assertNotIn(marker, printed.getvalue())
        kept = os.path.join(base, f"night-{DATE}", "raw", "S4")
        for name in os.listdir(kept):
            with open(os.path.join(kept, name)) as f:
                self.assertNotIn(marker, f.read())


class Finding4DryRun(Owner):
    """4: --dry-run of every command does nothing: no folder, no marker, no lock, no signal, no client run."""

    def tree(self):
        return sorted((os.path.relpath(os.path.join(d, n), self.tmp), os.lstat(os.path.join(d, n)).st_mtime_ns)
                      for d, dirs, files in os.walk(self.tmp) for n in dirs + files)

    def test_every_command(self):
        base = self.client_home()
        # A smoke that passes the checks, a launched client with a live run: what a dry run could wrongly act on.
        Finding9Launcher.smoke_files(self.repo)
        os.makedirs(os.path.join(night.night_dir(DATE), "launch"), mode=0o700)
        write(night.lock_path(DATE, "codex"), json.dumps({"launch_id": "L", "runs": {"CX1": {"pid": 4242, "started": "T"}}}))
        write(night.everyday_path(DATE), json.dumps({"files": {}, "keychain": []}))
        os.chmod(night.night_dir(DATE), 0o700)
        before = self.tree()
        forbidden = mock.Mock(side_effect=AssertionError("a dry run acted"))
        live = "python3 harness/probe.py --label CX1 --out x --launch-id L"
        commands = [["stop", "all"], ["stop", "codex"], ["smoke-reviewed"], ["untouched", "--save"],
                    ["untouched", "--report"], ["login", "devin"], ["login", "codex"], ["status"], ["codex"], ["all"],
                    ["smoke"]]
        with mock.patch.object(night.os, "killpg", forbidden), mock.patch.object(night.os, "kill", forbidden), \
                mock.patch.object(night.subprocess, "Popen", forbidden), \
                mock.patch.object(night, "process_command", lambda pid: live), \
                mock.patch.object(night, "process_started", lambda pid: "T"), \
                mock.patch.object(night, "dry_run", lambda *a, **k: None), \
                mock.patch.object(night, "keychain_items", forbidden), redirect_stdout(io.StringIO()) as said:
            for cmd in commands:
                with self.subTest(cmd=cmd):
                    night.main(["--date", DATE, "--dry-run", *cmd])
        self.assertEqual(self.tree(), before)
        forbidden.assert_not_called()
        self.assertFalse(os.path.exists(night.reviewed_path(DATE)))
        self.assertIn("would signal pid 4242", said.getvalue())
        self.assertTrue(base)


class Finding5Muse(unittest.TestCase):
    """5: Muse Code, two runs in one invocation are two calls, never the last run's figures as one."""

    def test_two_runs_are_two_calls(self):
        warm = fx("muse", "warm")["stdout"]
        u = C.Muse("m").parse(warm + warm, "", 0, {}, expect={"session": "s", "prompt": C.OK_PROMPT})
        self.assertEqual(u.calls, 2)
        self.assertEqual(u.cached, 2 * 36200)
        one = C.Muse("m").parse(warm, "", 0, {})
        self.assertEqual(one.calls, 1)

    def test_a_check_of_two_runs_is_not_counted(self):
        clock = FakeClock()
        fake = FakeClient(clock, ttl=3600)
        fake.calls["s1"] = C.Muse("m").parse(fx("muse", "warm")["stdout"] * 2, "", 0, {}).calls
        reason, events = loop(fake, clock, ages=(), replicas=0)
        self.assertEqual(reason, "control-failed")
        self.assertEqual([e["event"] for e in events][-2:], ["check-invalid", "stop"])


class Finding9Launcher(Owner):
    """9: the launcher: one lock per client, a second start refused; liveness by process and launch; stop signals
    exactly those; the smoke checks take S3b's cold control as expected and refuse a late control."""

    @staticmethod
    def smoke_files(repo, s3b_cold=True, late=None):
        folder = os.path.join(repo, night.folders(DATE)["smoke"])
        for step in night.PARTS["smoke"]:
            sid = step["id"]
            cold = sid == "S3b" and s3b_cold
            check = {"event": "check", "age": "control", "late": sid == late, "warm": not cold,
                     "usage": {"calls": 1}, "realAgeSec": 600 if sid == late else 31}
            last = {"event": "stop", "reason": "no-observable-cache"} if cold else {"event": "done"}
            isolation = {"home": "dedicated", "HOME": "throwaway", "work": "temporary"}
            rows = [{"event": "start", "isolation": isolation}, {"event": "baseline"},
                    {"event": "prime", "age": "control"}, check, last]
            write(os.path.join(folder, sid + ".jsonl"), "".join(json.dumps(r) + "\n" for r in rows))

    def ready(self):
        base = self.client_home()
        # Stand-in pids: every process "started" at the same recorded time (stop and status check it).
        p = mock.patch.object(night, "process_started", lambda pid: "T")
        p.start()
        self.addCleanup(p.stop)
        night.make_night_dir(DATE)
        write(night.everyday_path(DATE), json.dumps({"files": {}, "keychain": []}))
        self.smoke_files(self.repo)
        night.smoke_reviewed(DATE, out=lambda *_: None)
        return base

    def popen(self):
        pids = iter(range(5000, 6000))
        self.started = []

        def popen(argv, **kw):
            self.started.append((argv, kw))
            return SimpleNamespace(pid=next(pids))
        return popen

    def ps_of(self, lock):
        lines = {info["pid"]: f"python3 harness/probe.py --label {rid} --out x --launch-id {lock['launch_id']}"
                 for rid, info in lock["runs"].items()}
        return lambda pid: lines.get(pid, "")

    def test_a_client_s_runs_start_in_the_background_under_one_lock_and_a_second_start_is_refused(self):
        self.ready()
        popen = self.popen()
        lock = night.go_clients(["codex"], DATE, popen=popen, out=lambda *_: None)[0]
        self.assertEqual(sorted(lock["runs"]), sorted(s["id"] for s in night.PARTS["codex"]))
        argv, kw = self.started[0]
        self.assertTrue(argv[1].endswith("harness/probe.py"))  # the probe itself: its pid is the run's (caffeinate -w)
        self.assertTrue(kw["start_new_session"])
        self.assertIn(lock["launch_id"], argv)
        self.assertEqual(mode(night.lock_path(DATE, "codex")), 0o600)
        with self.assertRaisesRegex(SystemExit, "a second start is refused"):
            night.go_clients(["codex"], DATE, popen=popen, out=lambda *_: None)
        with self.assertRaisesRegex(SystemExit, "codex launched already"):
            night.go_clients(["all"], DATE, popen=popen, out=lambda *_: None)
        self.assertEqual(len(self.started), len(night.PARTS["codex"]))  # `all` started nothing: codex's lock held

    def test_two_overlapping_starts_launch_once(self):
        # The review's case: a second go while the first is still starting its runs.
        self.ready()
        inner = []
        base_popen = self.popen()

        def popen(argv, **kw):
            if not inner:
                try:
                    night.launch("codex", DATE, popen=base_popen, out=lambda *_: None)
                except SystemExit as e:
                    inner.append(str(e))
            return base_popen(argv, **kw)
        night.launch("codex", DATE, popen=popen, out=lambda *_: None)
        self.assertIn("a second start is refused", inner[0])
        self.assertEqual(len(self.started), len(night.PARTS["codex"]))

    def test_status_is_process_liveness_and_stop_signals_exactly_those(self):
        self.ready()
        lock = night.go_clients(["devin"], DATE, popen=self.popen(), out=lambda *_: None)[0]
        ps = self.ps_of(lock)
        dv1 = lock["runs"]["DV1"]["pid"]
        alive_only = lambda pid: ps(pid) if pid == dv1 else ""  # noqa: E731
        lines = []
        counts = night.status(DATE, ps=alive_only, out=lines.append)
        self.assertEqual(counts, {"alive": 1, "ended": len(night.PARTS["devin"]) - 1})
        sent = []
        night.stop("codex", DATE, ps=alive_only, kill=lambda p, s: sent.append(p), out=lambda *_: None)
        self.assertEqual(sent, [])
        night.stop("devin", DATE, ps=alive_only, kill=lambda p, s: sent.append(p), out=lambda *_: None)
        self.assertEqual(sent, [dv1])

    def test_a_reused_pid_or_another_night_s_run_is_never_signalled(self):
        # The review's case: the pid now belongs to the following night's run (same label, other launch).
        self.ready()
        lock = night.go_clients(["codex"], DATE, popen=self.popen(), out=lambda *_: None)[0]
        cc1 = lock["runs"]["CX1"]["pid"]
        other = lambda pid: ("python3 harness/probe.py --label CX1 --out results/own-clients-2099-06-20 "  # noqa: E731
                             "--launch-id 2099-06-20-codex-000000000000") if pid == cc1 else "/usr/bin/vim"
        sent = []
        night.stop("all", DATE, ps=other, kill=lambda p, s: sent.append(p), out=lambda *_: None)
        self.assertEqual(sent, [])
        self.assertEqual(night.status(DATE, ps=other, out=lambda *_: None),
                         {"ended": len(night.PARTS["codex"])})

    def test_the_go_waits_for_the_snapshot_and_the_smoke_review(self):
        self.client_home()
        with self.assertRaisesRegex(SystemExit, "snapshot"):
            night.go_clients(["devin"], DATE, popen=self.popen(), out=lambda *_: None)
        night.make_night_dir(DATE)
        write(night.everyday_path(DATE), "{}")
        with self.assertRaisesRegex(SystemExit, "smoke-reviewed"):
            night.go_clients(["devin"], DATE, popen=self.popen(), out=lambda *_: None)
        with self.assertRaisesRegex(SystemExit, "--go: smoke, or one of"):
            night.go_clients(["smoke", "codex"], DATE, popen=self.popen(), out=lambda *_: None)

    def test_the_smoke_checks_take_s3b_cold_as_expected_and_refuse_a_late_control(self):
        self.client_home()
        self.smoke_files(self.repo, s3b_cold=True)
        problems, notes = night.smoke_verdict(DATE)
        self.assertEqual(problems, [])
        self.assertTrue(any(n.startswith("S3b: the control was cold") for n in notes))
        self.smoke_files(self.repo, s3b_cold=False, late="S2")  # the review's warm control at 600 s
        problems, _ = night.smoke_verdict(DATE)
        self.assertTrue(any("S2: the control was checked late" in p for p in problems), problems)
        with self.assertRaisesRegex(SystemExit, "refused"):
            night.smoke_reviewed(DATE, out=lambda *_: None)
        self.assertFalse(os.path.exists(night.reviewed_path(DATE)))

    def test_a_late_control_ends_the_run_unchecked(self):
        # The review's case: a priming that took 600 s; the control is not checked late, the run stops.
        clock = FakeClock()
        fake = FakeClient(clock, ttl=3600)
        fake.prime_took[1] = 600
        reason, events = loop(fake, clock, ages=(), replicas=0)
        self.assertEqual(reason, "control-late")
        self.assertEqual([e["event"] for e in events], ["baseline", "prime", "stop"])
        self.assertEqual(fake.resumes, [])


class Finding13Capture(Owner):
    """13: the raw output's folder is never a link (at any level under <client-home>); it is 700, its files 600."""

    def run_s4(self, keep):
        def execution(argv, **kw):
            return (0, "v", "") if argv[-1] == "--version" else (0, fx("muse", "warm")["stdout"], "")

        def one(h, *, log, **kw):
            h.start("p")
            log({"event": "done"})
        with mock.patch.dict(os.environ, {"META_API_KEY": "k" * 20}), mock.patch.object(C, "_run", side_effect=execution), \
                mock.patch.object(probe, "run_probe", side_effect=one), redirect_stdout(io.StringIO()):
            probe.main(["--harness", "muse", "--model", "m", "--label", "S4", "--replicas", "0",
                        "--out", os.path.join(self.repo, "results"), "--keep-raw", keep])

    def test_a_linked_capture_folder_is_refused(self):
        # The review's case: <client-home>/night-.../raw/S4 a link into a checkout.
        base = self.client_home()
        public = os.path.join(self.repo, "published")
        os.makedirs(public)
        raw = os.path.join(base, f"night-{DATE}", "raw")
        os.makedirs(raw)
        os.symlink(public, os.path.join(raw, "S4"))
        with self.assertRaisesRegex(SystemExit, "is a link"):
            self.run_s4(os.path.join(raw, "S4"))
        self.assertEqual(os.listdir(public), [])
        os.remove(os.path.join(raw, "S4"))
        shutil.rmtree(raw)
        os.symlink(public, raw)  # a link higher up
        with self.assertRaisesRegex(SystemExit, "is a link"):
            self.run_s4(os.path.join(raw, "S4"))
        self.assertEqual(os.listdir(public), [])

    def test_captures_are_owner_only(self):
        base = self.client_home()
        keep = os.path.join(base, f"night-{DATE}", "raw", "S4")
        self.run_s4(keep)
        files = os.listdir(keep)
        self.assertTrue(files)
        self.assertEqual(mode(keep), 0o700)
        for name in files:
            self.assertEqual(mode(os.path.join(keep, name)), 0o600)


class FindingM1CodexModel(unittest.TestCase):
    """M-1: the model that answered, recorded for Codex too (from its session file: the turn's model, or the model
    the server rerouted it to)."""

    def test_the_answered_model_is_recorded(self):
        f = fx("codex", "warm")
        tid = f["expect"]["handle"]
        with tempfile.TemporaryDirectory() as t:
            rollout = os.path.join(t, "state", "sessions", "2026", "11", "23", f"rollout-2026-11-23T01-00-00-{tid}.jsonl")
            write(rollout, json.dumps({"type": "session" + "_meta", "payload": {"id": tid}}) + "\n")
            turn = []  # what the client's invocation appends to its session file

            def run(*a, **k):
                with open(rollout, "a") as out:
                    out.write("".join(json.dumps(x) + "\n" for x in turn))
                return 0, f["stdout"], ""
            s = C.Session(C.Codex("gpt-6-luna"), env={}, io=t + "/io", work=t + "/work", home=os.path.join(t, "state"),
                          run=run)
            turn[:] = [{"type": "turn_context", "payload": {"model": "gpt-6-luna", "cwd": "/w", "turn_id": "t1"}},
                       {"type": "event_msg", "payload": {"type": "token_count"}}]
            self.assertEqual(s.resume(tid, "p").model, "gpt-6-luna")
            # A reroute (Codex's ModelRerouteEvent carries no turn id) is a model record of no turn: the check's model
            # is not certain (since the fifth review; it was recorded as the rerouted model before).
            turn[:] = [{"type": "turn_context", "payload": {"model": "gpt-6-luna", "cwd": "/w", "turn_id": "t2"}},
                       {"type": "event_msg", "payload": {"type": "model_reroute", "from_model": "gpt-6-luna",
                                                         "to_model": "gpt-6-astra"}}]
            u = s.resume(tid, "p")
            self.assertEqual((u.model, u.model_issue), (None, "ambiguous-model"))


class FindingM3Waves(unittest.TestCase):
    """M-3: an age's replicas are primed at least 300 s apart, whatever a slow priming did (the review saw 82 s)."""

    def test_the_review_s_case(self):
        clock = FakeClock()
        fake = FakeClient(clock, ttl=100000, took=1)
        fake.prime_took[3] = 220
        reason, events = loop(fake, clock, ages=("2.5m", "5m"), replicas=3)
        self.assertIsNone(reason)
        for age in ("2.5m", "5m"):
            t = [fake.primed[e["handle"]] for e in events if e["event"] == "prime" and e["age"] == age]
            self.assertEqual(len(t), 3)
            self.assertTrue(all(b - a >= probe.WAVE_GAP for a, b in zip(t, t[1:])), (age, t))


if __name__ == "__main__":
    unittest.main()
