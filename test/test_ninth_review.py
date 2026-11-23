"""The last check of 60e65ba (the ninth review), its three open cases, each replayed from the review's receipts with
its near variants, each failing at 60e65ba. Nothing is sent and no real client is run: stand-in clients and session
files, scratch Git repositories with a linked worktree, fixture home folders.

    python3 -m unittest discover -s test -p "test_*.py"
"""
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
# No client is run to list its models (harness/model_ids.py): the checked list, also in the children.
os.environ.setdefault("GROUNDTRUTH_MODEL_LIST", "checked")
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
# The real hook check, before Owner replaces it for the fixture repositories (which are no Git checkouts).
REAL_HOOK_PROBLEM = night.hook_problem
GIT_ENV = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
NOTHING = os.path.join(tempfile.gettempdir(), "gt-ninth-nothing")
GIT_ENV.update(SCAN_CLIENT_KEYS=NOTHING, SCAN_KEYS_FILE=NOTHING, SCAN_CONFIG=NOTHING, SCAN_LOGINS=NOTHING + "/*.json",
               SCAN_FINGERPRINTS=NOTHING, PYTHONDONTWRITEBYTECODE="1")


def git(cwd, *args, check=True):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t" + "@" + "example.invalid", *args],
                          cwd=cwd, env=GIT_ENV, capture_output=True, text=True, check=check)


class Point1HookGitRuns(unittest.TestCase):
    """1: the hook check reads the hook Git will really run (hook-spelling.log: `core.hooksPath` = `scripts ` passed
    the check while Git ran a missing hook and committed a raw file alone)."""

    @classmethod
    def setUpClass(cls):
        # The review's topology: a main checkout whose older hook passes anything, linked under .git/hooks, and a
        # linked worktree holding this tree's code (hook, gate, launcher).
        cls.tmp = tempfile.mkdtemp(prefix="gt-ninth-hook-")
        cls.main, cls.wt = os.path.join(cls.tmp, "main"), os.path.join(cls.tmp, "wt")
        subprocess.run(["git", "clone", "-q", ROOT, cls.main], check=True, env=GIT_ENV)
        for rel in ("scripts/pre-commit", "scripts/build_observed.py", "harness/scan_secrets.py", "harness/night.py",
                    "harness/probe.py", "harness/clients.py"):
            shutil.copy2(os.path.join(ROOT, rel), os.path.join(cls.main, rel))
        git(cls.main, "add", "-A")
        git(cls.main, "commit", "-q", "--no-verify", "--allow-empty", "-m", "candidate")
        git(cls.main, "branch", "candidate")
        write(os.path.join(cls.main, "scripts", "pre-commit"), "#!/bin/bash\nexit 0  # the older hook\n", 0o755)
        git(cls.main, "commit", "-q", "--no-verify", "-am", "older main")
        os.symlink("../../scripts/pre-commit", os.path.join(cls.main, ".git", "hooks", "pre-commit"))
        git(cls.main, "worktree", "add", "-q", cls.wt, "candidate")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, True)

    def setUp(self):
        git(self.wt, "config", "--unset-all", "core.hooksPath", check=False)
        hook = os.path.join(self.wt, "scripts", "pre-commit")
        if os.path.isdir(hook):
            os.rmdir(hook)
        git(self.wt, "checkout", "--", "scripts/pre-commit")
        os.chmod(hook, 0o755)

    def problem(self):
        return REAL_HOOK_PROBLEM(self.wt)

    def go(self, what):
        """`night.py --go <what>` in the worktree, with an empty campaign folder: (exit, output, files made)."""
        with tempfile.TemporaryDirectory() as campaign:
            os.chmod(campaign, 0o700)
            r = subprocess.run([sys.executable, "-B", "harness/night.py", "--date", "2026-11-23", "--go", what],
                               cwd=self.wt, env=dict(GIT_ENV, GROUNDTRUTH_CLIENT_HOME=campaign), capture_output=True,
                               text=True, timeout=60)
            return r.returncode, r.stdout + r.stderr, os.listdir(campaign)

    def test_the_review_s_trailing_blank(self):
        git(self.wt, "config", "core.hooksPath", "scripts ")
        selected = git(self.wt, "rev-parse", "--path-format=absolute", "--git-path", "hooks/pre-commit").stdout
        self.assertTrue(selected.endswith("scripts /pre-commit\n"), selected)  # Git's own reading: a missing hook
        why = self.problem()
        self.assertIsNotNone(why)
        for what in ("smoke", "all"):
            code, out, made = self.go(what)
            self.assertEqual(code, 1, out)
            self.assertIn("commit hook", out)
            self.assertEqual(made, [])
        # The refusal names the exact command that fixes it; run as given, the check passes and the hook refuses a
        # raw file staged alone.
        command = re.search(r"`(git -C [^`]+ config core\.hooksPath scripts)`", why).group(1)
        subprocess.run(command, shell=True, check=True, env=GIT_ENV)
        self.assertIsNone(self.problem())
        raw = os.path.join("results", "own-clients-2026-11-23", "CX6.jsonl")
        write(os.path.join(self.wt, raw), '{"event": "done"}\n')
        git(self.wt, "add", "--", raw)
        r = git(self.wt, "commit", "-q", "-m", "raw only", check=False)
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("audit gate: refused", r.stderr)
        git(self.wt, "reset", "-q", "--", raw)
        os.remove(os.path.join(self.wt, raw))

    def test_near_spellings_of_the_setting(self):
        for value in ("scripts ", " scripts", "scripts/", "./scripts", "Scripts", "scripts\t", ".git/hooks",
                      os.path.join(self.main, "scripts")):
            with self.subTest(value=value):
                git(self.wt, "config", "core.hooksPath", value)
                self.assertIsNotNone(self.problem())

    def test_unset_is_still_refused(self):
        why = self.problem()
        self.assertIn("not set", why)
        self.assertIn(f"git -C {self.wt} config core.hooksPath scripts", why)

    def test_the_selected_hook_must_be_this_checkout_s_executable_file(self):
        git(self.wt, "config", "core.hooksPath", "scripts")
        self.assertIsNone(self.problem())
        hook = os.path.join(self.wt, "scripts", "pre-commit")
        os.chmod(hook, 0o644)
        self.assertIn("not executable", self.problem())
        os.chmod(hook, 0o755)
        os.remove(hook)
        self.assertIn("does not exist", self.problem())
        os.mkdir(hook)
        self.assertIn("does not exist", self.problem())


# --- 2. the public record ------------------------------------------------------------------------------------------

def allowed_strings(ages):
    return (set(getattr(probe, "EVENTS", ())) | set(getattr(probe, "REASONS", ())) | set(C.ERROR_KINDS)
            | {"own-turn", "baseline", "control", *ages})


TIME = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\+00:00")


class Point2PublicRecord(R5.CodexNight):
    """2: every public line is written by one allowlist (probe.Public): listed keys; numbers and booleans; strings of
    a fixed set or of the run's own plan. The client- or vendor-reported model is `model_matches`
    (model-fixtures/current-turn-same-label/.../CX6.jsonl:9 had copied it into check-invalid.usage.model)."""

    KEY = "sk-" + "t345syntheticCanary1234567890"
    VALUES = (KEY, KEY.lower(), "internal-project-label", "19.28.3746", "nested/model/diagnostic",
              "/Volumes/FixtureData/test-campaign/" + "codex" + "-cli", "MixedCase-FixTure-Label")

    def assert_public(self, text, values):
        lines = [json.loads(x) for x in text.splitlines()]
        start = lines[0]
        self.assertEqual(start["event"], "start")
        ages = start["ages"].split(",")
        ok = allowed_strings(ages)
        keys = set(getattr(probe, "FIELDS", {})) | set(getattr(probe, "USAGE", {})) | {"at"}

        def walk(v, key, where):
            if isinstance(v, dict):
                for k, x in v.items():
                    self.assertIn(k, keys, where)
                    walk(x, k, where)
            elif isinstance(v, str):
                if key == "at":
                    self.assertRegex(v, TIME)
                else:
                    self.assertIn(v, ok, f"{where}: {key}")
            else:
                self.assertIn(type(v), (int, float, bool), f"{where}: {key}")
        for n, ev in enumerate(lines[1:], 2):
            walk(ev, None, f"line {n}")
        low = text.lower()
        for v in values:
            self.assertNotIn(v.lower(), low)

    def replay(self, placement, values):
        """The review's model-replay.py: the fixture value in the baseline's diagnostic records (`baseline`), or as
        the measured turn's own `turn_context.model` (`own-turn`, in place of the other model), or none (`clean`)."""
        self.PRIVATE = values
        variant = {"baseline": "private-strings", "own-turn": "other-model", "clean": "matching-evidence"}[placement]
        # Each replay its own results file and session files, as the review's were.
        shutil.rmtree(os.path.join(self.repo, "results", variant), True)
        shutil.rmtree(os.path.join(os.environ.get("GROUNDTRUTH_CLIENT_HOME", "/nonexistent"), "codex-cli", "sessions"),
                      True)
        real = json.dumps

        def records(obj, *a, **kw):
            if placement == "own-turn" and isinstance(obj, dict) and obj.get("type") == "turn_context" \
                    and obj["payload"].get("model") == "gpt-6-astra":
                obj = {**obj, "payload": {**obj["payload"], "model": values[0]}}
            return real(obj, *a, **kw)
        with mock.patch.object(json, "dumps", side_effect=records):
            return self.run_case(variant)

    def test_every_variant_of_the_review(self):
        cases = [("previous-baseline", "baseline", self.VALUES[:5]),
                 ("case-and-duplicate", "baseline", self.VALUES + (self.VALUES[2],))]
        cases += [(f"current-turn-{v}", "own-turn", (v,)) for v in self.VALUES]
        for name, placement, values in cases:
            with self.subTest(case=name):
                path, text, events, row = self.replay(placement, values)
                self.assert_public(text, values)
                if placement == "own-turn":
                    # other-model; or no-model, for a value the redaction already takes for a key
                    self.assertEqual(row["event"], "check-invalid")
                    self.assertIn(row["reason"], ("other-model", "no-model"))
                    self.assertIsNot(row["usage"].get("model_matches"), True)
                    if row["reason"] == "other-model":
                        self.assertIs(row["usage"]["model_matches"], False)
                        self.assertIn(values[0], self.console)  # kept, privately, for the audit
                with self.assertRaises(SystemExit):
                    R5.build_in_night(events)

    def test_a_clean_run_is_published_from_model_matches(self):
        path, text, events, row = self.replay("clean", ())
        self.assert_public(text, ())
        self.assertEqual((row["event"], row["usage"]["model_matches"]), ("check", True))
        self.assertEqual(R5.build_in_night(events)["model"], MODEL)

    def test_the_writer_itself(self):
        with tempfile.TemporaryDirectory() as t:
            path, kept = os.path.join(t, "X.jsonl"), []
            plan = {"event": "start", "harness": "codex", "model": MODEL, "ages": "2.5m,5m"}
            w = probe.Public(path, plan, private=kept.append, now=lambda: "2026-11-23T01:00:00+00:00")
            plan["model"] = "changed after the writer was made"
            w.line({"event": "start", "client_version": "codex-cli 9", "model": "x"})
            hostile = {"event": "check-invalid", "age": "2.5m", "ageSec": "150", "late": 1, "warm": True,
                       "reason": "other-model", "error_kind": "sk-abc", "handle": "thread-uuid", "session": 3,
                       "note": "free text", "usage": {"total": 1, "calls": True, "model": "internal-project-label",
                                                      "model_issue": "other-model", "model_evidence": "/x",
                                                      "raw": {"total": 2, "cached": "3", "extra": 4}},
                       "prime": {"model": MODEL.upper(), "total": 5}}
            w.line(hostile)
            w.line({"event": "whatever", "reason": "quota"})
            w.line({"event": "check", "age": "3h", "usage": {"model": MODEL}})
            with open(path) as f:
                lines = [json.loads(x) for x in f]
        self.assertEqual(lines[0], {"event": "start", "harness": "codex", "model": MODEL, "ages": "2.5m,5m",
                                    "at": "2026-11-23T01:00:00+00:00"})
        self.assertEqual(lines[1], {"event": "check-invalid", "age": "2.5m", "warm": True, "reason": "other-model",
                                    "session": 3, "usage": {"total": 1, "model_matches": False,
                                                            "model_issue": "other-model", "raw": {"total": 2}},
                                    "prime": {"model_matches": False, "total": 5}, "at": "2026-11-23T01:00:00+00:00"})
        self.assertEqual(lines[2], {"event": "check", "usage": {"model_matches": True},
                                    "at": "2026-11-23T01:00:00+00:00"})  # an unknown event: not written; `3h`: no age
        self.assertEqual(len(lines), 3)
        dropped = "\n".join(kept)
        for v in ("thread-uuid", "free text", "internal-project-label", "sk-abc", "'150'", "whatever"):
            self.assertIn(v, dropped)

    def test_a_devin_model_matches_with_its_own_suffixes(self):
        with tempfile.TemporaryDirectory() as t:
            w = probe.Public(os.path.join(t, "D.jsonl"), {"harness": "devin", "model": "glm-5-3-low", "ages": "2.5m"})
            for reported, matches in (("glm-5-3-low", True), ("GLM-5-3-LOW", True), ("glm-5-3-low-20261001", True),
                                      ("glm-5-3", False), ("glm-5-4-low", False), ("internal-project-label", False)):
                with self.subTest(reported=reported):
                    self.assertEqual(w.clean({"usage": {"model": reported}}, probe.FIELDS, "x"),
                                     {"usage": {"model_matches": matches}})

    def test_the_builder_wants_model_matches(self):
        path, text, events, row = self.replay("clean", ())
        last = max(i for i, r in enumerate(events) if r["event"] == "check")
        for change, message in (({"model_matches": False}, "model_matches"), ({"model_matches": None}, "model_matches"),
                                ({"model": MODEL}, "client-reported model text")):
            with self.subTest(change=change):
                rows = [dict(r, usage=dict(r["usage"], **change)) if i == last else r for i, r in enumerate(events)]
                with self.assertRaisesRegex(SystemExit, message):
                    R5.build_in_night(rows)

    def test_one_writer(self):
        # The probe opens its public file in one place: Public.line.
        with open(os.path.join(ROOT, "harness", "probe.py")) as f:
            source = f.read()
        self.assertEqual(source.count('open(self.path, "a")'), 1)
        self.assertNotIn('open(path, "a")', source)
        self.assertFalse(hasattr(C, "handle_text"))

    def test_the_audit_checklist_reads_the_new_fields(self):
        with open(os.path.join(ROOT, "docs", "own-clients-RUN.md")) as f:
            run = f.read()
        self.assertIn('"model_matches": true', run)
        self.assertNotIn("usage.model`", run)
        self.assertIn("detail: session", run)


# --- 3. the everyday folders ---------------------------------------------------------------------------------------

class Point3RealFolders(Owner):
    """3: the everyday-folder guard compares real folders, not spellings (stop-folders.log:11: on a case-insensitive
    disk `.CODEX` and `.DEVIN` named the everyday folders and `stop all` wrote its marks there)."""

    def setUp(self):
        super().setUp()
        for rel in (".codex", ".devin", ".claude", ".pi", ".config/devin", "Library/Keychains", "dedicated"):
            os.makedirs(os.path.join(self.user, rel), mode=0o700)
            write(os.path.join(self.user, rel, "fixture"), "x\n")
        os.chmod(os.path.join(self.user, "dedicated"), 0o700)
        os.remove(os.path.join(self.user, "dedicated", "fixture"))
        self.insensitive = os.path.exists(os.path.join(self.user, ".CODEX"))

    def inventory(self):
        return sorted(os.path.relpath(os.path.join(d, n), self.user)
                      for d, ds, fs in os.walk(self.user) for n in ds + fs if "dedicated" not in d + n)

    def stop_with(self, setting):
        before = self.inventory()
        with mock.patch.dict(os.environ, {"GROUNDTRUTH_CLIENT_HOME": setting, "HOME": self.user}):
            with self.assertRaisesRegex(SystemExit, "everyday folder"):
                night.stop("all", DATE, kill=lambda *a: self.fail("signalled"), out=lambda *_: None)
        self.assertEqual(self.inventory(), before)

    def test_the_review_s_cases_and_their_spellings(self):
        if not self.insensitive:
            self.skipTest("a case-sensitive disk: `.CODEX` is another folder here")
        os.symlink(os.path.join(self.user, ".CODEX"), os.path.join(self.user, "campaign-link"))
        for rel in (".codex", ".codex/new-child", ".devin", ".config/devin", "Library/Keychains", "campaign-link",
                    ".CODEX", ".DEVIN", ".Codex/new-child", ".CLAUDE", ".PI", ".CONFIG/Devin", "LIBRARY/keychains",
                    ".MUSE", ".Local/Share/x", "dedicated/../.CODEX"):
            with self.subTest(setting=rel):
                self.stop_with(os.path.join(self.user, rel))

    def test_links_below_the_campaign_spelled_otherwise(self):
        base = os.path.join(self.user, "dedicated")
        for link, target in ((f"night-{DATE}", ".CODEX"), (f"night-{DATE}/launch", ".DEVIN")):
            with self.subTest(link=link):
                if link.endswith("launch"):
                    os.mkdir(os.path.join(base, f"night-{DATE}"), 0o700)
                os.symlink(os.path.join(self.user, target), os.path.join(base, link))
                self.stop_with(base)
                os.remove(os.path.join(base, link))

    def test_the_dedicated_folder_gets_its_marks(self):
        base = os.path.join(self.user, "dedicated")
        with mock.patch.dict(os.environ, {"GROUNDTRUTH_CLIENT_HOME": base, "HOME": self.user}):
            night.stop("all", DATE, out=lambda *_: None)
            self.assertTrue(all(os.path.isfile(night.stop_path(DATE, n)) for n in night.CLIENT_PARTS))

    def test_every_place_the_night_writes(self):
        if not self.insensitive:
            self.skipTest("a case-sensitive disk")
        os.mkdir(os.path.join(self.user, ".codex", "codex-cli"), 0o700)  # a fixture state folder spelled `.CODEX`
        before = self.inventory()
        upper = os.path.join(self.user, ".CODEX")
        with mock.patch.dict(os.environ, {"GROUNDTRUTH_CLIENT_HOME": upper, "HOME": self.user}):
            for what, call in (
                    ("night folder", lambda: night.make_night_dir(DATE)),
                    ("snapshot", lambda: night.untouched(DATE, "save", user_home=self.user, out=lambda *_: None)),
                    ("state folder", lambda: C.state_folder(C.Codex("m"), upper, self.repo, user_home=self.user)),
                    ("throwaway home", lambda: C.prepare_home("x", os.path.join(upper, "codex-cli"), upper, self.repo,
                                                              os.path.realpath(self.user))),
                    ("raw output", lambda: probe.private_capture_folder(os.path.join(upper, "raw"), upper, self.repo,
                                                                        self.user))):
                with self.subTest(what=what), self.assertRaisesRegex(SystemExit, "everyday folder"):
                    call()
        self.assertEqual(self.inventory(), before)

    def test_the_working_folder_is_checked_before_it_is_made(self):
        if not self.insensitive:
            self.skipTest("a case-sensitive disk")
        base = os.path.join(self.user, "dedicated")
        write(os.path.join(base, "codex-cli", "auth.json"), "{}", 0o600)
        os.chmod(os.path.join(base, "codex-cli"), 0o700)
        before = self.inventory()
        with mock.patch.dict(os.environ, {"GROUNDTRUTH_CLIENT_HOME": base, "HOME": self.user}), \
                mock.patch.object(tempfile, "tempdir", os.path.join(self.user, ".CODEX")), \
                mock.patch.object(C, "_run", side_effect=lambda *a, **k: (0, "Logged in using ChatGPT", "")), \
                redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()), \
                self.assertRaisesRegex(SystemExit, "working folder"):
            probe.main(["--harness", "codex", "--model", MODEL, "--label", "CX1", "--ages", "2.5m", "--words", "20",
                        "--replicas", "1", "--out", os.path.join(self.repo, "results", "x")])
        self.assertEqual(self.inventory(), before)

    def test_identity_not_spelling(self):
        home = os.path.realpath(self.user)
        self.assertEqual(C.everyday_folder(os.path.join(home, ".codex", "a", "b"), home), "~/.codex")
        self.assertEqual(C.everyday_folder(home, home), "~")
        self.assertIsNone(C.everyday_folder(os.path.join(home, "dedicated", "night"), home))
        os.symlink(os.path.join(home, ".devin"), os.path.join(home, "dedicated", "elsewhere"))
        self.assertEqual(C.everyday_folder(os.path.join(home, "dedicated", "elsewhere", "x"), home), "~/.devin")


if __name__ == "__main__":
    unittest.main()
