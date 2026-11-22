"""The safety check of bc99948 (the seventh review): its four points, each replayed from the review's receipts, every
test failing at bc99948. Nothing is sent and no real client is run: stand-in workers, a passive `grep`, stand-in
status replies and session files, a disposable clone for the commit hook.

    python3 -m unittest discover -s test -p "test_*.py"
"""
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
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


class Point1Stop(Owner):
    """1: only the pids the night's lock records, each checked by its recorded start time and its command line (label
    and the lock's exact launch id; the launcher: its recorded command line); never a process group; no search for
    the launch id elsewhere (stop.log: a passive `grep` for the id qualified)."""

    def setUp(self):
        super().setUp()
        self.worker = os.path.join(self.tmp, "worker.py")
        write(self.worker, "import time\ntime.sleep(60)\n")
        self.client_home()
        night.make_night_dir(DATE)
        os.mkdir(os.path.join(night.night_dir(DATE), "launch"), 0o700)
        self.procs = []
        self.addCleanup(self.cleanup)

    def cleanup(self):
        for p in self.procs:
            if p.poll() is None:
                p.kill()
            p.wait(timeout=10)

    def spawn(self, argv, **kw):
        p = subprocess.Popen(argv, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kw)
        self.procs.append(p)
        for _ in range(200):
            if night.process_command(p.pid).endswith(argv[-1]):
                break
            time.sleep(0.02)
        return p

    def lock(self, runs, **extra):
        lid = f"{DATE}-codex-0123456789ab"
        write(night.lock_path(DATE, "codex"), json.dumps({"launch_id": lid, "launcher_pid": 1234567,
                                                          "launcher_started": "never", "launcher_command": "never",
                                                          "runs": runs, **extra}))
        return lid

    def test_the_review_s_passive_observer_survives(self):
        lid = f"{DATE}-codex-0123456789ab"
        w = self.spawn([sys.executable, "-B", self.worker, "--label", "CX1", "--launch-id", lid])
        observer = self.spawn(["grep", "-F", "--", lid], stdin=subprocess.PIPE)  # reads its stdin: never ends alone
        self.lock({"CX1": {"pid": w.pid, "started": night.process_started(w.pid)}})
        sent, real_kill = [], os.kill

        def deliver(pid, sig):
            sent.append(("pid", pid))
            if pid == w.pid:
                real_kill(pid, sig)

        def group(pgid, sig):
            sent.append(("group", pgid))  # never delivered
        with mock.patch.object(night.os, "kill", side_effect=deliver), \
                mock.patch.object(night.os, "killpg", side_effect=group):
            signalled = night.stop("codex", DATE, out=lambda *_: None, wait=0.2)
        self.assertEqual(sent, [("pid", w.pid)])
        self.assertEqual(signalled, [w.pid])
        self.assertEqual(w.wait(timeout=10), -signal.SIGTERM)
        self.assertIsNone(observer.poll())

    def test_a_recorded_pid_is_signalled_only_with_its_recorded_start_time(self):
        w = self.spawn([sys.executable, "-B", self.worker, "--label", "CX1", "--launch-id", f"{DATE}-codex-0123456789ab"])
        for started, expected in (("Mon Jan  1 00:00:00 2001", []), (None, []), (night.process_started(w.pid), [w.pid])):
            with self.subTest(started=started):
                self.lock({"CX1": {"pid": w.pid, "started": started}})
                sent = []
                night.stop("codex", DATE, kill=lambda pid, sig: sent.append(pid), out=lambda *_: None, wait=0.2)
                self.assertEqual(sent, expected)
        self.assertIsNone(w.poll())

    def test_the_launcher_is_signalled_only_with_its_recorded_command_line(self):
        launcher = self.spawn([sys.executable, "-B", self.worker, "night.py", "--date", DATE, "--go", "codex"])
        when = night.process_started(launcher.pid)
        for command, expected in (("python3 harness/night.py --date 2099-06-19 --go devin", []),
                                  (night.process_command(launcher.pid), [launcher.pid])):
            with self.subTest(command=command):
                self.lock({}, launcher_pid=launcher.pid, launcher_started=when, launcher_command=command)
                sent = []
                night.stop("codex", DATE, kill=lambda pid, sig: sent.append(pid), out=lambda *_: None, wait=0.2,
                           sleep=lambda s: None)
                self.assertEqual(sent, expected)

    def test_the_launcher_cannot_be_ended_between_a_start_and_its_record(self):
        # Its ending signals are held back from the start to the record, and the run gets the launcher's own mask.
        for p in (night.everyday_path(DATE), night.reviewed_path(DATE)):
            write(p, "fixture")
        mask_file = os.path.join(self.tmp, "mask")
        script = os.path.join(self.tmp, "mask.py")
        write(script, f"import signal, sys\nopen({mask_file!r}, 'w').write(repr(sorted(int(s) for s in "
                      "signal.pthread_sigmask(signal.SIG_BLOCK, []))))\n")
        held = []
        real_popen = subprocess.Popen

        def popen(argv, **kw):
            held.append(signal.pthread_sigmask(signal.SIG_BLOCK, []))
            if held[1:]:
                return mock.Mock(pid=987654)
            p = real_popen([sys.executable, "-B", script], **kw)
            p.wait(timeout=10)
            return p
        with mock.patch.object(night.os, "kill", side_effect=lambda pid, sig: None), \
                mock.patch.object(night, "process_started", lambda pid: "T"):
            night.go_clients(["codex"], DATE, popen=popen, out=lambda *_: None)
        self.assertTrue(all(night.HELD <= set(h) for h in held))
        self.assertFalse(night.HELD & set(signal.pthread_sigmask(signal.SIG_BLOCK, [])))  # released after
        with open(mask_file) as f:
            self.assertFalse({int(s) for s in night.HELD} & set(json.loads(f.read())))

    def test_a_launched_probe_ends_its_client_with_it(self):
        # `stop` signals the probe's pid alone: the probe ends the client invocation under way with itself.
        script = os.path.join(self.tmp, "launched.py")
        pidfile = os.path.join(self.tmp, "child")
        write(script, f"""import subprocess, sys, shutil
sys.path.insert(0, {os.path.join(ROOT, 'harness')!r})
import probe
probe.shutil.which = lambda name: None  # no caffeinate here
probe.stay_awake_and_stoppable(True)
p = subprocess.Popen([sys.executable, "-B", {self.worker!r}, "client"])
open({pidfile!r}, "w").write(str(p.pid))
try:
    p.wait()
finally:
    p.kill()
""")
        p = self.spawn([sys.executable, "-B", script])
        for _ in range(200):
            if os.path.exists(pidfile) and open(pidfile).read():
                break
            time.sleep(0.02)
        child = int(open(pidfile).read())
        os.kill(p.pid, signal.SIGTERM)
        self.assertEqual(p.wait(timeout=10), 128 + signal.SIGTERM)
        for _ in range(200):
            if not night.process_command(child):
                break
            time.sleep(0.02)
        self.assertEqual(night.process_command(child), "")

    def test_no_search_is_left(self):
        for gone in ("workers", "process_table", "groups_of", "launchers", "launch_mark"):
            self.assertFalse(hasattr(night, gone), gone)
        with open(os.path.join(ROOT, "harness", "night.py")) as f:
            self.assertNotIn("killpg", f.read())


class Point2DevinStatus(unittest.TestCase):
    """2: every control character removed (C0, C1, escape sequences of both); no `api`, `token`, `key`, `pat` (a word)
    or `personal access`; only the accepted whole lines; any other reply refused and shown (status-profile.log:5)."""

    def test_the_review_s_replies_and_the_accepted_lines(self):
        devin = C.Devin("m")
        for out, ok in (("Logged in (via PAT)", False), ("Logged in (via to\u009b0mken)", False),
                        ("Logged in (via to\x9b0mken)", False), ("Logged in (via pat)", False),
                        ("Logged in (via personal access)", False), ("Logged in (via Personal  Access token)", False),
                        ("Logged in (via sso)", False), ("Logged in (via Browser)", False),
                        ("Logged in as two words", False), ("Logged in\nOrganisation: x", False),
                        ("Logged in (via \x1b]8;;http://x/token\x07web\x1b]8;;\x07)", False), ("", False),
                        ("Logged in", True), ("Logged in.", True), ("Logged in as fixture", True),
                        ("Logged in (via browser)", True), ("Logged in (via web)", True), ("Logged in (via oauth)", True),
                        ("\x1b[1mLogged in\x1b[0m", True), ("\u009b1mLogged in\u009b0m as fixture", True),
                        ("Logged in as patron", True)):
            with self.subTest(out=out):
                why = C.login_ok(devin, 0, out, "")
                self.assertEqual(why is None, ok, why)
        why = C.login_ok(devin, 0, "Logged in (via sso)\nWorkspace fixture", "")
        self.assertIn('"Logged in (via sso)\\nWorkspace fixture"', why)  # shown to the owner as it reads

    def test_bytes_that_are_not_text_are_refused(self):
        def run(argv, **kw):
            raise UnicodeDecodeError("utf-8", b"\x9b", 0, 1, "invalid start byte")
        with tempfile.TemporaryDirectory() as t, mock.patch.object(C, "CONFINED", False):
            self.assertIn("not text", C.login_status(C.Devin("m"), t, env={"HOME": t, "TMPDIR": t}, run=run))


class Point3Gate(unittest.TestCase):
    """3: nothing of an unaudited night is published or committed: no link under results/own-clients-*, the night
    read from where the file lies, whatever its timestamp, its `excluded` entries too, and the commit hook
    (audit.log:6, raw-staging.log)."""

    def rows(self, at="2026-11-23T01:00:00+00:00"):
        with open(os.path.join(R5.SAVED, "CX6-old-context-after-complete.jsonl")) as f:
            rows = [json.loads(x) for x in f]
        for r in rows:
            if r["event"] == "check":
                r["usage"]["model_evidence"] = "own-turn"
        rows.insert(-1, {"event": "model-scan", "final": True, "other_models": [], "unreadable": False})
        rows[0]["at"] = at
        return rows

    def tree(self, root, rows, audited=()):
        for night_date in audited:
            write(os.path.join(root, "results", f"own-clients-{night_date}", "AUDIT.md"), B.AUDIT_FIRST_LINE + "\n")
        write(os.path.join(root, "results", "own-clients-2026-11-23", "CX6.jsonl"),
              "".join(json.dumps(r) + "\n" for r in rows))

    def build(self, root, path, excluded=()):
        with mock.patch.object(B, "ROOT", root):
            return B.build_cache({"runs": [{"id": "own-clients-2026-11-23/CX6", "route": "codex-subscription",
                                            "file": path, "model": MODEL}]}) if path else B.build_excluded(
                {"excluded": list(excluded)})

    def test_a_link_from_an_audited_night(self):
        with tempfile.TemporaryDirectory() as root:
            self.tree(root, self.rows(), audited=("2026-11-22",))
            os.symlink(os.path.join(root, "results", "own-clients-2026-11-23", "CX6.jsonl"),
                       os.path.join(root, "results", "own-clients-2026-11-22", "CX6.jsonl"))
            with self.assertRaisesRegex(SystemExit, "symbolic link"):
                self.build(root, "results/own-clients-2026-11-22/CX6.jsonl")
            self.assertTrue(any("symbolic link" in p for p in B.audit_gate(root)))

    def test_any_link_under_a_night_stops_the_build(self):
        with tempfile.TemporaryDirectory() as root:
            self.tree(root, self.rows(), audited=("2026-11-23",))
            self.assertEqual(self.build(root, "results/own-clients-2026-11-23/CX6.jsonl")[0]["model"], MODEL)
            os.symlink("/tmp", os.path.join(root, "results", "own-clients-2026-11-23", "elsewhere"))
            with self.assertRaisesRegex(SystemExit, "symbolic link"):
                self.build(root, "results/own-clients-2026-11-23/CX6.jsonl")

    def test_an_older_timestamp_in_the_night_s_folder(self):
        with tempfile.TemporaryDirectory() as root:
            self.tree(root, self.rows(at="2026-11-21T23:58:59+00:00"))
            with self.assertRaisesRegex(SystemExit, "no AUDIT.md"):
                self.build(root, "results/own-clients-2026-11-23/CX6.jsonl")

    def test_an_excluded_entry_of_an_unaudited_night(self):
        with tempfile.TemporaryDirectory() as root:
            self.tree(root, self.rows())
            entry = {"id": "own-clients-2026-11-23/CX6", "reason": "Control was cold."}
            with self.assertRaisesRegex(SystemExit, "no AUDIT.md"):
                self.build(root, None, [entry])
            write(os.path.join(root, "results", "own-clients-2026-11-23", "AUDIT.md"), B.AUDIT_FIRST_LINE + "\n")
            self.assertEqual(self.build(root, None, [entry]), [entry])
            self.assertEqual(self.build(root, None, [{"id": "cpa-8.0.53/C2", "reason": "x"}]),
                             [{"id": "cpa-8.0.53/C2", "reason": "x"}])

    def test_the_commit_hook_refuses_a_raw_file_before_the_audit(self):
        # raw-staging.log: a disposable clone of the branch with this tree's hook and code; a night's raw JSONL staged
        # alone, then with its AUDIT.md.
        with tempfile.TemporaryDirectory() as t:
            clone = os.path.join(t, "clone")
            env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
            subprocess.run(["git", "clone", "-q", ROOT, clone], check=True, env=env)
            for rel in ("scripts/pre-commit", "scripts/build_observed.py", "harness/scan_secrets.py"):
                shutil.copyfile(os.path.join(ROOT, rel), os.path.join(clone, rel))
            nothing = os.path.join(t, "nothing")
            env.update(SCAN_CLIENT_KEYS=nothing, SCAN_KEYS_FILE=nothing, SCAN_CONFIG=nothing,
                       SCAN_LOGINS=nothing + "/*.json", SCAN_FINGERPRINTS=nothing)
            git = lambda *a: subprocess.run(["git", *a], cwd=clone, env=env, check=True)  # noqa: E731
            git("add", "-A")
            git("-c", "user.name=t", "-c", "user.email=t" + "@" + "example.invalid", "commit", "-q", "--no-verify", "--allow-empty", "-m", "code")
            write(os.path.join(clone, "results", "own-clients-2026-11-23", "CX6.jsonl"), '{"event": "done"}\n')
            git("add", "results/own-clients-2026-11-23/CX6.jsonl")
            hook = lambda: subprocess.run(["bash", "scripts/pre-commit"], cwd=clone, env=env,  # noqa: E731
                                          capture_output=True, text=True)
            r = hook()
            self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("audit gate: refused", r.stderr)
            write(os.path.join(clone, "results", "own-clients-2026-11-23", "AUDIT.md"), "# Pending audit\n")
            git("add", "results/own-clients-2026-11-23/AUDIT.md")
            self.assertNotEqual(hook().returncode, 0)
            write(os.path.join(clone, "results", "own-clients-2026-11-23", "AUDIT.md"), B.AUDIT_FIRST_LINE + "\n")
            git("add", "results/own-clients-2026-11-23/AUDIT.md")
            r = hook()
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class Point4ModelScan(R5.CodexNight):
    """4: the public model-scan event carries `final`, `other_models` (model-id-shaped names, anything else `?`) and
    `unreadable`, nothing else; the session files' own strings go to the console log only (calendar-fixtures.log:2,
    path-test.log)."""

    def test_the_review_s_strings_never_reach_the_public_file(self):
        path, text, events, row = self.run_case("private-strings")
        scans = [e for e in events if e["event"] == "model-scan"]
        for e in scans:
            self.assertEqual(set(e), {"event", "final", "other_models", "unreadable", "at"})
            self.assertIsInstance(e["unreadable"], bool)
            self.assertTrue(all(n == "?" or probe.PUBLIC_MODEL.fullmatch(n) for n in e["other_models"]))
        self.assertEqual(scans[-1]["other_models"], ["19.28.3746", "?"])
        for private in self.PRIVATE[1:]:
            self.assertNotIn(private, text)
        for word in ("Volumes", "auth.json", "t345synthetic", "unavailable", "Gpt-Upper"):
            self.assertNotIn(word, text)
        self.assertIn("model-scan: other models named in the session files", self.console)
        with self.assertRaises(SystemExit):
            R5.build_in_night(events)

    def test_an_unreadable_file_is_a_boolean(self):
        path, text, events, row = self.run_case("matching-evidence")
        self.assertTrue(all(e["unreadable"] is False for e in events if e["event"] == "model-scan"))
        rows = [dict(e, unreadable=True) if e["event"] == "model-scan" and e["final"] else e for e in events]
        with self.assertRaisesRegex(SystemExit, "could not all be read"):
            R5.build_in_night(rows)


if __name__ == "__main__":
    unittest.main()
