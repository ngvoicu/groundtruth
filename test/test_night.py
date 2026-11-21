"""harness/night.py: the run plan, its dry run, and the launcher against fakes (nothing is run or sent; the review's
reproductions of findings 1, 4, 9, 10 and 12).

    python3 -m unittest discover -s test -p "test_*.py"
"""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "harness"))
import night  # noqa: E402
import probe  # noqa: E402


def ids(prefix, n, start=1):
    return [f"{prefix}{i}" for i in range(start, n + 1)]


class Plan(unittest.TestCase):
    def test_every_run_of_the_narrowed_night_is_in_the_plan(self):
        want = (ids("OR", 5) + ids("OW", 9) + ["S1", "S2", "S3", "S3b", "S4", "SP"] + ids("CC", 8) + ids("CX", 6)
                + ids("DV", 17) + ["DV9d"] + ids("MC", 3) + ["CXS-a"])
        for i in want:
            self.assertIn(i, night.ALL_STEPS)

    def test_no_input_limit_walk_and_no_antigravity(self):
        for step in night.ALL_STEPS.values():
            argv = " ".join(night.command(step, "2026-11-23"))
            self.assertNotIn("client_limits", argv)
            self.assertNotIn("agy", argv)
        for gone in ("CL1", "DL1", "ML1", "S1-refusal", "S5", "AG1"):
            self.assertNotIn(gone, night.ALL_STEPS)

    def test_the_pairs_of_the_parity_design(self):
        pairs = {"P-CC3": ("claude-sonnet-5-5", "CC-1"), "P-CC4": ("claude-haiku-5-5", "CC-2"),
                 "P-CX4": ("gpt-6.1-terra", "CX-1"), "P-CX3": ("gpt-6.1-sol", "CX-2"), "P-CX1": ("gpt-6.2-sol", "CX-3"),
                 "P-DV1": ("devin/claude-opus-5-5-low", "DV-1"), "P-DV9": ("devin/glm-5-3-low", "DV-2"),
                 "P-DV11": ("devin/nemotron-3-5-super-none", "DV-3"), "P-DV14": ("devin/grok-4-7-low", "DV-4"),
                 "P-DV5": ("devin/gpt-6-1-terra-low", "DV-6"), "P-MC1": ("muse-wonder-1.0", "MC-1 (without the 24 h rule)"),
                 "P-MC1b": ("muse-wonder-1.0", "MC-1 (with the 24 h rule)")}
        for pid, (model, pair) in pairs.items():
            step = night.ALL_STEPS[pid]
            self.assertEqual((step["harness"], step["model"], step["pair"]), ("pi", model, pair))
        # one pi run per pair, CX-3 once (its second run, under Provimux's own name, is skipped)
        self.assertEqual(len([s for s in night.ALL_STEPS.values() if s.get("harness") == "pi" and s["kind"] == "probe"]), 12)
        # a pi run takes its own-client run's schedule and filler, and starts right after it
        for own, pi in (("CC3", "P-CC3"), ("CX4", "P-CX4"), ("DV11", "P-DV11"), ("MC1", "P-MC1")):
            a, b = night.ALL_STEPS[own]["args"], night.ALL_STEPS[pi]["args"]
            for flag in ("--ages", "--schedule", "--filler"):
                self.assertEqual(flag in a and a[a.index(flag) + 1], flag in b and b[b.index(flag) + 1])
        order = [s["id"] for s in night.select(["devin", "devin-terra-pi"])]
        self.assertEqual(order[order.index("DV5") + 1], "P-DV5")
        self.assertIn("--devin-daemon", night.ALL_STEPS["DV9d"]["args"])  # DV-5
        self.assertEqual(night.ALL_STEPS["DV9"]["args"][night.ALL_STEPS["DV9"]["args"].index("--schedule") + 1], "std")

    def test_claude_short_runs_set_the_5_minute_lifetime(self):
        for i in ids("CC", 8, 5):
            argv = night.command(night.ALL_STEPS[i], "2026-11-23")
            self.assertIn("CLAUDE_CODE_PROMPT_CACHE_TTL=5m", argv)
            self.assertEqual(argv[argv.index("--ages") + 1], "10m,15m")

    def test_s1_uses_the_filler_haiku_accepts(self):
        # Review note 13: Haiku refused the random filler on the login.
        argv = night.command(night.ALL_STEPS["S1"], "2026-11-23")
        self.assertEqual(argv[argv.index("--filler") + 1], "list")
        self.assertIn("--keep-raw", argv)

    def test_dv11_and_dv17_record_the_effort_they_ask(self):
        # Review finding 12.
        for i, effort in (("DV11", "none"), ("DV17", "medium"), ("DV1", "low")):
            args = night.command(night.ALL_STEPS[i], "2099-01-01")[2:]
            a = probe.parser().parse_args(args)
            self.assertEqual(probe.HARNESSES[a.harness](a.model, a.effort).effective_effort(), effort)

    def test_results_folders(self):
        self.assertIn("results/own-clients-2026-11-23", night.command(night.ALL_STEPS["CX1"], "2026-11-23"))
        self.assertIn("results/own-clients-2026-11-23/smoke", night.command(night.ALL_STEPS["S1"], "2026-11-23"))
        self.assertIn("results/openrouter-direct-2026-11-23", night.command(night.ALL_STEPS["OR1"], "2026-11-23"))

    def test_the_dry_run_sends_nothing(self):
        lines = []
        night.dry_run(night.select(["S1", "CC5", "OW1", "P-DV11"]), "2099-01-01", out=lines.append)
        text = "\n".join(lines)
        self.assertIn("at most 3 requests", text)
        self.assertIn("CLAUDE_CODE_PROMPT_CACHE_TTL", text)
        self.assertIn("cliproxyapi/devin/nemotron-3-5-super-none", text)
        self.assertIn("nothing sent", text)
        self.assertFalse(os.path.exists(os.path.join(night.ROOT, "results", "own-clients-2099-01-01")))
        self.assertFalse(os.path.exists(os.path.join(night.ROOT, "results", "openrouter-direct-2099-01-01")))


class Window(unittest.TestCase):
    """Review finding 4: the printed window command honours --dry-run, needs --go, and goes direct."""

    def test_only_go_sends(self):
        for flags, live in (([], False), (["--dry-run"], False), (["--go"], True)):
            with mock.patch.object(night, "window") as w, redirect_stdout(io.StringIO()):
                night.main(["--date", "2099-01-01", *flags, "window", "m"])
            self.assertEqual(w.call_args.kwargs["live"], live, flags)

    def test_without_go_nothing_is_posted(self):
        with mock.patch.object(night, "openrouter_post") as post, redirect_stdout(io.StringIO()) as out:
            night.window("m", "2099-01-01", live=False)
        post.assert_not_called()
        self.assertIn("Not sent", out.getvalue())

    def test_a_shell_key_alone_does_not_send_past_the_money_stop(self):
        get = lambda path, key: {"data": {"usage": 4.5}}  # noqa: E731
        with mock.patch.dict(os.environ, {"CACHE_PROBE_KEY": "synthetic"}), \
                mock.patch.object(night, "openrouter_post") as post, self.assertRaisesRegex(SystemExit, "stop"):
            night.window("m", "2099-01-01", live=True, get=get, out=lambda *_: None)
        post.assert_not_called()

    def test_openrouter_never_goes_through_a_proxy_of_the_environment(self):
        with mock.patch.dict(os.environ, {"HTTPS_PROXY": "http://127.0.0.1:8317", "https_proxy": "http://127.0.0.1:8317"}):
            handlers = [h for h in night.DIRECT.handlers if h.__class__.__name__ == "ProxyHandler"]
            self.assertTrue(all(not h.proxies for h in handlers))
            env = night.clean_env({"CACHE_PROBE_KEY": "k"})
        for k in night.PROXY_VARS:
            self.assertNotIn(k, env)
        argv = night.command(night.ALL_STEPS["OR1"], "d")
        self.assertEqual(argv[argv.index("--base-url") + 1], "https://openrouter.ai/api/v1")
        self.assertNotIn("8317", " ".join(" ".join(night.command(s, "d")) for s in night.PARTS["openrouter"] + night.PARTS["windows"]))


class Launcher(unittest.TestCase):
    """Review findings 9 and 10, against a fake process table and a fake OpenRouter."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = os.path.join(self.tmp.name, "repo")
        os.makedirs(self.root)
        self.home = os.path.join(self.tmp.name, "client-home")
        os.makedirs(self.home)
        p = [mock.patch.object(night, "ROOT", self.root), mock.patch.dict(os.environ, {"GROUNDTRUTH_CLIENT_HOME": self.home}),
             mock.patch.object(night, "keychain", return_value="synthetic-key-0123456789"),
             mock.patch.object(night.scan_secrets, "remember")]
        for x in p:
            x.start()
            self.addCleanup(x.stop)
        self.addCleanup(self.tmp.cleanup)

    def test_the_money_stop_is_checked_before_every_launch(self):
        ledger = {"spent": 3.50, "launched": []}

        def get(path, key):
            if path == "/key":
                return {"data": {"usage": ledger["spent"]}}
            return {"data": {"endpoints": [{"pricing": {"prompt": "0.000001", "completion": "0.000002"}}]}}

        def popen(argv, **kw):
            ledger["launched"].append(argv[argv.index("--label") + 1])
            ledger["spent"] += 0.03
            return SimpleNamespace(pid=100 + len(ledger["launched"]))
        # each run's worst case is 90 x (3000 x 1e-6 + 32 x 2e-6) = 0.28: committed estimates add up
        with self.assertRaisesRegex(SystemExit, "would pass the 4.00 USD stop"):
            night.go(night.select(["openrouter"]), "2099-02-01", popen=popen, sleep=lambda s: None, get=get,
                     check_everyday=False, out=lambda *_: None)
        self.assertEqual(ledger["launched"], ["OR1"])  # 3.53 + 0.28 committed + 0.28 > 4.00

    def test_an_unknown_spend_starts_nothing(self):
        with self.assertRaisesRegex(SystemExit, "unknown"):
            night.go(night.select(["OR1"]), "2099-02-01", popen=mock.Mock(), sleep=lambda s: None,
                     get=lambda p, k: {"data": {}}, check_everyday=False, out=lambda *_: None)

    def smoke_run(self, codes):
        seq = []

        def run(argv, **kw):
            label = argv[argv.index("--label") + 1]
            seq.append(label)
            folder = os.path.join(self.root, night.folders("2099-02-02")["smoke"])
            os.makedirs(folder, exist_ok=True)
            with open(os.path.join(folder, label + ".jsonl"), "w") as f:
                f.write(json.dumps({"event": "start"}) + "\n" + json.dumps({"event": "done" if codes.get(label, 0) == 0 else "stop"}) + "\n")
            return SimpleNamespace(returncode=codes.get(label, 0))
        return seq, run

    def test_smoke_waits_for_each_run_and_a_rerun_skips_what_is_done(self):
        seq, run = self.smoke_run({})
        popen = mock.Mock()
        night.go(night.select(["smoke"]), "2099-02-02", popen=popen, run=run, check_everyday=False, out=lambda *_: None)
        popen.assert_not_called()  # in the foreground, one after the other
        self.assertEqual(seq, ["S1", "S2", "S3", "S3b", "S4", "SP"])
        night.go(night.select(["smoke"]), "2099-02-02", popen=popen, run=run, check_everyday=False, out=lambda *_: None)
        self.assertEqual(len(seq), 6, "nothing sent twice")

    def test_a_smoke_failure_stops_the_launcher(self):
        seq, run = self.smoke_run({"S2": 1})
        with self.assertRaisesRegex(SystemExit, "S2"):
            night.go(night.select(["smoke"]), "2099-02-02", run=run, check_everyday=False, out=lambda *_: None)

    def test_a_rerun_skips_detached_runs_started_once(self):
        launched = []

        def popen(argv, **kw):
            launched.append(argv[argv.index("--label") + 1])
            return SimpleNamespace(pid=200 + len(launched))
        steps = night.select(["CC1", "CC2"])
        night.go(steps, "2099-02-03", popen=popen, sleep=lambda s: None, check_everyday=False, out=lambda *_: None)
        night.go(steps, "2099-02-03", popen=popen, sleep=lambda s: None, check_everyday=False, out=lambda *_: None)
        self.assertEqual(launched, ["CC1", "CC2"])

    def test_the_guards(self):
        with self.assertRaisesRegex(SystemExit, "all"):
            night.guard(["all"], night.select(["all"]), "2099-02-04")
        with self.assertRaisesRegex(SystemExit, "smoke runs go alone"):
            night.guard(["smoke", "claude"], night.select(["smoke", "claude"]), "2099-02-04")
        with self.assertRaisesRegex(SystemExit, "smoke results were read"):
            night.guard(["claude"], night.select(["claude"]), "2099-02-04")
        night.guard(["openrouter"], night.select(["openrouter"]), "2099-02-04")  # no login: no smoke needed
        os.makedirs(night.night_dir("2099-02-04"))
        open(night.reviewed_path("2099-02-04"), "w").close()
        night.guard(["claude"], night.select(["claude"]), "2099-02-04")

    def test_stop_finds_each_runs_pid_folder_and_checks_the_process(self):
        for sid, folder in (("S1", "smoke"), ("OR1", "or"), ("CC1", "own")):
            logs = os.path.join(self.root, night.folders("2099-02-05")[folder], "logs")
            os.makedirs(logs, exist_ok=True)
            with open(os.path.join(logs, sid + ".pid"), "w") as f:
                f.write("4242\n")
            killed = []
            night.stop(sid, "2099-02-05", ps=lambda p: f"caffeinate -i python3 x --label {sid} --out y",
                       killpg=lambda p, s: killed.append(p), out=lambda *_: None)
            self.assertEqual(killed, [4242])
            with self.assertRaisesRegex(SystemExit, "not this run"):
                night.stop(sid, "2099-02-05", ps=lambda p: "some other program", killpg=lambda p, s: killed.append(p))


class Everyday(unittest.TestCase):
    """Review finding 1: the everyday folders compared to their depth, ~/.pi included, and the Keychain's items."""

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
        p = mock.patch.dict(os.environ, {"GROUNDTRUTH_CLIENT_HOME": os.path.join(self.tmp.name, "client-home")})
        p.start()
        self.addCleanup(p.stop)

    def lister(self):
        return lambda: "\n".join(self.keychain)

    def check(self):
        return night.untouched("2099-03-01", "compare", user_home=self.user, lister=self.lister(), out=lambda *_: None)

    def test_a_nested_edit_and_a_file_under_pi_are_seen(self):
        night.untouched("2099-03-01", "save", user_home=self.user, lister=self.lister(), out=lambda *_: None)
        self.assertTrue(self.check())
        with open(os.path.join(self.user, ".codex", "sessions", "thread.jsonl"), "w") as f:
            f.write("a new conversation, longer\n")
        lines = []
        self.assertFalse(night.untouched("2099-03-01", "compare", user_home=self.user, lister=self.lister(), out=lines.append))
        self.assertIn("changed: ~/.codex/sessions/thread.jsonl", lines[0])

    def test_pi_is_snapshotted(self):
        night.untouched("2099-03-01", "save", user_home=self.user, lister=self.lister(), out=lambda *_: None)
        with open(os.path.join(self.user, ".pi", "agent", "sentinel"), "w") as f:
            f.write("added")
        self.assertFalse(self.check())

    def test_the_keychain_items_by_name_never_a_secret(self):
        night.untouched("2099-03-01", "save", user_home=self.user, lister=self.lister(), out=lambda *_: None)
        with open(night.everyday_path("2099-03-01")) as f:
            saved = f.read()
        self.assertIn("Claude Code-credentials", saved)
        self.keychain[4] = '    "mdat"<timedate>=0x3230323631313232  "20261122000000Z\\000"'  # the item changed
        lines = []
        self.assertFalse(night.untouched("2099-03-01", "compare", user_home=self.user, lister=self.lister(), out=lines.append))
        self.assertIn("Keychain item", lines[0])

    def test_a_login_s_new_keychain_item_is_accepted_only_by_the_owner(self):
        night.untouched("2099-03-01", "save", user_home=self.user, lister=self.lister(), out=lambda *_: None)
        self.keychain += ['keychain: "/k"', 'class: "genp"', '    "svce"<blob>="Claude Code-credentials-abc123"']
        self.assertFalse(self.check())
        night.untouched("2099-03-01", "accept", user_home=self.user, lister=self.lister(), out=lambda *_: None)
        self.assertTrue(self.check())

    def test_the_launcher_stops_on_a_difference(self):
        night.untouched("2099-03-01", "save", user_home=self.user, lister=self.lister(), out=lambda *_: None)
        with open(os.path.join(self.user, ".codex", "sessions", "thread.jsonl"), "w") as f:
            f.write("changed\n\n")
        with mock.patch.object(night, "untouched", return_value=False), \
                self.assertRaisesRegex(SystemExit, "the night stops here"):
            night.go(night.select(["CC1"]), "2099-03-01", popen=mock.Mock(), out=lambda *_: None)

    def test_the_snapshot_is_taken_once(self):
        night.untouched("2099-03-01", "save", user_home=self.user, lister=self.lister(), out=lambda *_: None)
        with self.assertRaisesRegex(SystemExit, "once"):
            night.untouched("2099-03-01", "save", user_home=self.user, lister=self.lister(), out=lambda *_: None)


if __name__ == "__main__":
    unittest.main()
