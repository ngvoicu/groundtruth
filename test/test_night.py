"""harness/night.py: the run plan of docs/own-clients.md, section 4, and its dry run (nothing is run or sent).

    python3 -m unittest discover -s test -p "test_*.py"
"""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "harness"))
import night  # noqa: E402


def ids(prefix, n, start=1):
    return [f"{prefix}{i}" for i in range(start, n + 1)]


class Plan(unittest.TestCase):
    def test_every_run_of_the_design_is_in_the_plan(self):
        want = (ids("OR", 5) + ids("OW", 9) + ["S1", "S2", "S3", "S3b", "S4"] + ids("CC", 8) + ids("CX", 6)
                + ids("DV", 17) + ids("MC", 3) + ids("CL", 4) + ids("DL", 12) + ids("ML", 3))
        for i in want:
            self.assertIn(i, night.ALL_STEPS)

    def test_no_antigravity_run(self):
        for step in night.ALL_STEPS.values():
            self.assertNotIn("agy", " ".join(night.command(step, "2026-11-23")))
        self.assertNotIn("S5", night.ALL_STEPS)
        self.assertNotIn("AG1", night.ALL_STEPS)

    def test_claude_short_runs_set_the_5_minute_lifetime(self):
        for i in ids("CC", 8, 5):
            argv = night.command(night.ALL_STEPS[i], "2026-11-23")
            self.assertIn("CLAUDE_CODE_PROMPT_CACHE_TTL=5m", argv)
            self.assertEqual(argv[argv.index("--ages") + 1], "10m,15m")
        for i in ids("CC", 4):
            argv = night.command(night.ALL_STEPS[i], "2026-11-23")
            self.assertEqual(argv[argv.index("--ages") + 1], night.STD65)
            self.assertIn("list", argv)

    def test_codex_has_no_limits_walk_and_long_runs(self):
        self.assertFalse([s for s in night.ALL_STEPS.values() if s["kind"] == "limits" and s["harness"] == "codex"
                          and "--only-refusal" not in s["args"]])
        for i in ids("CX", 6):
            self.assertIn("long", night.command(night.ALL_STEPS[i], "d"))

    def test_conditional_walks_are_not_in_the_night(self):
        night_steps = {s["id"] for s in night.select(["all"])}
        for i in ids("DL", 12) + ids("ML", 3):
            self.assertNotIn(i, night_steps)
        self.assertIn("CL1", night_steps)

    def test_results_folders(self):
        self.assertIn("results/own-clients-2026-11-23", night.command(night.ALL_STEPS["CX1"], "2026-11-23"))
        self.assertIn("results/openrouter-direct-2026-11-23", night.command(night.ALL_STEPS["OR1"], "2026-11-23"))

    def test_the_dry_run_sends_nothing(self):
        lines = []
        night.dry_run(night.select(["S1", "CC5", "DL1", "OW1"]), "2099-01-01", out=lines.append)
        text = "\n".join(lines)
        self.assertIn("at most 3 requests", text)
        self.assertIn("CLAUDE_CODE_PROMPT_CACHE_TTL", text)
        self.assertIn("--accepted 999500 --refused 1000300", text)
        self.assertIn("nothing sent", text)
        self.assertFalse(os.path.exists(os.path.join(night.ROOT, "results", "own-clients-2099-01-01")))
        self.assertFalse(os.path.exists(os.path.join(night.ROOT, "results", "openrouter-direct-2099-01-01")))

    def test_the_everyday_folders_are_compared_by_their_times_only(self):
        with tempfile.TemporaryDirectory() as home:
            os.makedirs(os.path.join(home, ".claude"))
            before = night.mtimes(home)
            self.assertIsNotNone(before["~/.claude"])
            self.assertIsNone(before["~/.codex"])
            os.utime(os.path.join(home, ".claude"), (1, 1))
            self.assertNotEqual(night.mtimes(home)["~/.claude"], before["~/.claude"])


if __name__ == "__main__":
    unittest.main()
