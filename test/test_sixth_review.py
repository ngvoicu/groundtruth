"""The sixth review (at 7827a50) and the change of approach that followed it: the code stays simple and safe for the
owner's computer and accounts, and what is published waits for an audit of the real night. One test class per point:
stop acts only on what its own night's lock records; Devin's status; no client version in public results; Codex's
model at the run's level; the publication gate; the RUN wording. Nothing is sent and no real client is run.

    python3 -m unittest discover -s test -p "test_*.py"
"""
import json
import os
import signal
import stat
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
    """1: `stop` writes the mark, reads its own night's lock and signals only what that lock records (the launcher by
    pid and start time, the runs by pid and command line with the lock's exact launch id). The review's case: an
    unrelated `midnight.py --date <same> --go` and a second campaign under another GROUNDTRUTH_CLIENT_HOME survive."""

    def setUp(self):
        super().setUp()
        self.worker = os.path.join(self.tmp, "worker.py")
        write(self.worker, "import time\ntime.sleep(60)\n")
        self.procs = []
        self.addCleanup(self.cleanup)

    def cleanup(self):
        for p in self.procs:
            if p.poll() is None:
                try:
                    os.killpg(p.pid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    p.kill()
            p.wait(timeout=10)

    def spawn(self, argv):
        p = subprocess.Popen(argv, start_new_session=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        self.procs.append(p)
        for _ in range(200):
            if night.process_command(p.pid).endswith(argv[-1]):
                break
            time.sleep(0.02)
        return p

    def campaign(self, name):
        """A campaign: its own <client-home>, night folder, lock (complete, its own launch id) and live CX1 worker."""
        base = os.path.join(self.tmp, name, "groundtruth-clients")
        os.makedirs(base, mode=0o700)
        lid = f"{DATE}-codex-{os.urandom(6).hex()}"
        w = self.spawn([sys.executable, "-B", self.worker, "--label", "CX1", "--launch-id", lid])
        with mock.patch.dict(os.environ, {"GROUNDTRUTH_CLIENT_HOME": base}):
            os.makedirs(os.path.join(night.night_dir(DATE), "launch"), mode=0o700)
            write(night.lock_path(DATE, "codex"), json.dumps({
                "client": "codex", "date": DATE, "launch_id": lid, "launcher_pid": 1234567, "launcher_started": "never",
                "launcher_command": "never",
                "runs": {"CX1": {"pid": w.pid, "started": night.process_started(w.pid), "delay_s": 0}}}))
        return base, w

    def test_the_review_s_case(self):
        base_a, a = self.campaign("campaign-a")
        base_b, b = self.campaign("campaign-b")
        midnight = os.path.join(self.tmp, "midnight.py")
        write(midnight, "import time\ntime.sleep(60)\n")
        job = self.spawn([sys.executable, "-B", midnight, "--date", DATE, "--go", "codex"])
        other_date = self.spawn([sys.executable, "-B", midnight, "--date", "2099-06-20", "--go", "codex"])
        sent = []

        def only_a(pid, sig):
            sent.append(pid)
            self.assertEqual(pid, a.pid, "a signal to something campaign A did not start")
            os.kill(pid, sig)
        with mock.patch.dict(os.environ, {"GROUNDTRUTH_CLIENT_HOME": base_a}), \
                mock.patch.object(night.os, "killpg", side_effect=AssertionError("a process group signalled")):
            signalled = night.stop("all", DATE, kill=only_a, out=lambda *_: None)
        self.assertEqual((signalled, sent), ([a.pid], [a.pid]))
        self.assertEqual(a.wait(timeout=10), -signal.SIGTERM)
        time.sleep(0.2)
        for p in (b, job, other_date):
            self.assertIsNone(p.poll(), "a process campaign A did not start was ended")
        with mock.patch.dict(os.environ, {"GROUNDTRUTH_CLIENT_HOME": base_b}):
            self.assertFalse(os.path.lexists(night.stop_path(DATE, "codex")))  # B's night is not stopped either

    def test_the_launcher_is_signalled_only_when_its_pid_has_its_recorded_start_time(self):
        base = os.path.join(self.tmp, "c", "groundtruth-clients")
        os.makedirs(base, mode=0o700)
        launcher = self.spawn([sys.executable, "-B", self.worker, "night.py", "--date", DATE, "--go", "codex"])
        with mock.patch.dict(os.environ, {"GROUNDTRUTH_CLIENT_HOME": base}):
            os.makedirs(os.path.join(night.night_dir(DATE), "launch"), mode=0o700)
            lock = {"launch_id": f"{DATE}-codex-000000000001", "launcher_pid": launcher.pid, "runs": {},
                    "launcher_command": night.process_command(launcher.pid)}
            for recorded, expected in (("Mon Jan  1 00:00:00 2001", []), (None, []),
                                       (night.process_started(launcher.pid), [launcher.pid])):
                with self.subTest(recorded=recorded):
                    write(night.lock_path(DATE, "codex"), json.dumps(dict(lock, launcher_started=recorded)))
                    killed = []
                    night.stop("codex", DATE, kill=lambda pid, sig: killed.append(pid),
                               out=lambda *_: None)
                    self.assertEqual(killed, expected)
        self.assertIsNone(launcher.poll())  # only recorded, never really signalled here

    def test_nothing_without_the_lock_s_launch_id(self):
        # An empty or unreadable lock (or none): no process is searched for by date, client or pattern.
        self.client_home()
        lid = f"{DATE}-codex-0123456789ab"
        w = self.spawn([sys.executable, "-B", self.worker, "--label", "CX1", "--launch-id", lid])
        os.makedirs(os.path.join(night.night_dir(DATE), "launch"), mode=0o700)
        for lock in (None, "", json.dumps({"runs": {"CX1": {"pid": w.pid}}})):
            with self.subTest(lock=lock):
                if lock is not None:
                    write(night.lock_path(DATE, "codex"), lock)
                self.assertEqual(night.stop("codex", DATE, kill=lambda *a: self.fail("signalled"),
                                            out=lambda *_: None), [])
        self.assertIsNone(w.poll())

    def test_no_search_by_program_name_or_date_is_left(self):
        for gone in ("launchers", "parent_table", "launch_mark", "workers", "process_table", "groups_of"):
            self.assertFalse(hasattr(night, gone), gone)


class Point2DevinStatus(unittest.TestCase):
    """2: terminal styling removed before matching; only a positive `Logged in` line, and no mention of an API, a
    token or a key anywhere (status-variants.log)."""

    def test_the_review_s_replies(self):
        devin = C.Devin("m")
        for out, err, ok in (("Logged in (via API token)", "", False), ("Logged in (via \x1b[1mAPI\x1b[0m key)", "", False),
                             ("\x1b[1mLogged in\x1b[0m (via \x1b[2mtoken\x1b[0m)", "", False),
                             ("Logged in (via AP\x1b[0mI k\x1b[0mey)", "", False),
                             ("Logged in as fixture", "You are no longer logged in.", False),
                             ("Logged in as fixture", "You are now signed out.", False),
                             ("Logged in as fixture", "Not logged in", False), ("", "", False),
                             ("Logged in (via WINDSURF_API_KEY)", "", False), ("Logged in with an api_key", "", False),
                             ("\x1b[32mLogged in\x1b[0m", "", True), ("Logged in as fixture", "", True),
                             ("Logged in (via browser)", "", True)):
            with self.subTest(out=out, err=err):
                self.assertEqual(C.login_ok(devin, 0, out, err) is None, ok, C.login_ok(devin, 0, out, err))

    def test_both_entry_points_use_it(self):
        # The owner's login and every run's preflight read the status through login_status -> login_ok.
        devin = C.Devin("m")
        run = lambda argv, **kw: (0, "Logged in (via API token)", "")  # noqa: E731
        with tempfile.TemporaryDirectory() as t, mock.patch.object(C, "CONFINED", False):
            self.assertIn("an API, a token, a key", C.login_status(devin, t, env={"HOME": t, "TMPDIR": t}, run=run))


class Point3NoVersion(R5.CodexNight):
    """3: no client version in any public result: the console log and a private record (600, under <client-home>)
    only; the builder publishes none for an own client. The review's warning-first versions (variants.log:11)."""

    VERSION = "WARNING: workspace at 10.23.45.67 uses schema 2.4\ncodex-cli 0.171.0"

    def test_the_review_s_variants_never_reach_a_public_file(self):
        path, text, events, row = self.run_case("matching-evidence")
        self.assertNotIn("client_version", events[0])
        for word in ("10.23.45.67", "2.4", "0.171.0", "WARNING", "workspace"):
            self.assertNotIn(word, text)
        self.assertIn("detail: client version: WARNING: workspace at 10.23.45.67", self.console)
        base = os.environ["GROUNDTRUTH_CLIENT_HOME"]
        folder = os.path.join(base, probe.PRIVATE_RUNS)
        records = os.listdir(folder)
        self.assertEqual(len(records), 1)
        self.assertEqual(stat.S_IMODE(os.lstat(folder).st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(os.lstat(os.path.join(folder, records[0])).st_mode), 0o600)
        with open(os.path.join(folder, records[0])) as f:
            self.assertIn("10.23.45.67", json.load(f)["client_version"])
        self.assertNotIn("client_version", R5.build_in_night(events))

    def test_the_builder_publishes_no_version_and_the_smoke_check_refuses_one(self):
        with open(os.path.join(R5.SAVED, "CX6-old-context-after-complete.jsonl")) as f:
            rows = [json.loads(x) for x in f]
        for r in rows:
            if r["event"] == "check":
                r["usage"]["model_evidence"] = "own-turn"
                if isinstance(r.get("usage"), dict) and "model" in r["usage"]:  # the ninth review's public form
                    r["usage"]["model_matches"] = r["usage"].pop("model") == MODEL
        rows.insert(-1, {"event": "model-scan", "final": True, "other_models": 0, "unreadable": False})
        rows[0]["client_version"] = "0.171.0"
        self.assertNotIn("client_version", R5.build_in_night(rows))
        self.assertFalse(hasattr(B, "VERSION_TOKEN") or hasattr(C, "VERSION_TOKEN"))


class Point4CodexRunLevel(R5.CodexNight):
    """4: every session file of a Codex run read whole, after each check and at the end: a model other than the
    requested one anywhere excludes the whole run, whatever the per-turn rule said of the measured turn."""

    def test_another_model_anywhere_excludes_the_run(self):
        for variant in ("astra-record-elsewhere", "rewrite-before-offset", "astra-in-the-baseline"):
            with self.subTest(variant=variant):
                path, text, events, row = self.run_case(variant)
                scans = [e for e in events if e["event"] == "model-scan"]
                self.assertTrue(scans[-1]["final"])
                self.assertGreaterEqual(scans[-1]["other_models"], 1)  # a count since the eighth review
                if variant != "astra-in-the-baseline":  # found at the check: the run stops there
                    self.assertEqual(events[-1], dict(events[-1], event="stop", reason="other-model"))
                with self.assertRaisesRegex(SystemExit, "gpt-6-astra|another model|other-model"):
                    R5.build_in_night(events)

    def test_a_clean_run_is_scanned_and_published(self):
        path, text, events, row = self.run_case("matching-evidence")
        scans = [e for e in events if e["event"] == "model-scan"]
        self.assertEqual([s["final"] for s in scans], [False] * 4 + [True])  # control, 2.5m, 5m, 7.5m, the end
        self.assertTrue(all(s["other_models"] == 0 for s in scans))
        self.assertEqual(set(scans[-1]), {"event", "final", "other_models", "unreadable", "at"})
        self.assertEqual(R5.build_in_night(events)["model"], MODEL)

    def test_the_builder_wants_the_end_scan(self):
        path, text, events, row = self.run_case("matching-evidence")
        rows = [e for e in events if not (e["event"] == "model-scan" and e["final"])]
        with self.assertRaisesRegex(SystemExit, "end-of-run scan"):
            R5.build_in_night(rows)

    def test_the_whole_file_reader(self):
        with tempfile.TemporaryDirectory() as t:
            path = os.path.join(t, "rollout.jsonl")
            write(path, json.dumps({"type": "turn_context", "payload": {"model": MODEL}}) + "\n"
                  + json.dumps({"type": "x", "payload": {"deep": [{"to_model": "a"}, {"from_model": "b"}]}}) + "\n"
                  + "not json\n")
            self.assertEqual(C.codex_models(path), ({MODEL, "a", "b"}, True))
            self.assertEqual(C.codex_models(os.path.join(t, "none.jsonl")), (set(), True))


class Point5Gate(unittest.TestCase):
    """5: no own-client run of the new design is built before its night's AUDIT.md, with the fixed first line."""

    def rows(self):
        with open(os.path.join(R5.SAVED, "CX6-old-context-after-complete.jsonl")) as f:
            rows = [json.loads(x) for x in f]
        for r in rows:
            if r["event"] == "check":
                r["usage"]["model_evidence"] = "own-turn"
                if isinstance(r.get("usage"), dict) and "model" in r["usage"]:  # the ninth review's public form
                    r["usage"]["model_matches"] = r["usage"].pop("model") == MODEL
        rows.insert(-1, {"event": "model-scan", "final": True, "other_models": 0, "unreadable": False})
        return rows

    def test_the_gate(self):
        rows = self.rows()
        self.assertEqual(R5.build_in_night(rows)["model"], MODEL)
        with self.assertRaisesRegex(SystemExit, "no AUDIT.md"):
            R5.build_in_night(rows, audit=False)
        with tempfile.TemporaryDirectory() as root:
            for folder, first in ((R5.NIGHT, "# Own-client night audit: pending"),
                                  (R5.NIGHT, "fixture\n" + B.AUDIT_FIRST_LINE), ("results/elsewhere", B.AUDIT_FIRST_LINE)):
                with self.subTest(folder=folder, first=first):
                    write(os.path.join(root, folder, "AUDIT.md"), first + "\n")
                    write(os.path.join(root, folder, "CX6.jsonl"), "".join(json.dumps(r) + "\n" for r in rows))
                    with mock.patch.object(B, "ROOT", root), self.assertRaises(SystemExit):
                        R5.build(folder + "/CX6.jsonl")

    def test_the_tracked_artifact_is_unchanged(self):
        r = subprocess.run([sys.executable, "-B", os.path.join(ROOT, "scripts", "build_observed.py"), "--check"],
                           cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_the_run_document_has_the_audit(self):
        with open(os.path.join(ROOT, "docs", "own-clients-RUN.md")) as f:
            text = f.read()
        morning = text.split("## The morning", 1)[1]
        self.assertLess(morning.index("The audit, before anything is built"), morning.index("The build"))
        self.assertIn("### The audit checklist", morning)
        self.assertIn(f"`{B.AUDIT_FIRST_LINE}`", morning)
        for item in ("The raw results", "Codex's session files, for reroutes", "for anything private"):
            self.assertIn(item, morning)


class Point6Wording(unittest.TestCase):
    def test_the_retry_wording(self):
        with open(os.path.join(ROOT, "docs", "own-clients-RUN.md")) as f:
            text = " ".join(f.read().split())
        self.assertIn("up to one extra session per priming retry", text)


if __name__ == "__main__":
    unittest.main()
