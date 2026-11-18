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
    env = {k: v for k, v in os.environ.items() if k != "CACHE_PROBE_KEY" and not k.startswith("GIT_")}
    env.update(extra)
    env.update(SCAN_CLIENT_KEYS=missing, SCAN_KEYS_FILE=missing, SCAN_CONFIG=missing, SCAN_LOGINS=missing + "/*.json")
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

    def test_other_skipped_folders_stay_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            tree = os.path.join(tmp, "tree")
            write(os.path.join(tree, "ok.txt"), "nothing\n")
            write(os.path.join(tree, "node_modules", "m.js"), TOKEN)
            write(os.path.join(tree, "work-1", "m.txt"), TOKEN)
            r = scan(tree, tmp)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("1 files scanned", r.stdout)


if __name__ == "__main__":
    unittest.main()
