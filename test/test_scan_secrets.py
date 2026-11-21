"""harness/scan_secrets.py: a `logs` folder is scanned for the files git tracks (a campaign may force-add its usage
logs), not for local ones; outside a git work tree (the tree the pre-commit hook and CI export) all of it is scanned.

    python3 -m unittest discover -s test -p "test_*.py"
"""
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCAN = os.path.join(HERE, "..", "harness", "scan_secrets.py")
# Built here, so that this file does not hold the shape itself.
TOKEN = "sk-" + "A1b2" * 6


def scan(target, cwd, **extra):
    # No key file of this machine is read: every source points at a path that does not exist.
    missing = os.path.join(cwd, "missing")
    env = {k: v for k, v in os.environ.items() if k not in ("CACHE_PROBE_KEY", "GROUNDTRUTH_CLIENT_HOME", "META_API_KEY")
           and not k.startswith("GIT_")}
    env.update(SCAN_CLIENT_KEYS=missing, SCAN_KEYS_FILE=missing, SCAN_CONFIG=missing, SCAN_LOGINS=missing + "/*.json",
               SCAN_FINGERPRINTS=missing + "/fingerprints.json")
    env.update(extra)
    return subprocess.run([sys.executable, SCAN, target], capture_output=True, text=True, env=env, cwd=cwd)


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)


def git(root, *args):
    subprocess.run(["git", "-C", root, *args], check=True, capture_output=True)


class LogsFolder(unittest.TestCase):
    def test_a_tracked_log_is_scanned_an_untracked_one_is_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = os.path.join(tmp, "repo")
            git(tmp, "init", "-q", root)
            write(os.path.join(root, "results", "run", "a.json"), "{}")
            write(os.path.join(root, "results", "run", "logs", "tracked.usage.jsonl"), '{"k": "%s"}\n' % TOKEN)
            write(os.path.join(root, "results", "run", "logs", "local.log"), "Bearer " + TOKEN[3:] + "\n")
            # staged with -f, as a campaign force-adds its usage logs: in the index, so tracked
            git(root, "add", "-f", "results/run/a.json", "results/run/logs/tracked.usage.jsonl")
            r = scan(os.path.join(root, "results"), tmp)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn(os.path.join("logs", "tracked.usage.jsonl") + ": something shaped like a token", r.stdout)
            self.assertNotIn("local.log", r.stdout)
            self.assertNotIn(TOKEN, r.stdout + r.stderr)  # the value is never printed
            self.assertIn("2 files scanned", r.stdout)

    def test_a_clean_tracked_log_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = os.path.join(tmp, "repo")
            git(tmp, "init", "-q", root)
            write(os.path.join(root, "logs", "tracked.usage.jsonl"), '{"usage": {"input_tokens": 2400}}\n')
            write(os.path.join(root, "logs", "local.log"), "Bearer " + TOKEN[3:] + "\n")
            git(root, "add", "-f", "logs/tracked.usage.jsonl")
            r = scan(root, tmp)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("1 files scanned", r.stdout)

    def test_outside_git_every_log_is_scanned(self):
        # The pre-commit hook and CI scan the tree exported from the index: no .git, every file in it is published.
        with tempfile.TemporaryDirectory() as tmp:
            tree = os.path.join(tmp, "tree")
            write(os.path.join(tree, "results", "run", "logs", "x.usage.jsonl"), '{"k": "%s"}\n' % TOKEN)
            r = scan(tree, tmp)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("x.usage.jsonl: something shaped like a token", r.stdout)

    def test_inside_the_pre_commit_hook_too(self):
        # git runs the hook with GIT_DIR and GIT_INDEX_FILE of the repository being committed to; the exported tree
        # is still outside git, and all of its logs are scanned.
        with tempfile.TemporaryDirectory() as tmp:
            repo = os.path.join(tmp, "repo")
            git(tmp, "init", "-q", repo)
            tree = os.path.join(tmp, "tree")
            write(os.path.join(tree, "results", "run", "logs", "x.usage.jsonl"), '{"k": "%s"}\n' % TOKEN)
            git_dir = os.path.join(repo, ".git")
            r = scan(tree, tmp, GIT_DIR=git_dir, GIT_INDEX_FILE=os.path.join(git_dir, "index"))
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("x.usage.jsonl: something shaped like a token", r.stdout)

    def test_node_modules_stays_skipped_a_work_folder_does_not(self):
        # A work-* folder is ignored by git, but a tree exported from the index publishes whatever is in it (review).
        with tempfile.TemporaryDirectory() as tmp:
            tree = os.path.join(tmp, "tree")
            write(os.path.join(tree, "ok.txt"), "nothing\n")
            write(os.path.join(tree, "node_modules", "m.js"), TOKEN)
            r = scan(tree, tmp)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("1 files scanned", r.stdout)
            write(os.path.join(tree, "work-1", "m.txt"), TOKEN)
            r = scan(tree, tmp)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)


class OwnClients(unittest.TestCase):
    """An own client's state folder and session files are never committed; its key variables are searched for."""

    # Built here, so that this file does not hold the shapes itself (the scan reads it too).
    SESSIONS = {
        # a Claude Code session record, as under <state folder>/projects/<folder>/<uuid>.jsonl
        "claude.jsonl": '{"parent' + 'Uuid": null, "session' + 'Id": "00000000-0000-4000-8000-000000000001", "type": "user"}\n',
        # a Codex CLI session file, as under <state folder>/sessions/2026/11/22/
        "rollout-2026-11-22T10-00-00-0000.jsonl": '{"type": "session_' + 'meta", "payload": {}}\n',
        # a Devin CLI export
        "devin-export.json": '{"schema_version": "' + 'ATIF-v1.2", "session_id": "surf-sleep", "steps": []}\n',
        # Muse Code's login file
        "auth.json": '{"provider": "meta"}\n',
    }

    def test_a_session_file_of_each_client_is_refused(self):
        for name, text in self.SESSIONS.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                tree = os.path.join(tmp, "tree")
                write(os.path.join(tree, "results", "run", name), text)
                r = scan(tree, tmp)
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                self.assertIn(name + ":", r.stdout)

    def test_a_state_folder_is_refused_whatever_it_holds(self):
        for folder in ("claude-code", "codex-cli", "devin-cli", "muse-code"):
            with self.subTest(folder=folder), tempfile.TemporaryDirectory() as tmp:
                tree = os.path.join(tmp, "tree")
                write(os.path.join(tree, "results", "run", folder, "settings.txt"), "nothing\n")
                r = scan(tree, tmp)
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                self.assertIn("state folder", r.stdout)

    def test_a_run_file_naming_a_client_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            tree = os.path.join(tmp, "tree")
            write(os.path.join(tree, "results", "run", "CC1.jsonl"),
                  '{"event": "start", "client": "claude-code", "isolation": {"home": "dedicated", "work": "temporary"}}\n')
            r = scan(tree, tmp)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_the_key_variables_are_searched_for(self):
        for var in ("META_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN"):
            value = "kv" + "9x" * 12  # not shaped like a token: only the variable can find it
            with self.subTest(var=var), tempfile.TemporaryDirectory() as tmp:
                tree = os.path.join(tmp, "tree")
                write(os.path.join(tree, "results", "run", "log.txt"), "key " + value + "\n")
                r = scan(tree, tmp, **{var: value})
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                self.assertIn("environment variable " + var, r.stdout)
                self.assertNotIn(value, r.stdout + r.stderr)


sys.path.insert(0, os.path.join(HERE, "..", "harness"))
import scan_secrets as S  # noqa: E402


class Review(unittest.TestCase):
    """Review finding 3: what cleared the scan (all values synthetic)."""

    CANARY = "reviewonly_opaque_" + "A23" * 8

    def test_a_child_only_value_is_found_by_its_fingerprint(self):
        with tempfile.TemporaryDirectory() as tmp:
            fp = os.path.join(tmp, "fp.json")
            S.remember(self.CANARY, "META_API_KEY", path=fp)
            with open(fp) as f:
                self.assertNotIn(self.CANARY, f.read())  # the value itself is never written
            tree = os.path.join(tmp, "tree")
            write(os.path.join(tree, "results", "night", "client-limits.jsonl"), '{"message": "credential=%s"}\n' % self.CANARY)
            r = scan(tree, tmp, SCAN_FINGERPRINTS=fp)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("the value of META_API_KEY", r.stdout)
            self.assertNotIn(self.CANARY, r.stdout + r.stderr)

    def test_a_state_folders_path_is_found(self):
        state = "/Volumes/measure/" + "campaign"
        with tempfile.TemporaryDirectory() as tmp:
            tree = os.path.join(tmp, "tree")
            write(os.path.join(tree, "a.jsonl"), '{"error": "state=%s/muse-code"}\n' % state)
            r = scan(tree, tmp)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("state folder's path", r.stdout)
            write(os.path.join(tree, "a.jsonl"), '{"error": "state=%s"}\n' % state)
            r = scan(tree, tmp, GROUNDTRUTH_CLIENT_HOME=state)
            self.assertIn("state folder's path", r.stdout)

    def test_session_databases_names_with_an_e_mail_and_auth_json_in_a_work_folder(self):
        cases = {"results/night/sessions.db": "SQLite format 3\x00 data",
                 "results/night/" + "someone" + "@" + "example.com" + ".txt": "nothing",
                 "notes/work-review/" + "codex-cli/auth.json": '{"x": 1}'}
        for rel, text in cases.items():
            with self.subTest(rel=rel), tempfile.TemporaryDirectory() as tmp:
                tree = os.path.join(tmp, "tree")
                write(os.path.join(tree, rel), text)
                r = scan(tree, tmp)
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)

    def test_git_mode_scans_staged_changed_and_untracked_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = os.path.join(tmp, "repo")
            git(tmp, "init", "-q", root)
            write(os.path.join(root, "ok.txt"), "fine\n")
            write(os.path.join(root, "notes", "untracked.txt"), "Bearer " + TOKEN[3:] + "\n")
            git(root, "add", "ok.txt")
            r = subprocess.run([sys.executable, SCAN, "--git", root], capture_output=True, text=True, cwd=tmp,
                               env={**os.environ, "SCAN_CLIENT_KEYS": tmp + "/m", "SCAN_KEYS_FILE": tmp + "/m",
                                    "SCAN_CONFIG": tmp + "/m", "SCAN_LOGINS": tmp + "/m/*.json",
                                    "SCAN_FINGERPRINTS": tmp + "/m/f.json"})
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("untracked.txt", r.stdout)
            self.assertIn("2 files scanned", r.stdout)

    def test_the_ignore_rules_cover_them(self):
        repo = os.path.join(HERE, "..")
        for rel in ("results/night/" + "codex-cli/auth.json", "notes/work-review/" + "codex-cli/auth.json", "results/night/sessions.db",
                    "results/x/" + "pi-provimux/settings.json", "anything/auth.json"):
            r = subprocess.run(["git", "-C", repo, "check-ignore", "-q", "--no-index", "--", rel], capture_output=True)
            self.assertEqual(r.returncode, 0, rel)


if __name__ == "__main__":
    unittest.main()
