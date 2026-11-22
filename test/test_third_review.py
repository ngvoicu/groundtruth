"""The third review of the own-client night (at 1302623): the last round's points, each reproduced as the review did
and closed. Every test here fails at 1302623. Nothing is sent and no real client is run: stand-in programs, the
probe and the launcher run in temporary folders.

    python3 -m unittest discover -s test -p "test_*.py"
"""
import io
import json
import os
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout, redirect_stderr
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "harness"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, HERE)
import clients as C  # noqa: E402
import night  # noqa: E402
import probe  # noqa: E402
import build_observed as B  # noqa: E402
from test_probe import FakeClient, FakeClock, go as loop  # noqa: E402
import test_second_review as R2  # noqa: E402  (as a module: its tests are not collected twice)

Owner = R2.Owner
fx, write, mode, status_run, DATE = R2.fx, R2.write, R2.mode, R2.status_run, R2.DATE

SCAN = os.path.join(ROOT, "harness", "scan_secrets.py")


def no_sources(tmp, **extra):
    """An environment whose scan sources all point at nothing."""
    gone = os.path.join(tmp, "absent")
    env = {k: v for k, v in os.environ.items() if k not in ("CACHE_PROBE_KEY", "GROUNDTRUTH_CLIENT_HOME", "META_API_KEY",
                                                             "PYTHONDONTWRITEBYTECODE") and not k.startswith("GIT_")}
    env.update(SCAN_CLIENT_KEYS=gone, SCAN_KEYS_FILE=gone, SCAN_CONFIG=gone, SCAN_LOGINS=gone + "/*.json",
               SCAN_FINGERPRINTS=gone + "/fingerprints.json")
    env.update(extra)
    return env


class Point1Logins(Owner):
    """1: a login is done only with its file in the night's folder and the client's own status; Claude's preflight
    refuses an empty folder; the night's own TMPDIR, never the shell's."""

    def login(self, name, creates=None, content="{}", status=None):
        def run(argv, env, cwd):
            if creates:
                write(os.path.join(cwd, creates), content, 0o644)
            return mock.Mock(returncode=0)
        statuses = []

        def status_fn(argv, env, cwd, stdin, timeout):
            statuses.append(argv)
            return status if status is not None else status_run(argv, env, cwd, stdin, timeout)
        lines = []
        night.login(name, DATE, run=run, out=lines.append, user_home=self.user, status_run=status_fn)
        return lines, statuses

    def snapshot(self):
        night.untouched(DATE, "save", user_home=self.user, lister=lambda: "", out=lambda *_: None)

    def test_a_login_that_wrote_nothing_or_an_empty_file_is_not_done(self):
        self.client_home()
        self.snapshot()
        files = {"codex": "auth.json", "devin": "config/devin/credentials.toml"}
        with self.assertRaisesRegex(SystemExit, "not in the first night"):
            self.login("claude", creates=".credentials.json")
        for name in files:
            with self.subTest(client=name, case="nothing"), self.assertRaisesRegex(SystemExit, "no login file"):
                self.login(name)
            with self.subTest(client=name, case="empty"), self.assertRaisesRegex(SystemExit, "no login file"):
                self.login(name, creates=files[name], content="")
            os.remove(os.path.join(night.client_home(), C.CLIENTS[name].client_id, files[name]))
        for name, rel in files.items():
            with self.subTest(client=name, case="written"):
                lines, statuses = self.login(name, creates=rel)
                self.assertIn("done", lines[-1])
                self.assertEqual(mode(os.path.join(night.client_home(), C.CLIENTS[name].client_id, rel)), 0o600)
                self.assertEqual(statuses[0][-len(C.CLIENTS[name]("m").login_command()):],
                                 C.CLIENTS[name]("m").login_command())

    def test_a_login_whose_status_refuses_is_not_done(self):
        self.client_home()
        self.snapshot()
        with self.assertRaisesRegex(SystemExit, "status refuses"):
            self.login("devin", creates="config/devin/credentials.toml", status=(0, "Logged in with an API key", ""))
        with self.assertRaisesRegex(SystemExit, "status refuses"):
            self.login("codex", creates="auth.json", status=(0, "Logged in using an API key", ""))

    def test_a_login_waits_for_the_snapshot(self):
        self.client_home()
        with self.assertRaisesRegex(SystemExit, "no snapshot"):
            self.login("codex", creates="auth.json")

    def test_claude_s_preflight_refuses_an_empty_state_folder(self):
        # The review's case: an affirmative subscription status, the dedicated folder empty.
        base = self.client_home()
        with self.assertRaisesRegex(SystemExit, "no login file"):
            self.state(C.Claude("m"), base)
        write(os.path.join(base, "claude-code", ".credentials.json"), "{}", 0o600)
        self.assertTrue(self.state(C.Claude("m"), base))

    def test_the_shell_s_tmpdir_never_reaches_a_client_nor_its_sandbox(self):
        # The review's case: the shell's TMPDIR is the home folder itself.
        base = self.client_home()
        write(os.path.join(base, "claude-code", ".credentials.json"), "{}", 0o600)
        seen = []

        def run(argv, env, cwd, stdin, timeout):
            seen.append((argv, env))
            return status_run(argv, env, cwd, stdin, timeout)
        with mock.patch.dict(os.environ, {"TMPDIR": self.user}), mock.patch.object(C, "CONFINED", True), \
                mock.patch.object(C.os.path, "exists", lambda p: True if p == C.SANDBOX_EXEC else os.path.lexists(p)):
            env = C.Claude("m").environment(os.path.join(base, "claude-code"))
            C.state_folder(C.Claude("m"), base, self.repo, user_home=self.user, run=run)
        self.assertEqual(env["TMPDIR"], C.throwaway_tmp(os.path.join(base, "claude-code")))
        argv, child_env = seen[0]
        self.assertNotEqual(child_env["TMPDIR"], self.user)
        profile = argv[argv.index("-p") + 1]
        allowed = profile.split("(allow file-write*", 1)[1]
        self.assertNotIn(f'(subpath "{os.path.realpath(self.user)}")', allowed)
        self.assertEqual(mode(child_env["TMPDIR"]), 0o700)
        with self.assertRaisesRegex(SystemExit, "holds it"):
            C.sandbox_profile([self.user], user_home=self.user)

    def test_modes_are_exact(self):
        # The review's case: 0500 folders and 0400 files passed a check that said 700 and 600.
        base = self.client_home()
        os.chmod(os.path.join(base, "codex-cli"), 0o500)
        with self.assertRaisesRegex(SystemExit, "mode 500"):
            self.state(C.Codex("m"), base)
        os.chmod(os.path.join(base, "codex-cli"), 0o700)
        write(os.path.join(base, "codex-cli", "auth.json"), "{}", 0o400)
        with self.assertRaisesRegex(SystemExit, "mode 400"):
            self.state(C.Codex("m"), base)


class Point2Logs(Owner):
    """2: console logs mode 600 and scrubbed of the child's secrets; no error path puts a folder in the public JSONL."""

    def test_the_review_s_version_diagnostic_case(self):
        # A stand-in client prints its home folder in a failing version diagnostic: the launcher's console log is 600,
        # holds no traceback and no home folder. (The review's case was Muse's; the first night runs no Muse Code.)
        base = self.client_home()
        value = self.user
        bin_ = os.path.join(self.tmp, "bin")
        write(os.path.join(bin_, "codex"), "#!" + sys.executable + "\nimport os,sys\n"
              "if sys.argv[1:3] == ['login', 'status']:\n    print('Logged in using ChatGPT'); sys.exit(0)\n"
              "print('fixture diagnostic: ' + os.environ['HOME'] + ' ' + " + repr(self.user) + ", file=sys.stderr)\n"
              "sys.exit(1)\n", 0o700)
        repo = os.path.join(self.tmp, "tree")
        shutil.copytree(os.path.join(ROOT, "harness"), os.path.join(repo, "harness"),
                        ignore=shutil.ignore_patterns("__pycache__"))
        night.make_night_dir(DATE)
        for p in (night.everyday_path(DATE), night.reviewed_path(DATE)):
            write(p, "fixture")
        children = []

        def popen(*a, **kw):
            p = subprocess.Popen(*a, **kw)
            children.append(p)
            return p
        env = {"PATH": bin_ + os.pathsep + "/usr/bin:/bin:/usr/sbin:/sbin", "HOME": self.user,
               "SCAN_FINGERPRINTS": os.path.join(self.tmp, "fp.json"), "GROUNDTRUTH_CLIENT_HOME": base}
        try:
            with mock.patch.dict(os.environ, env), mock.patch.object(night, "ROOT", repo), \
                    mock.patch.dict(night.PARTS, {"codex": [night.PARTS["codex"][0]]}):
                night.go_clients(["codex"], DATE, popen=popen, out=lambda *_: None)
            self.assertNotEqual(children[0].wait(timeout=60), 0)
        finally:
            for p in children:
                if p.poll() is None:
                    os.killpg(p.pid, signal.SIGTERM)
        log = os.path.join(repo, night.folders(DATE)["own"], "logs", "CX1.log")
        with open(log) as f:
            text = f.read()
        self.assertIn("--version failed", text)
        self.assertNotIn(value, text)
        self.assertNotIn("Traceback", text)
        self.assertEqual(mode(log), 0o600)

    def test_a_timeout_keeps_every_folder_out_of_the_public_record(self):
        # The review's case: a subprocess timeout, whose text holds the sandbox profile with the owner's folders.
        base = self.client_home()
        out = os.path.join(self.repo, "results")

        def timeout_or_status(argv, **kw):
            if "--version" in argv:
                return 0, "fixture v1", ""
            raise subprocess.TimeoutExpired(argv, 900)
        with mock.patch.object(C, "_run", side_effect=timeout_or_status), \
                mock.patch.dict(os.environ, {"META_API_KEY": "fixture-muse-key-000"}), \
                mock.patch.object(probe.Clock, "sleep", lambda self, n: None), redirect_stdout(io.StringIO()), \
                redirect_stderr(io.StringIO()):
            probe.main(["--harness", "muse", "--model", "muse-wonder-1.0", "--label", "S4", "--out", out,
                        "--replicas", "0"])
        with open(os.path.join(out, "S4.jsonl")) as f:
            public = f.read()
        self.assertIn('"error_kind": "timeout"', public)
        for folder in (self.user, os.path.realpath(self.user), base, "sandbox-exec", "subpath"):
            self.assertNotIn(folder, public)
        r = subprocess.run([sys.executable, SCAN, "--own-clients", out], capture_output=True, text=True,
                           env=no_sources(self.tmp))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_an_unexpected_error_reaches_the_console_redacted(self):
        self.client_home()
        value = "synthetic.review.only.99"

        def boom(*a, **kw):
            raise RuntimeError("failed with " + value + " in " + self.user)
        with mock.patch.dict(os.environ, {"META_API_KEY": value}), mock.patch.object(C, "state_folder", boom), \
                self.assertRaises(SystemExit) as e:
            probe.main(["--harness", "muse", "--model", "m", "--label", "MC1", "--out", self.repo, "--replicas", "0"])
        self.assertNotIn(value, str(e.exception.code))
        self.assertNotIn(self.user, str(e.exception.code))


class Point3Bytecode(unittest.TestCase):
    """3: a dry run writes no bytecode, with ordinary Python defaults."""

    def test_the_dry_run_on_a_fresh_copy(self):
        with tempfile.TemporaryDirectory() as t:
            shutil.copytree(os.path.join(ROOT, "harness"), os.path.join(t, "harness"),
                            ignore=shutil.ignore_patterns("__pycache__"))
            env = no_sources(t, GROUNDTRUTH_CLIENT_HOME=os.path.join(t, "absent-home"))
            r = subprocess.run([sys.executable, "harness/night.py", "--date", DATE, "--dry-run", "devin"], cwd=t, env=env,
                               capture_output=True, text=True, timeout=120)
            self.assertEqual(r.returncode, 0, r.stderr)
            made = [os.path.join(d, n) for d, dirs, files in os.walk(t) for n in dirs + files
                    if n == "__pycache__" or n.endswith(".pyc")]
            self.assertEqual(made, [])
            self.assertFalse(os.path.exists(os.path.join(t, "absent-home")))


class Point4ZeroCalls(unittest.TestCase):
    """4: an explicit zero-call Muse response is no call; an absent count is unknown; the builder never publishes a
    check with zero calls."""

    def shape(self, payload):
        lines = fx("muse", "warm")["stdout"].splitlines()
        usage = json.loads(lines[1])
        usage["payload"] = payload
        return "\n".join([lines[0], json.dumps(usage), lines[2]])

    def test_zero_and_absent_counts(self):
        self.assertEqual(C.Muse("m").parse(self.shape({"calls": 0, "models": []}), "", 0, {}).calls, 0)
        self.assertIsNone(C.Muse("m").parse(self.shape({"models": []}), "", 0, {}).calls)
        self.assertEqual(C.Muse("m").parse(fx("muse", "warm")["stdout"], "", 0, {}).calls, 1)

    def test_the_review_s_case_is_not_a_check_and_not_published(self):
        parsed = C.Muse("m").parse(self.shape({"calls": 0, "models": []}), "", 0, {})
        clock = FakeClock()
        fake = FakeClient(clock, ttl=3600)
        real = fake.resume
        fake.resume = lambda h, p: real(h, p) if h == "s1" else parsed.record()
        reason, events = loop(fake, clock, ages=("2.5m",), replicas=1)
        self.assertFalse([e for e in events if e["event"] == "check" and e["age"] == "2.5m"])
        self.assertTrue([e for e in events if e["event"] == "check-invalid" and e["age"] == "2.5m"])
        # The builder, given such a check anyway (an older probe's file), refuses it.
        with tempfile.TemporaryDirectory() as t:
            start = {"event": "start", "harness": "muse", "client_version": "f", "isolation": probe.ISOLATION,
                     "model": "muse-wonder-1.0", "at": "2026-11-23T20:00:00Z"}
            bad = {"event": "check", "age": "2.5m", "ageSec": 150, "late": False, "warm": False,
                   "usage": {"total": 0, "cached": 0, "calls": 0, "model_matches": True}}
            control = {"event": "check", "age": "control", "late": False, "warm": True,
                       "usage": {"total": 9, "cached": 9, "calls": 1, "model_matches": True}}
            path = os.path.join(t, "MC1.jsonl")
            write(path, "".join(json.dumps(x) + "\n" for x in (start, control, bad, {"event": "done"})))
            with self.assertRaisesRegex(SystemExit, "model requests, not 1"):
                B.build_cache({"runs": [{"id": "MC1", "file": path, "route": "meta-subscription",
                                         "model": "muse-wonder-1.0"}]})


class Point5Launcher(Owner):
    """5: each worker's pid in the lock as soon as it starts; the review's interrupted launch (since the seventh review
    `stop` signals only the pids the lock records: a process it does not record is never signalled)."""

    def setUp(self):
        super().setUp()
        self.worker = os.path.join(self.tmp, "worker.py")
        write(self.worker, "import time\ntime.sleep(30)\n")
        self.client_home()
        night.make_night_dir(DATE)
        for p in (night.everyday_path(DATE), night.reviewed_path(DATE)):
            write(p, "fixture")
        self.pids = []
        self.addCleanup(self.cleanup)

    def cleanup(self):
        for pid in self.pids:
            try:
                os.killpg(pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass

    def command(self, step, date, launch_id=None, delay=None):
        return [sys.executable, "-B", self.worker, "--label", step["id"], "--launch-id", launch_id]

    def wait_alive(self, pid, rid, lid):
        for _ in range(100):
            if night.alive(rid, {"pid": pid, "started": night.process_started(pid)}, lid):
                return True
            time.sleep(0.02)
        return False

    def test_each_pid_is_in_the_lock_as_soon_as_its_worker_starts(self):
        seen = []

        def popen(argv, **kw):
            lock = night.read_lock(DATE, "codex")
            seen.append(sorted(lock["runs"]))
            return mock.Mock(pid=7000 + len(seen))
        night.go_clients(["codex"], DATE, popen=popen, out=lambda *_: None)
        self.assertEqual(seen[1], ["CX1"])
        self.assertEqual(seen[2], ["CX1", "CX2"])

    def test_the_review_s_interrupted_launch(self):
        # The launcher dies right after its first worker started (os._exit, before anything else is written).
        script = os.path.join(self.tmp, "launcher.py")
        write(script, f"""import os, sys
sys.path.insert(0, {os.path.join(ROOT, 'harness')!r})
import night
night.ROOT = {self.repo!r}
night.hook_problem = lambda *a, **k: None
night.command = lambda step, date, launch_id=None, delay=None: [sys.executable, "-B", {self.worker!r}, "--label",
                                                               step["id"], "--launch-id", launch_id]
night.write_lock = lambda *a, **k: None  # as if it died before recording anything after the first worker
def out(line):
    if line.startswith("CX1 pid "):
        open({os.path.join(self.tmp, 'pid')!r}, "w").write(line.split()[2].rstrip(","))
        os._exit(73)
night.go_clients(["codex"], {DATE!r}, out=out)
""")
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        r = subprocess.run([sys.executable, script], env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 73, r.stderr)
        with open(os.path.join(self.tmp, "pid")) as f:
            orphan = int(f.read())
        self.pids.append(orphan)
        lock = night.read_lock(DATE, "codex")
        self.assertEqual(lock["runs"], {})  # the review's state: nothing recorded
        self.assertTrue(self.wait_alive(orphan, "CX1", lock["launch_id"]))
        # A launcher that dies between a start and its record leaves this. `stop` acts on recorded pids only, so this
        # stand-in orphan is not signalled; a real run (harness/probe.py) is never left so: it waits for its pid in
        # the lock before its first client call and exits without one (test_eighth_review).
        self.assertEqual(night.status(DATE, out=lambda *_: None), {})
        self.assertEqual(night.stop("all", DATE, dry=True, out=lambda *_: None), [])
        self.assertEqual(night.stop("all", DATE, out=lambda *_: None), [])
        self.assertTrue(night.process_command(orphan))

    def test_a_recorded_run_that_ended_meanwhile(self):
        # Two recorded runs; the first ends between the lookup and the signal: passed over, the other still signalled.
        lid = f"{DATE}-devin-0123456789ab"
        ps = [subprocess.Popen([sys.executable, "-B", self.worker, "--label", rid, "--launch-id", lid],
                               start_new_session=True) for rid in ("DV1", "DV2")]
        self.pids += [p.pid for p in ps]
        for p, rid in zip(ps, ("DV1", "DV2")):
            self.assertTrue(self.wait_alive(p.pid, rid, lid))
        runs = {rid: {"pid": p.pid, "started": night.process_started(p.pid)} for p, rid in zip(ps, ("DV1", "DV2"))}
        os.makedirs(os.path.dirname(night.lock_path(DATE, "devin")), exist_ok=True)
        write(night.lock_path(DATE, "devin"), json.dumps({"launch_id": lid, "runs": runs}))
        sent = []

        def kill(pid, sig):
            if not sent:
                sent.append("gone")
                raise ProcessLookupError
            sent.append(pid)
        self.assertEqual(night.stop("devin", DATE, kill=kill, out=lambda *_: None), [ps[1].pid])
        self.assertEqual(sent, ["gone", ps[1].pid])
        self.assertEqual(night.stop("devin", DATE, out=lambda *_: None), [p.pid for p in ps])
        for p in ps:
            self.assertEqual(p.wait(timeout=10), -signal.SIGTERM)


class Point6Model(unittest.TestCase):
    """6 (M-1): a resumed turn without its own model evidence is unknown; the builder refuses a check answered by
    another model than the manifest's."""

    def rollout(self, t, tid, records):
        path = os.path.join(t, "state", "sessions", "2099", "01", "01", f"rollout-2099-01-01T00-00-00-{tid}.jsonl")
        write(path, "".join(json.dumps(r) + "\n" for r in records))

    def test_the_review_s_two_cases(self):
        f = fx("codex", "warm")
        tid = f["expect"]["handle"]
        with tempfile.TemporaryDirectory() as t:
            ctx = {"type": "turn_context", "payload": {"model": "gpt-6-luna", "turn_id": "fixture-prime"}}
            reroute = {"type": "event_msg", "payload": {"type": "model_reroute", "from_model": "gpt-6-luna",
                                                        "to_model": "gpt-6-astra"}}
            done = {"type": "event_msg", "payload": {"type": "task_complete", "turn_id": "fixture-prime"}}
            started = {"type": "event_msg", "payload": {"type": "task_started", "turn_id": "fixture-resume"}}
            records, turn = [], []

            def run(*a, **k):  # each invocation appends its own turn to the session file
                records.extend(turn)
                self.rollout(t, tid, records)
                return 0, f["stdout"], ""
            s = C.Session(C.Codex("gpt-6-luna"), env={}, io=t + "/io", work=t + "/work", home=os.path.join(t, "state"),
                          run=run)
            turn[:] = [ctx]
            luna = s.resume(tid, "p").record()
            self.assertEqual((luna["model"], luna["model_evidence"]), ("gpt-6-luna", "own-turn"))
            # (At 7cc500c a turn that also carried a record of the earlier turn, or a reroute, gave a model; now the
            # earlier turn's id, or two models for one turn, make it ambiguous: test_fifth_review.)
            turn[:] = [done, dict(ctx, payload=dict(ctx["payload"], turn_id="t2")), dict(reroute, payload=dict(
                reroute["payload"], turn_id="t2"))]
            u = s.resume(tid, "p")
            self.assertEqual((u.model, u.model_issue), (None, "ambiguous-model"))
            turn[:] = [started]
            u = s.resume(tid, "p")
            self.assertEqual((u.model, u.model_issue), (None, "no-model"))
            # The builder: warm checks answered by Astra under the scheduled Luna entry (since the ninth review a public
            # line says only whether the reported model is the requested one: model_matches).
            luna = {**{k: v for k, v in luna.items() if k != "model"}, "model_matches": True}
            astra = dict(luna, model_matches=False)
            start = {"event": "start", "harness": "codex", "client_version": "f", "isolation": probe.ISOLATION,
                     "model": "gpt-6-luna", "at": "2026-11-23T20:00:00Z"}
            rows = [start, {"event": "baseline", "usage": luna},
                    {"event": "check", "age": "control", "warm": True, "late": False, "usage": astra},
                    {"event": "check", "age": "2.5m", "warm": True, "late": False, "usage": astra}, {"event": "done"}]
            path = os.path.join(t, "CX6.jsonl")
            write(path, "".join(json.dumps(x) + "\n" for x in rows))
            run = {"id": "CX6", "file": path, "route": "codex-subscription", "model": "gpt-6-luna"}
            with self.assertRaisesRegex(SystemExit, "model_matches"):
                B.build_cache({"runs": [run]})
            for r in rows[2:4]:
                r["usage"] = luna
            write(path, "".join(json.dumps(x) + "\n" for x in rows))
            # Since the sixth review nothing of an own-client night is built before its audit (AUDIT.md beside the
            # night's results; test_sixth_review builds the same rows from an audited night).
            with self.assertRaisesRegex(SystemExit, "own-clients-<date>"):
                B.build_cache({"runs": [run]})

    def test_a_client_s_own_suffixes_are_the_same_model(self):
        self.assertTrue(B.same_model("nemotron-3-5-super-none", "nemotron-3-5-super"))
        self.assertTrue(B.same_model("claude-haiku-5-5-20261001", "claude-haiku-5-5"))
        self.assertFalse(B.same_model("gpt-6-astra", "gpt-6-luna"))


class Point7Scan(unittest.TestCase):
    """7: the RUN checklist's scan reads no proxy or pi file, finds the Muse key by the night's fingerprint, and
    reads the console logs."""

    def test_no_proxy_file_is_opened_and_the_fingerprint_is_found_in_a_console_log(self):
        with tempfile.TemporaryDirectory() as t:
            config = os.path.join(t, "provimux.conf")
            write(config, "api-keys: [x]\n", 0o000)  # unreadable: the review denied it
            value = "synthetic-muse-key-0123456789"
            import scan_secrets
            fp = os.path.join(t, "fingerprints.json")
            scan_secrets.remember(value, "META_API_KEY", path=fp)
            root = os.path.join(t, "repo")
            subprocess.run(["git", "init", "-q", root], check=True)
            write(os.path.join(root, ".gitignore"), "results/**/logs/\n")
            write(os.path.join(root, "results", "own-clients-x", "MC1.jsonl"), '{"event": "done"}\n')
            env = no_sources(t, SCAN_CONFIG=config, SCAN_CLIENT_KEYS=config, SCAN_FINGERPRINTS=fp)
            for args in (["--own-clients", "--git", root], ["--own-clients", os.path.join(root, "results")]):
                r = subprocess.run([sys.executable, SCAN, *args], env=env, capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, (args, r.stdout, r.stderr))
            write(os.path.join(root, "results", "own-clients-x", "logs", "MC1.log"), "diagnostic " + value + "\n")
            r = subprocess.run([sys.executable, SCAN, "--own-clients", os.path.join(root, "results")], env=env,
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("MC1.log", r.stdout)
            self.assertNotIn(value, r.stdout)

    def test_the_run_document_names_the_scan(self):
        with open(os.path.join(ROOT, "docs", "own-clients-RUN.md")) as f:
            text = f.read()
        self.assertTrue("scan_secrets.py --own-clients" in text)
        self.assertFalse("python3 harness/scan_secrets.py --git .` ends" in text)


class Point8Owner(Owner):
    """8: a Keychain that cannot be listed is said so, never "nothing changed". (The overage part left with Claude: the
    first night runs no Claude Code.)"""

    def test_an_unlisted_keychain_is_reported_as_not_compared(self):
        self.client_home()
        said = []
        night.untouched(DATE, "save", user_home=self.user, lister=lambda: None, out=said.append)
        self.assertIn("NOT the Keychain", said[-1])
        lines = []
        changed = night.untouched(DATE, "report", user_home=self.user, lister=lambda: None, out=lines.append, at="t")
        self.assertTrue(any(x.startswith("Keychain not compared") for x in changed))
        self.assertFalse(any("nothing changed" in x for x in lines), lines)
        with open(night.report_path(DATE, "t")) as f:
            self.assertIn("Keychain not compared", f.read())


if __name__ == "__main__":
    unittest.main()
