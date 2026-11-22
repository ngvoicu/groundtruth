"""Tuesday (step G5): the audit gate on results/night-*, the mechanical audit (`weekly.py audit`) on a clean night, a
night with a reroute and one with a private string in a public line, and the manifest generated from the night.

    python3 -m unittest discover -s test -p "test_*.py"
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "harness"))
import weekly as W  # noqa: E402

spec = importlib.util.spec_from_file_location("build_observed", os.path.join(ROOT, "scripts", "build_observed.py"))
B = importlib.util.module_from_spec(spec)
spec.loader.exec_module(B)

DATE = "2026-11-30"
NIGHT = f"results/night-{DATE}"
SID = "0198c0de-1234-7abc-8def-0123456789ab"
ISOLATION = {"home": "dedicated", "HOME": "throwaway", "work": "temporary"}


def write(path, text, mode=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)
    if mode:
        os.chmod(path, mode)


def codex_run(model="gpt-x", extra=None):
    lines = [{"event": "start", "harness": "codex", "client": "codex-cli", "model": model, "ages": "2.5m",
              "isolation": ISOLATION, "at": "2026-11-30T22:00:00+00:00"},
             {"event": "check", "age": "control", "warm": True, "late": False,
              "usage": {"calls": 1, "total": 3000, "cached": 2900, "model_matches": True, "model_evidence": "own-turn"},
              "at": "2026-11-30T22:01:00+00:00"},
             {"event": "model-scan", "final": True, "other_models": 0, "unreadable": False,
              "at": "2026-11-30T22:02:00+00:00"},
             {"event": "done", "at": "2026-11-30T22:02:00+00:00"}]
    if extra:
        lines.insert(2, extra)
    return "".join(json.dumps(x) + "\n" for x in lines)


class Gate(unittest.TestCase):
    def test_a_weekly_night_s_folder_is_refused_without_its_audit(self):
        with tempfile.TemporaryDirectory() as root:
            write(os.path.join(root, NIGHT, "cx-gpt-x.jsonl"), codex_run())
            problems = B.audit_gate(root)
            self.assertEqual(len(problems), 1)
            self.assertIn(f"night-{DATE} has no AUDIT.md", problems[0])
            write(os.path.join(root, NIGHT, "AUDIT.md"), B.AUDIT_FIRST_LINE + "\n")  # the first night's line
            self.assertIn("does not begin with '# Night audit: passed'", B.audit_gate(root)[0])
            write(os.path.join(root, NIGHT, "AUDIT.md"), B.NIGHT_AUDIT_FIRST_LINE + "\n")
            self.assertEqual(B.audit_gate(root), [])

    def test_the_first_night_s_folder_keeps_its_own_line(self):
        with tempfile.TemporaryDirectory() as root:
            write(os.path.join(root, "results", "own-clients-2026-11-23", "DV1.jsonl"), "{}\n")
            write(os.path.join(root, "results", "own-clients-2026-11-23", "AUDIT.md"), B.NIGHT_AUDIT_FIRST_LINE + "\n")
            self.assertTrue(B.audit_gate(root))
            write(os.path.join(root, "results", "own-clients-2026-11-23", "AUDIT.md"), B.AUDIT_FIRST_LINE + "\n")
            self.assertEqual(B.audit_gate(root), [])

    def test_a_link_in_a_weekly_night_s_folder_is_refused(self):
        with tempfile.TemporaryDirectory() as root:
            write(os.path.join(root, NIGHT, "AUDIT.md"), B.NIGHT_AUDIT_FIRST_LINE + "\n")
            os.symlink("/etc/hosts", os.path.join(root, NIGHT, "x.jsonl"))
            self.assertTrue(any("symbolic link" in p for p in B.audit_gate(root)))

    def test_the_builder_refuses_a_run_and_an_excluded_entry_of_an_unaudited_night(self):
        self.assertEqual(B.NIGHT_NAME.search(f"night-{DATE}/cx-gpt-x").group(1), f"night-{DATE}")
        self.assertIsNone(B.NIGHT_NAME.search("fortnight-2026-11-30"))
        with tempfile.TemporaryDirectory() as root:
            old = B.ROOT
            B.ROOT = root
            try:
                with self.assertRaises(SystemExit) as e:
                    B.build_excluded({"excluded": [{"id": f"night-{DATE}/cx-1", "reason": "x"}]})
                self.assertIn("has no AUDIT.md", str(e.exception))
                write(os.path.join(root, NIGHT, "AUDIT.md"), B.NIGHT_AUDIT_FIRST_LINE + "\n")
                B.build_excluded({"excluded": [{"id": f"night-{DATE}/cx-1", "reason": "x"}]})
                self.assertEqual(B.night_of("r", f"{NIGHT}/cx-1.jsonl"), f"night-{DATE}")
            finally:
                B.ROOT = old

    def test_the_hook_and_ci_run_the_gate_over_both_kinds(self):
        with open(os.path.join(ROOT, "scripts", "pre-commit")) as f:
            self.assertIn("--audit-gate", f.read())
        with open(os.path.join(ROOT, ".github", "workflows", "ci.yml")) as f:
            self.assertIn("--audit-gate", f.read())


class Audit(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = os.path.join(self.tmp.name, "repo")
        self.home = os.path.join(self.tmp.name, "G")
        os.makedirs(self.root)
        os.makedirs(self.home, mode=0o700)
        self.git_outside = ""

    def tearDown(self):
        self.tmp.cleanup()

    def run_(self, argv, cwd=None, **kw):
        """git status faked (the temporary folder is no checkout); the folder scan is the real one."""
        if argv[0] == "git":
            return subprocess.CompletedProcess(argv, 0, self.git_outside, "")
        if "--git" in argv:
            return subprocess.CompletedProcess(argv, 0, "1 files scanned against 0 credentials: CLEAN\n", "")
        nothing = os.path.join(self.tmp.name, "nothing")
        env = {k: v for k, v in os.environ.items() if k not in ("GROUNDTRUTH_CLIENT_HOME", "CACHE_PROBE_KEY")}
        env.update(SCAN_FINGERPRINTS=nothing, SCAN_CLIENT_KEYS=nothing, SCAN_KEYS_FILE=nothing, SCAN_CONFIG=nothing,
                   SCAN_LOGINS=nothing + "/*.json")
        argv = [argv[0], argv[1], os.path.join(ROOT, "harness", "scan_secrets.py"), *argv[3:]]
        return subprocess.run(argv, cwd=cwd, env=env, **kw)

    def night(self, run_text, session_text, label="cx-gpt-x"):
        write(os.path.join(self.root, NIGHT, label + ".jsonl"), run_text)
        write(os.path.join(self.root, NIGHT, "logs", label + ".log"), f"detail: session 1: {SID}\n", 0o600)
        write(os.path.join(self.home, "codex-cli", "sessions", "2026", "11", "30",
                           f"rollout-2026-11-30T23-00-00-{SID}.jsonl"), session_text)
        lines = []
        items = W.audit(DATE, self.home, self.root, run=self.run_, out=lines.append)
        with open(os.path.join(self.home, f"night-{DATE}", "audit-draft.md")) as f:
            draft = f.read()
        return {name: ok for name, ok, _ in items}, draft, lines

    def test_a_clean_night(self):
        items, draft, lines = self.night(codex_run(), '{"payload": {"model": "gpt-x"}}\n')
        self.assertTrue(all(items.values()), items)
        self.assertIn("passed", lines[0])
        self.assertNotIn("FAILED", draft)
        self.assertEqual(oct(os.stat(os.path.join(self.home, f"night-{DATE}", "audit-draft.md")).st_mode & 0o777),
                         "0o600")

    def test_a_night_with_a_reroute(self):
        session = '{"payload": {"model": "gpt-x"}}\n{"type": "model_reroute", "from_model": "gpt-x", ' \
                  '"to_model": "gpt-secret-y"}\n'
        items, draft, _ = self.night(codex_run(), session)
        self.assertFalse(items["B. no reroute in Codex session files"])
        self.assertFalse(items["B. Codex session files name only the run's model"])
        self.assertTrue(items["A. every public line against its schema"])
        self.assertNotIn("gpt-secret-y", draft)
        self.assertIn("1 reroutes", draft)

    def test_a_private_string_in_a_public_line(self):
        private = "someone.private" + "@" + "example.org"
        bad = {"event": "check-failed", "kind": "other", "note": f"account {private}", "at": "2026-11-30T22:01:30Z"}
        items, draft, _ = self.night(codex_run(extra=bad), '{"payload": {"model": "gpt-x"}}\n')
        self.assertFalse(items["A. every public line against its schema"])
        self.assertFalse(items["D. the scan of the night's folder and its logs"])
        self.assertNotIn(private, draft)
        self.assertNotIn("someone", draft)

    def test_a_check_without_its_model_and_a_file_outside_the_folder(self):
        run = codex_run().replace('"model_matches": true', '"model_matches": false')
        self.git_outside = " M README.md\n"
        items, _, _ = self.night(run, '{"payload": {"model": "gpt-x"}}\n')
        self.assertFalse(items["A. every check names the run's model (model_matches)"])
        self.assertFalse(items["C. git status lists nothing outside the night's folder"])

    def test_a_missing_session_file_fails_item_b(self):
        write(os.path.join(self.root, NIGHT, "cx-gpt-x.jsonl"), codex_run())
        items = {n: ok for n, ok, _ in W.audit(DATE, self.home, self.root, run=self.run_, out=lambda t: None)}
        self.assertFalse(items["B. Codex session files name only the run's model"])


class Manifest(unittest.TestCase):
    def test_generated_from_the_night_never_typed_and_only_after_its_audit(self):
        with tempfile.TemporaryDirectory() as root:
            write(os.path.join(root, "observed", "manifest.json"), json.dumps({"runs": [], "excluded": []}))
            runs = [{"label": "cx-gpt-x", "route": "codex-subscription", "model": "gpt-x", "quantity": "cache",
                     "client": "codex-cli", "file": f"{NIGHT}/cx-gpt-x.jsonl", "outcome": "done"},
                    {"label": "cx-bad", "route": "codex-subscription", "model": "gpt-b", "quantity": "cache",
                     "client": "codex-cli", "file": f"{NIGHT}/cx-bad.jsonl", "outcome": "done"},
                    {"label": "dv-q", "route": "devin", "model": "m-q", "quantity": "cache", "client": "devin-cli",
                     "file": f"{NIGHT}/dv-q.jsonl", "outcome": "quota"},
                    {"label": "or-a-anth", "route": "openrouter", "model": "anthropic/x", "quantity": "cache",
                     "client": "direct", "file": f"{NIGHT}/or-a-anth-2026-11-30T22-00-00.json", "outcome": "done",
                     "options": {"cache_control": {"type": "ephemeral"}, "session_id": True}},
                    {"label": "or-a-w-window", "route": "openrouter", "model": "a/w", "quantity": "window",
                     "client": "direct", "file": f"{NIGHT}/windows.jsonl", "outcome": "refused as expected"}]
            write(os.path.join(root, NIGHT, "runs.json"), json.dumps({"runs": runs}))
            with self.assertRaises(SystemExit):
                W.manifest(DATE, root, out=lambda t: None)
            write(os.path.join(root, NIGHT, "AUDIT.md"), B.NIGHT_AUDIT_FIRST_LINE + "\n2026-12-01, the reviewer\n\n"
                  "## Excluded\n\n- `cx-bad`: a reroute in its session file\n\n## Items\n\n- A: checked\n")
            lines = []
            added, excluded = W.manifest(DATE, root, out=lines.append)
            self.assertEqual([r["id"] for r in added], [f"night-{DATE}/cx-gpt-x", f"night-{DATE}/or-a-anth"])
            self.assertEqual(added[1]["options"], {"cache_control": {"type": "ephemeral"}, "session_id": True})
            self.assertEqual({e["id"]: e["reason"] for e in excluded},
                             {f"night-{DATE}/cx-bad": "a reroute in its session file",
                              f"night-{DATE}/dv-q": "the run ended quota"})
            self.assertIn("1 window requests", lines[0])
            again, _ = W.manifest(DATE, root, out=lambda t: None)  # idempotent
            self.assertEqual(again, [])
            with open(os.path.join(root, "observed", "manifest.json")) as f:
                man = json.load(f)
            self.assertEqual(len(man["runs"]), 2)
            self.assertEqual(len(man["excluded"]), 2)


class KeysScan(unittest.TestCase):
    def test_the_scan_looks_for_the_night_s_keys(self):
        with tempfile.TemporaryDirectory() as t:
            home, folder = os.path.join(t, "G"), os.path.join(t, "results")
            value = "orkey" + "Z" * 30
            write(os.path.join(home, "keys.env"), f"OPENROUTER_API_KEY={value}\n", 0o600)
            write(os.path.join(folder, "x.json"), json.dumps({"leak": value}))
            nothing = os.path.join(t, "nothing")
            env = dict(os.environ, GROUNDTRUTH_CLIENT_HOME=home, SCAN_FINGERPRINTS=nothing)
            r = subprocess.run([sys.executable, "-B", os.path.join(ROOT, "harness", "scan_secrets.py"), "--own-clients",
                                folder], env=env, capture_output=True, text=True)
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn("the night's keys file, OPENROUTER_API_KEY", r.stdout)
            self.assertNotIn(value, r.stdout)


class NightPyDispatch(unittest.TestCase):
    def test_night_py_audit_and_manifest_are_the_weekly_commands(self):
        r = subprocess.run([sys.executable, "-B", "harness/night.py", "--date", DATE, "--dry-run", "audit"], cwd=ROOT,
                           env=dict(os.environ, GROUNDTRUTH_CLIENT_HOME=tempfile.gettempdir()), capture_output=True,
                           text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("would check results/night-2026-11-30/", r.stdout)


if __name__ == "__main__":
    unittest.main()
