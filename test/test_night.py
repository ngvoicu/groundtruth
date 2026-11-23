"""harness/night.py: the run plan of the first night (the own clients' cache runs only), its dry run, the everyday
state's snapshot and report. Nothing is run or sent. The launcher, status, stop and the smoke review are tested in
test_second_review.py with the review's findings.

    python3 -m unittest discover -s test -p "test_*.py"
"""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "harness"))
import night  # noqa: E402
import probe  # noqa: E402


def ids(prefix, n, start=1):
    return [f"{prefix}{i}" for i in range(start, n + 1)]


class Plan(unittest.TestCase):
    def test_every_run_of_the_first_night_is_in_the_plan_and_nothing_else(self):
        want = (["S2", "S3", "S3b"] + ids("CX", 6) + ids("DV", 18) + ["DV9d"])
        self.assertEqual(sorted(night.ALL_STEPS), sorted(want))

    def test_no_pi_no_provimux_no_openrouter_no_window_no_supervisor(self):
        # The chief's decision of 2026-11-22: the first night is the own clients' cache runs only.
        for step in night.ALL_STEPS.values():
            argv = " ".join(night.command(step, "2026-11-23"))
            for gone in ("client_limits", "agy", "--harness pi", "provimux", "src/cli.ts", "openrouter", "8317"):
                self.assertNotIn(gone, argv)
        for gone in ("CL1", "DL1", "ML1", "S5", "AG1", "SP", "OR1", "OW1", "CXS-a", "P-CC3", "P-DV5", "S1", "S4", "CC1",
                     "CC5", "MC1"):
            self.assertNotIn(gone, night.ALL_STEPS)
        for gone in ("openrouter", "windows", "codex-plain", "devin-terra-pi", "claude-5m", "claude", "muse"):
            self.assertNotIn(gone, night.PARTS)
        for gone in ("supervise", "launch_night", "pi_setup", "window", "budget", "estimate", "openrouter_post",
                     "PROVIMUX_CONFIG", "MONEY_STOP"):
            self.assertFalse(hasattr(night, gone), gone)
        import clients
        for gone in ("Pi", "payload_section", "payload_record", "PROVIMUX_CONFIG"):
            self.assertFalse(hasattr(clients, gone), gone)
        self.assertNotIn("pi", probe.HARNESSES)

    def test_dv9d_is_devin_with_its_own_process_model(self):
        self.assertIn("--devin-daemon", night.ALL_STEPS["DV9d"]["args"])  # pair DV-5: both runs are Devin's
        self.assertEqual(night.ALL_STEPS["DV9"]["args"][night.ALL_STEPS["DV9"]["args"].index("--schedule") + 1], "std")

    def test_claude_and_muse_are_refused_by_every_night_command(self):
        # The owner's decision of 2026-11-22: the first night is Codex CLI and Devin CLI only.
        for argv in (["--go", "claude"], ["--go", "muse"], ["--dry-run", "claude"], ["login", "claude"],
                     ["login", "muse"], ["stop", "claude"], ["--go", "CC1"], ["--go", "S1"]):
            with self.subTest(argv=argv), self.assertRaises(SystemExit) as e:
                night.main(["--date", "2099-01-01", *argv])
            self.assertTrue(any(w in str(e.exception) for w in ("not in the first night", "not a part",
                                                                 "one of codex, devin")), str(e.exception))
        for gone in ("KEYCHAIN", "keychain", "key_reader", "step_env", "claude_overage", "overage_args"):
            self.assertFalse(hasattr(night, gone), gone)
        for gone in ("overage_in", "OVERAGE_STOPS"):
            self.assertFalse(hasattr(probe, gone), gone)
        self.assertNotIn("--allow-overage", probe.parser().format_help())
        self.assertEqual(night.CLIENT_PARTS, ("codex", "devin"))
        self.assertEqual(sorted(night.LOGINS), ["codex", "devin"])

    def test_the_starts_of_a_client_are_staggered(self):
        self.assertEqual([night.delay_of(s, i) for i, s in enumerate(night.PARTS["devin"])][:3], [0, 20, 40])
        self.assertEqual([night.delay_of(s, i) for i, s in enumerate(night.PARTS["codex"])][:3], [0, 15, 30])

    def test_the_smoke_runs_keep_their_raw_output(self):
        for sid in ("S2", "S3", "S3b"):
            self.assertIn("--keep-raw", night.command(night.ALL_STEPS[sid], "2026-11-23"))

    def test_dv11_and_dv17_record_the_effort_they_ask(self):
        for i, effort in (("DV11", "none"), ("DV17", "medium"), ("DV1", "low")):
            args = night.command(night.ALL_STEPS[i], "2099-01-01")[2:]
            a = probe.parser().parse_args(args)
            self.assertEqual(probe.HARNESSES[a.harness](a.model, a.effort).effective_effort(), effort)

    def test_results_folders(self):
        self.assertIn("results/own-clients-2026-11-23", night.command(night.ALL_STEPS["CX1"], "2026-11-23"))
        self.assertIn("results/own-clients-2026-11-23/smoke", night.command(night.ALL_STEPS["S2"], "2026-11-23"))

    def test_the_dry_run_sends_nothing(self):
        lines = []
        night.dry_run(night.select(["S2", "CX1", "DV9d"]), "2099-01-01", out=lines.append)
        text = "\n".join(lines)
        self.assertIn("at most 5 requests (3 with a warm first control)", text)  # S2: the control's second chance
        self.assertIn('model_provider=\\"openai\\"', text)
        self.assertIn("nothing sent", text)
        self.assertFalse(os.path.exists(os.path.join(night.ROOT, "results", "own-clients-2099-01-01")))


class Everyday(unittest.TestCase):
    """Review finding 1, by isolation: the everyday folders (to their depth, ~/.pi included) and the Keychain's item
    names are snapshot before the logins and reported in the morning, for a person to judge; never a stop."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.user = os.path.join(self.tmp.name, "person")
        os.makedirs(os.path.join(self.user, ".codex", "sessions"))
        os.makedirs(os.path.join(self.user, ".pi", "agent"))
        with open(os.path.join(self.user, ".codex", "sessions", "thread.jsonl"), "w") as f:
            f.write("one\n")
        self.keychain = ['keychain: "/k"', 'class: "genp"', '    "svce"<blob>="Claude Code-credentials"',
                         '    "acct"<blob>="someone"', '    "mdat"<timedate>=0x3230323630313031  "20260101000000Z\\000"']
        self.base = os.path.join(self.tmp.name, "client-home")
        mask = os.umask(0o077)  # the night's folders are private (mode 700)
        self.addCleanup(os.umask, mask)
        for name in ("claude-code", "codex-cli", "devin-cli", "muse-code"):
            os.makedirs(os.path.join(self.base, name))
        p = mock.patch.dict(os.environ, {"GROUNDTRUTH_CLIENT_HOME": self.base})
        p.start()
        self.addCleanup(p.stop)

    def lister(self):
        return lambda: "\n".join(self.keychain)

    def save(self, date="2099-03-01"):
        return night.untouched(date, "save", user_home=self.user, lister=self.lister(), out=lambda *_: None)

    def report(self, lines=None, at="t1"):
        return night.untouched("2099-03-01", "report", user_home=self.user, lister=self.lister(),
                               out=(lines.append if lines is not None else lambda *_: None), at=at)

    def test_a_nested_edit_and_a_file_under_pi_are_reported(self):
        self.save()
        self.assertEqual(self.report(), [])
        with open(os.path.join(self.user, ".codex", "sessions", "thread.jsonl"), "w") as f:
            f.write("a new conversation, longer\n")
        with open(os.path.join(self.user, ".pi", "agent", "session.jsonl"), "w") as f:
            f.write('{"type": "cache_warm"}\n')
        lines = []
        changed = self.report(lines, at="t2")
        self.assertIn("changed: ~/.codex/sessions/thread.jsonl", changed)
        self.assertIn("added: ~/.pi/agent/session.jsonl", changed)
        self.assertTrue(any(x.strip().startswith("~/.codex: 1 changed") for x in lines), lines)
        self.assertTrue(any(x.strip().startswith("~/.pi: 1 added") for x in lines), lines)  # and its folder changed
        with open(night.report_path("2099-03-01", "t2")) as f:
            text = f.read()
        self.assertIn("added: ~/.pi/agent/session.jsonl", text)
        self.assertEqual(os.stat(night.report_path("2099-03-01", "t2")).st_mode & 0o777, 0o600)

    def test_the_keychain_items_by_name_never_a_secret(self):
        self.save()
        with open(night.everyday_path("2099-03-01")) as f:
            saved = f.read()
        self.assertIn("Claude Code-credentials", saved)
        self.keychain[4] = '    "mdat"<timedate>=0x3230323631313232  "20261122000000Z\\000"'  # the item changed
        self.keychain += ['keychain: "/k"', 'class: "genp"', '    "svce"<blob>="groundtruth PROVIMUX_KEY"']
        lines = []
        self.assertCountEqual(self.report(lines), ['Keychain item added: class "genp", svce "groundtruth PROVIMUX_KEY"',
                                                   'Keychain item changed: class "genp", svce "Claude Code-credentials"'])
        self.assertIn('  Keychain item added: class "genp", svce "groundtruth PROVIMUX_KEY"', lines)

    def test_the_report_is_never_a_stop(self):
        self.save()
        with open(os.path.join(self.user, ".codex", "sessions", "thread.jsonl"), "w") as f:
            f.write("changed\n\n")
        real = night.snapshot_files
        with mock.patch.object(night, "keychain_items", return_value=[]), \
                mock.patch.object(night, "snapshot_files", lambda user_home=None, vanished=None: real(self.user, vanished)):
            night.main(["--date", "2099-03-01", "untouched", "--report"])  # no SystemExit: a report, exit 0

    def test_a_report_needs_the_snapshot(self):
        with self.assertRaisesRegex(SystemExit, "no snapshot"):
            self.report()

    def test_the_state_folders_are_checked_before_the_logins(self):
        os.symlink(os.path.join(self.user, ".codex"), os.path.join(self.base, "codex-cli", "x"))
        with self.assertRaisesRegex(SystemExit, "links that leave it"):
            self.save("2099-03-02")

    def test_the_snapshot_makes_and_checks_each_client_s_throwaway_home(self):
        self.save()
        for name in ("codex-cli", "devin-cli"):
            self.assertTrue(os.path.isdir(os.path.join(self.base, "home", name)))
            self.assertEqual(os.stat(os.path.join(self.base, "home", name)).st_mode & 0o777, 0o700)
        os.symlink(os.path.join(self.user, ".pi"), os.path.join(self.base, "home", "devin-cli", "agent"))
        with self.assertRaisesRegex(SystemExit, "HOME holds links that leave it"):
            self.save("2099-03-02")

    def test_a_throwaway_home_that_is_a_link_out_is_refused(self):
        os.makedirs(os.path.join(self.base, "home"))
        os.symlink(os.path.join(self.user, ".codex"), os.path.join(self.base, "home", "codex-cli"))
        with self.assertRaisesRegex(SystemExit, "not under <client-home>"):
            self.save()

    def test_the_snapshot_is_taken_once(self):
        self.save()
        with self.assertRaisesRegex(SystemExit, "once"):
            self.save()


if __name__ == "__main__":
    unittest.main()
