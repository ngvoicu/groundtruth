"""The safety check of 1a1ac8d (the eighth review): its four points, each replayed from the review's receipts and each
failing at 1a1ac8d. Nothing is sent and no real client is run: a stand-in client that records its invocations, stand-in
launchers, session files and a scratch Git repository with a linked worktree.

    python3 -m unittest discover -s test -p "test_*.py"
"""
import io
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
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
import test_second_review as R2  # noqa: E402  (as modules: their tests are not collected twice)
import test_fifth_review as R5  # noqa: E402

Owner = R2.Owner
write, DATE = R2.write, R2.DATE
MODEL = R5.MODEL
# The real check, before Owner replaces it for the fixture repositories (which are no Git checkouts).
REAL_HOOK_PROBLEM = getattr(night, "hook_problem", None)

# A run of harness/probe.py as the launcher starts it, with a stand-in client: every invocation it reaches is appended
# to CALLS before it answers. The probe's own code decides whether an invocation is made.
WORKER = """import json, os, sys
sys.path.insert(0, os.environ["HARNESS"])
import clients as C, probe
probe.shutil.which = lambda name: None  # no caffeinate here
probe.ROOT = os.environ["FIXTURE_REPO"]
C.CONFINED = False

def standin(argv, env, cwd, stdin, timeout):
    with open(os.environ["CALLS"], "a") as f:
        f.write(json.dumps(argv[-4:]) + "\\n")
    if "--version" in argv:
        return 0, "codex-cli 0.0.0", ""
    if "status" in argv:
        return 0, "Logged in using ChatGPT", ""
    return 1, "", "stand-in"
C._run = standin
probe.main(sys.argv[1:])
"""

# The review's held launcher (stop-replay.py, `interrupted-before-record`): it stops between starting CX1 and recording
# its pid, until told to go on.
LAUNCHER = """import os, sys, subprocess
sys.path.insert(0, os.environ["HARNESS"])
import night
night.ROOT = os.environ["FIXTURE_REPO"]
night.hook_problem = lambda *a, **k: None
night.PARTS["codex"] = night.PARTS["codex"][:1]
night.command = lambda step, date, launch_id=None, delay=None: [
    sys.executable, "-B", os.environ["WORKER"], "--harness", "codex", "--model", "gpt-6-luna", "--label", step["id"],
    "--ages", "2.5m", "--words", "20", "--replicas", "1", "--out", os.environ["OUT"], "--launch-id", launch_id]
def popen(args, **kw):
    p = subprocess.Popen(args, **kw)
    print("CHILD " + str(p.pid), flush=True)
    input()
    return p
night.go_clients(["codex"], os.environ["DAY"], popen=popen, out=lambda *_: None)
"""


class Point1StopMark(Owner):
    """1: the stop mark is the authority, signals the fast path. A launched run looks for the mark immediately before
    every client invocation and exits without calling the client once it exists; before its first one it waits for its
    own pid in the lock. `stop` sets the mark, then signals the recorded pids, and never says "no run alive" while a
    lock exists (stop.log, stop-default.log)."""

    def setUp(self):
        super().setUp()
        self.base = self.client_home()
        write(os.path.join(self.base, "codex-cli", "auth.json"), "{}", 0o600)
        night.make_night_dir(DATE)
        for p in (night.everyday_path(DATE), night.reviewed_path(DATE)):
            write(p, "fixture")
        self.calls = os.path.join(self.tmp, "calls")
        self.worker = os.path.join(self.tmp, "worker.py")
        write(self.worker, WORKER)
        self.procs, self.children = [], []
        self.addCleanup(self.cleanup)

    def cleanup(self):
        for pid in self.children:
            if self.running(pid):
                os.kill(pid, signal.SIGKILL)
        for p in self.procs:
            if p.poll() is None:
                p.kill()
            p.wait(timeout=10)
            for f in (p.stdin, p.stdout, p.stderr):
                f.close()

    def running(self, pid):
        return self.worker in night.process_command(pid)

    def client_calls(self):
        try:
            with open(self.calls) as f:
                return [json.loads(x) for x in f if x.strip()]
        except FileNotFoundError:
            return []

    def held_launcher(self):
        script = os.path.join(self.tmp, "launcher.py")
        write(script, LAUNCHER)
        env = dict(os.environ, HARNESS=os.path.join(ROOT, "harness"), FIXTURE_REPO=self.repo, DAY=DATE,
                   WORKER=self.worker, CALLS=self.calls, OUT=os.path.join(self.repo, "results", f"own-clients-{DATE}"),
                   PYTHONDONTWRITEBYTECODE="1")
        p = subprocess.Popen([sys.executable, "-B", script], env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True, start_new_session=True)
        self.procs.append(p)
        line = p.stdout.readline().strip()
        self.assertTrue(line.startswith("CHILD "), line + p.stderr.read() if p.poll() is not None else line)
        child = int(line.split()[1])
        self.children.append(child)
        return p, child

    def release(self, p):
        try:
            p.stdin.write("go on\n")
            p.stdin.flush()
        except (BrokenPipeError, OSError):
            pass

    def console(self):
        with open(os.path.join(self.repo, "results", f"own-clients-{DATE}", "logs", "CX1.log")) as f:
            return f.read()

    def ended(self, pid, within=15.0):
        end = time.monotonic() + within
        while time.monotonic() < end:
            if not self.running(pid):
                return True
            time.sleep(0.05)
        return False

    def test_the_review_s_held_launcher_replay(self):
        # stop-default.log: the launcher is held after starting CX1 and before recording its pid; `stop` returns.
        # Signals are delivered only to the launcher (the lock records no run yet). The run makes no client call.
        launcher, child = self.held_launcher()
        lines, sent = [], []

        def kill(pid, sig):
            self.assertIn(pid, (launcher.pid, child))
            sent.append(pid)
            os.kill(pid, sig)
        night.stop("all", DATE, kill=kill, out=lines.append)
        self.assertTrue(self.ended(child), "the run outlived the stop")
        self.assertEqual(self.client_calls(), [], "a client call after `stop`")
        self.assertIn("CX1: the night's stop mark is set: no client call", self.console())  # ended by the mark
        self.assertEqual(sent, [launcher.pid])
        self.assertEqual(launcher.wait(timeout=10), -signal.SIGTERM)
        self.assertIn("codex: stop mark set; 1 recorded process signalled; a run not yet recorded stops before its "
                      "next client call", lines)
        self.assertFalse(any("no run alive" in x for x in lines), lines)

    def test_the_launcher_records_the_run_after_stop_returned(self):
        # The same replay, but the launcher survives the stop (its signal not delivered) and records CX1 afterwards:
        # the run, now recorded, finds the mark before its first client call.
        launcher, child = self.held_launcher()
        lines = []
        night.stop("all", DATE, kill=lambda pid, sig: None, out=lines.append)
        self.release(launcher)
        self.assertTrue(self.ended(child), "the run outlived the stop")
        self.assertEqual(self.client_calls(), [], "a client call after `stop`")
        self.assertIn("CX1: the night's stop mark is set: no client call", self.console())  # ended by the mark
        launcher.wait(timeout=10)
        self.assertEqual(sorted(night.read_lock(DATE, "codex")["runs"]), ["CX1"])
        self.assertFalse(any("no run alive" in x for x in lines), lines)

    def test_control_without_stop_the_same_run_calls_its_client(self):
        # The fixture can see a call: released with no stop, the recorded run reaches its client.
        launcher, child = self.held_launcher()
        self.release(launcher)
        self.assertEqual(launcher.wait(timeout=10), 0)
        end = time.monotonic() + 15
        while not self.client_calls() and time.monotonic() < end:
            time.sleep(0.05)
        self.assertTrue(self.client_calls())

    def launched_probe(self, mark_at):
        """The probe in this process, as a launched run whose pid the lock records; the stand-in client sets the stop
        mark during invocation number `mark_at` (and answers it as usual). Returns the invocations and the probe's
        exit."""
        lid = f"{DATE}-codex-0123456789ab"
        os.makedirs(os.path.join(night.night_dir(DATE), "launch"), mode=0o700, exist_ok=True)
        write(night.lock_path(DATE, "codex"), json.dumps({"launch_id": lid, "runs": {"CX1": {"pid": os.getpid()}}}))
        calls = []

        def standin(argv, env, cwd, stdin, timeout):
            calls.append(argv)
            if len(calls) == mark_at:
                C.write_private(night.stop_path(DATE, "codex"), "now\n")
            if "--version" in argv:
                return 0, "codex-cli 0.0.0", ""
            if "status" in argv:
                return 0, "Logged in using ChatGPT", ""
            return 1, "", "stand-in"
        with mock.patch.object(C, "_run", side_effect=standin), mock.patch.object(probe, "RETRY_WAIT", 0), \
                mock.patch.object(probe, "stay_awake_and_stoppable"), redirect_stdout(io.StringIO()), \
                redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as e:
            probe.main(["--harness", "codex", "--model", MODEL, "--label", "CX1", "--ages", "2.5m", "--words", "20",
                        "--replicas", "1", "--out", os.path.join(self.repo, "results", "x"), "--launch-id", lid])
        return calls, str(e.exception.code)

    def test_the_mark_is_looked_for_before_every_client_invocation(self):
        # The mark set during the status call, the version call, then the first priming (which fails and would be
        # tried again): no invocation after it.
        for mark_at in (1, 2, 3):
            with self.subTest(mark_at=mark_at):
                if os.path.lexists(night.stop_path(DATE, "codex")):
                    os.remove(night.stop_path(DATE, "codex"))
                calls, why = self.launched_probe(mark_at)
                self.assertEqual(len(calls), mark_at)
                self.assertIn("stop mark is set: no client call", why)

    def test_a_run_waits_for_its_record_and_exits_without_it(self):
        lid = f"{DATE}-codex-0123456789ab"
        os.makedirs(os.path.join(night.night_dir(DATE), "launch"), mode=0o700, exist_ok=True)
        gate = probe.NightStop(self.base, lid, "CX1", "codex")
        with self.assertRaisesRegex(SystemExit, "not in the launch's lock"):
            gate.wait_recorded(0.2)  # no lock
        for runs in ({}, {"CX1": {"pid": os.getpid() + 1}}, {"CX2": {"pid": os.getpid()}}):
            write(night.lock_path(DATE, "codex"), json.dumps({"launch_id": lid, "runs": runs}))
            with self.assertRaisesRegex(SystemExit, "not in the launch's lock"):
                gate.wait_recorded(0.2)
        other = {"launch_id": lid[:-1] + "c", "runs": {"CX1": {"pid": os.getpid()}}}  # another launch's lock
        write(night.lock_path(DATE, "codex"), json.dumps(other))
        with self.assertRaisesRegex(SystemExit, "not in the launch's lock"):
            gate.wait_recorded(0.2)
        write(night.lock_path(DATE, "codex"), json.dumps({"launch_id": lid, "runs": {"CX1": {"pid": os.getpid()}}}))
        gate.wait_recorded(0.2)  # recorded: goes on
        C.write_private(night.stop_path(DATE, "codex"), "now\n")
        with self.assertRaisesRegex(SystemExit, "stop mark is set"):
            gate.wait_recorded(5)
        with self.assertRaisesRegex(SystemExit, "is not a launch of codex"):
            probe.NightStop(self.base, f"{DATE}-devin-0123456789ab", "CX1", "codex")

    def test_stop_s_words(self):
        lines = []
        night.stop("all", DATE, out=lines.append)
        self.assertEqual(lines, ["codex: stop mark set; not launched: nothing to signal",
                                 "devin: stop mark set; not launched: nothing to signal"])
        write(night.lock_path(DATE, "codex"), json.dumps({"launch_id": f"{DATE}-codex-0123456789ab", "runs": {}}))
        lines = []
        night.stop("codex", DATE, out=lines.append)
        self.assertEqual(lines, ["codex: stop mark set; 0 recorded processes signalled; a run not yet recorded stops "
                                 "before its next client call"])

    def test_the_held_signals_are_gone(self):
        self.assertFalse(hasattr(night, "HELD"))
        with open(os.path.join(ROOT, "harness", "night.py")) as f:
            self.assertNotIn("sigmask", f.read())


def git(cwd, *args, env=None, check=True):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t" + "@" + "example.invalid", *args],
                          cwd=cwd, env=env, capture_output=True, text=True, check=check)


class Point2Hook(unittest.TestCase):
    """2: the commit hook in a linked worktree (staged.log, hook-control.log): installed by `git config core.hooksPath
    scripts`, a relative path, each worktree runs its own scripts/pre-commit; the night refuses to start without it."""

    def test_the_review_s_scratch_setup(self):
        # A main checkout whose older hook passes anything, linked under .git/hooks as the old installer did; a linked
        # worktree with this tree's hook and gate. Raw-only index: refused; with a correct AUDIT.md: accepted.
        with tempfile.TemporaryDirectory() as t:
            env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
            nothing = os.path.join(t, "nothing")
            env.update(SCAN_CLIENT_KEYS=nothing, SCAN_KEYS_FILE=nothing, SCAN_CONFIG=nothing,
                       SCAN_LOGINS=nothing + "/*.json", SCAN_FINGERPRINTS=nothing)
            main, wt = os.path.join(t, "main"), os.path.join(t, "wt")
            subprocess.run(["git", "clone", "-q", ROOT, main], check=True, env=env)
            for rel in ("scripts/pre-commit", "scripts/build_observed.py", "harness/scan_secrets.py",
                        "harness/night.py", "harness/probe.py", "harness/clients.py"):
                shutil.copyfile(os.path.join(ROOT, rel), os.path.join(main, rel))
            git(main, "add", "-A", env=env)
            git(main, "commit", "-q", "--no-verify", "--allow-empty", "-m", "candidate", env=env)
            git(main, "branch", "candidate", env=env)
            write(os.path.join(main, "scripts", "pre-commit"), "#!/bin/bash\nexit 0  # the older hook\n")
            git(main, "commit", "-q", "--no-verify", "-am", "older main", env=env)
            os.symlink("../../scripts/pre-commit", os.path.join(main, ".git", "hooks", "pre-commit"))
            git(main, "worktree", "add", "-q", wt, "candidate", env=env)
            # A night no real one can have: the clone carries the published, audited nights of the repository.
            raw = os.path.join("results", "own-clients-2099-01-01")
            write(os.path.join(wt, raw, "CX6.jsonl"), '{"event": "done"}\n')
            git(wt, "add", "--", os.path.join(raw, "CX6.jsonl"), env=env)
            # Before: Git runs the main checkout's older hook, and the night would start.
            self.assertEqual(git(wt, "hook", "run", "pre-commit", env=env, check=False).returncode, 0)
            self.assertIn("core.hooksPath", REAL_HOOK_PROBLEM(wt))
            # The installer, as the documents give it.
            git(wt, "config", "core.hooksPath", "scripts", env=env)
            self.assertIsNone(REAL_HOOK_PROBLEM(wt))
            r = git(wt, "commit", "-q", "-m", "raw only", env=env, check=False)
            self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("audit gate: refused", r.stderr)
            write(os.path.join(wt, raw, "AUDIT.md"), B.AUDIT_FIRST_LINE + "\nScratch fixture.\n")
            git(wt, "add", "--", os.path.join(raw, "AUDIT.md"), env=env)
            r = git(wt, "commit", "-q", "-m", "audited", env=env, check=False)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            # The main checkout runs its own (older) hook, as it did: the setting is relative to each worktree.
            self.assertEqual(git(main, "hook", "run", "pre-commit", env=env, check=False).returncode, 0)

    def test_the_night_refuses_to_start_without_it(self):
        with tempfile.TemporaryDirectory() as t:
            env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
            subprocess.run(["git", "init", "-q", t], check=True, env=env)
            write(os.path.join(t, "scripts", "pre-commit"), "#!/bin/bash\nexit 0\n", 0o755)  # the checkout's own hook
            for value, ok in ((None, False), (".git/hooks", False), ("/elsewhere/scripts", False), ("scripts", True)):
                with self.subTest(value=value):
                    if value:
                        git(t, "config", "core.hooksPath", value, env=env)
                    why = REAL_HOOK_PROBLEM(t)
                    self.assertEqual(why is None, ok, why)
                    with mock.patch.object(night, "ROOT", t), mock.patch.object(night, "hook_problem",
                                                                                REAL_HOOK_PROBLEM):
                        if ok:
                            night.need_hook("--go")
                        else:
                            with self.assertRaisesRegex(SystemExit, "commit hook is not this checkout's own"):
                                night.need_hook("--go")

    def test_guard_and_smoke_check_it_first(self):
        with mock.patch.object(night, "hook_problem", return_value="not set"), \
                mock.patch.dict(os.environ, {"GROUNDTRUTH_CLIENT_HOME": "/nonexistent"}):
            with self.assertRaisesRegex(SystemExit, "commit hook"):
                night.guard(["codex"], DATE)
            with self.assertRaisesRegex(SystemExit, "commit hook"):
                night.go_smoke(DATE, run=lambda *a, **k: self.fail("a smoke run started"))

    def test_the_symlink_installer_is_gone(self):
        for rel in ("README.md", "CONTRIBUTING.md", "scripts/pre-commit", "docs/own-clients-RUN.md"):
            with open(os.path.join(ROOT, rel)) as f:
                text = f.read()
            self.assertNotIn("ln -sf ../../scripts/pre-commit", text, rel)
            self.assertIn("git config core.hooksPath scripts", text, rel)


class Point3ModelScan(R5.CodexNight):
    """3: the public model-scan event carries no text from any session file: `final`, the count `other_models` and
    `unreadable` (close-variants.log:9: a lowercased synthetic key had passed the name pattern)."""

    VARIANTS = ("sk-" + "t345syntheticCanary1234567890", "sk-" + "t345syntheticcanary1234567890",
                "internal-project-label", "19.28.3746", "nested/model/diagnostic", "gpt-6-astra")

    def test_every_variant_of_the_review(self):
        self.PRIVATE = tuple(dict.fromkeys(self.VARIANTS + R5.CodexNight.PRIVATE))
        path, text, events, row = self.run_case("private-strings")
        for value in self.PRIVATE:
            self.assertNotIn(value, text)
            self.assertNotIn(value.lower(), text.lower())
        scans = [e for e in events if e["event"] == "model-scan"]
        self.assertTrue(scans)
        for e in scans:
            self.assertEqual(set(e), {"event", "final", "other_models", "unreadable", "at"})
            self.assertIs(type(e["other_models"]), int)
            self.assertIsInstance(e["unreadable"], bool)
        self.assertEqual(scans[-1]["other_models"], len(self.PRIVATE))
        self.assertIn("internal-project-label", self.console)  # the names: the private console log, for the audit
        with self.assertRaisesRegex(SystemExit, "another model"):
            R5.build_in_night(events)

    def test_the_pattern_and_its_substitute_are_gone(self):
        self.assertFalse(hasattr(probe, "PUBLIC_MODEL"))
        with open(os.path.join(ROOT, "harness", "probe.py")) as f:
            self.assertNotIn('else "?"', f.read())

    def test_the_builder_reads_the_count(self):
        path, text, events, row = self.run_case("matching-evidence")
        self.assertEqual(R5.build_in_night(events)["model"], MODEL)
        for value in (1, [], ["gpt-6-astra"], True, False, None, "0"):
            with self.subTest(other_models=value):
                rows = [dict(e, other_models=value) if e["event"] == "model-scan" and e["final"] else e for e in events]
                with self.assertRaisesRegex(SystemExit, "another model"):
                    R5.build_in_night(rows)


class Point4StopFolder(Owner):
    """4: `stop` resolves the marks' folder and applies the everyday-folder check before it creates anything
    (owner-policy.log:5: with the setting pointed at a fixture ~/.codex, both marks were created there)."""

    def files(self, folder):
        return sorted(os.path.relpath(os.path.join(d, n), folder) for d, ds, fs in os.walk(folder) for n in ds + fs)

    def test_the_review_s_case(self):
        everyday = os.path.join(self.user, ".codex")
        os.makedirs(everyday, mode=0o700)
        write(os.path.join(everyday, "config.toml"), "fixture\n")
        before = self.files(everyday)
        for setting in (everyday, os.path.join(everyday, "sub")):
            with self.subTest(setting=setting), \
                    mock.patch.dict(os.environ, {"GROUNDTRUTH_CLIENT_HOME": setting, "HOME": self.user}):
                with self.assertRaisesRegex(SystemExit, "everyday folder"):
                    night.stop("all", DATE, kill=lambda *a: self.fail("signalled"), out=lambda *_: None)
                self.assertEqual(self.files(everyday), before)

    def test_a_link_to_an_everyday_folder(self):
        base = self.client_home()
        everyday = os.path.join(self.user, ".codex")
        os.makedirs(everyday, mode=0o700)
        os.symlink(everyday, os.path.join(base, f"night-{DATE}"))
        with self.assertRaisesRegex(SystemExit, "everyday folder"):
            night.stop("all", DATE, out=lambda *_: None)
        self.assertEqual(self.files(everyday), [])

    def test_the_campaign_folder_gets_its_marks(self):
        base = self.client_home()
        night.stop("all", DATE, out=lambda *_: None)
        for name in night.CLIENT_PARTS:
            self.assertTrue(os.path.isfile(night.stop_path(DATE, name)))
        self.assertTrue(os.path.isdir(os.path.join(base, f"night-{DATE}", "launch")))


if __name__ == "__main__":
    unittest.main()
