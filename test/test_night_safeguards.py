"""The weekly night's safeguards (docs/weekly-night.md):
1. the night looks at the checkout it runs from before it starts (weekly.check_checkout, Night.look_at_checkout):
   real git repositories in a temporary folder, a local bare repository standing for GitHub;
2. since 2026-11-26 no value is left out for what it costs: the record of values "too dear for the caps"
   (plan/not-measured.md, 2026-11-25) is retired, and the values it held are measured.
Nothing is sent to any vendor; no notification is shown.

    python3 -m unittest discover -s test -p "test_*.py"
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "harness"))
import asks as A  # noqa: E402
import plan as P  # noqa: E402
import weekly as W  # noqa: E402
from test_weekly_night import DATE, Fake, NightCase, bucharest, entry, fixture_site  # noqa: E402

GIT_ENV = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t" + "@" + "example.invalid", GIT_COMMITTER_NAME="t",
               GIT_COMMITTER_EMAIL="t" + "@" + "example.invalid", GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")


def git(cwd, *args):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, env=GIT_ENV)
    if r.returncode:
        raise AssertionError(f"git {' '.join(args)}: {r.stderr}")
    return r.stdout.strip()


class Repos(unittest.TestCase):
    """`hub`: a bare repository standing for GitHub; `work`: the night's checkout, cloned from it."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = self.tmp.name
        self.hub, self.seed, self.work = (os.path.join(t, n) for n in ("hub.git", "seed", "work"))
        git(t, "init", "-q", "--bare", "-b", "main", self.hub)
        git(t, "clone", "-q", self.hub, self.seed)
        git(self.seed, "checkout", "-q", "-b", "main")
        self.commit(self.seed, "a.txt", "1\n")
        with open(os.path.join(self.seed, ".gitignore"), "w") as f:
            f.write("logs/\n")
        git(self.seed, "add", ".gitignore")
        git(self.seed, "commit", "-q", "-m", "ignore")
        git(self.seed, "push", "-q", "origin", "main")
        git(t, "clone", "-q", self.hub, self.work)

    def tearDown(self):
        self.tmp.cleanup()

    def commit(self, repo, name, text, push=False):
        with open(os.path.join(repo, name), "w") as f:
            f.write(text)
        git(repo, "add", name)
        git(repo, "commit", "-q", "-m", f"{name} {text.strip()}")
        if push:
            git(repo, "push", "-q", "origin", "main")
        return git(repo, "rev-parse", "HEAD")

    def check(self, **kw):
        old = os.environ.copy()
        os.environ.update({k: v for k, v in GIT_ENV.items() if k.startswith("GIT_")})
        try:
            return W.check_checkout(self.work, url=self.hub, **kw)
        finally:
            os.environ.clear()
            os.environ.update(old)

    def head(self):
        return git(self.work, "rev-parse", "HEAD")


class TheCheckout(Repos):
    def test_clean_on_main_at_github_is_ready(self):
        c = self.check(update=True)
        self.assertEqual((c["problems"], c["behind"], c["updated"]), ([], 0, None))

    def test_untracked_and_ignored_files_never_count(self):
        os.makedirs(os.path.join(self.work, "logs"))
        for path in ("logs/private.log", "results-new.json"):
            with open(os.path.join(self.work, path), "w") as f:
                f.write("x\n")
        self.assertEqual(self.check()["problems"], [])

    def test_a_change_to_a_tracked_file_staged_or_not_stops_it(self):
        with open(os.path.join(self.work, "a.txt"), "w") as f:
            f.write("changed\n")
        c = self.check(update=True)
        self.assertEqual(c["problems"], ["1 tracked files changed (a.txt)"])
        self.assertEqual(c["fixes"], ['git stash push -m "kept before the weekly night"'])
        git(self.work, "add", "a.txt")
        self.assertEqual(len(self.check()["problems"]), 1)

    def test_another_branch_or_a_detached_head_stops_it(self):
        git(self.work, "switch", "-q", "-c", "someone-s-work")
        c = self.check()
        self.assertEqual(c["problems"], ["on the branch someone-s-work, not main"])
        self.assertEqual(c["fixes"], ["git switch main"])
        git(self.work, "switch", "-q", "--detach", "main")
        self.assertIn("on no branch (HEAD detached at", self.check()["problems"][0])

    def test_a_commit_github_lacks_stops_it_and_says_how_to_keep_it(self):
        mine = self.commit(self.work, "b.txt", "local\n")
        c = self.check(update=True)
        self.assertEqual(len(c["problems"]), 1)
        self.assertIn("`main` holds 1 commits GitHub's main lacks", c["problems"][0])
        gh = git(self.hub, "rev-parse", "main")
        self.assertEqual(c["fixes"], [f"git branch kept-{mine[:7]} main && git reset --keep {gh[:12]}"])
        self.assertEqual(self.head(), mine)  # nothing moved

    def test_behind_and_clean_it_fast_forwards_and_checks_the_result(self):
        old = self.head()
        new = self.commit(self.seed, "c.txt", "pushed on Monday afternoon\n", push=True)
        c = self.check(update=True)
        self.assertEqual(c["problems"], [])
        self.assertEqual(c["updated"], [old, new])
        self.assertEqual(self.head(), new)
        self.assertEqual(git(self.work, "status", "--porcelain", "--untracked-files=no"), "")

    def test_behind_the_dry_check_reads_github_and_writes_nothing(self):
        old = self.head()
        new = self.commit(self.seed, "c.txt", "new\n", push=True)
        refs = git(self.work, "for-each-ref")
        c = self.check(update=False, dry=True)
        self.assertEqual((c["problems"], c["github"], self.head()), ([], new, old))
        self.assertIn("not fetched here yet", c["note"])
        self.assertEqual(git(self.work, "for-each-ref"), refs)

    def test_an_update_refused_before_it_writes_leaves_the_old_commit_and_runs_on_it(self):
        old = self.head()
        self.commit(self.seed, "d.txt", "tracked upstream\n", push=True)
        with open(os.path.join(self.work, "d.txt"), "w") as f:  # untracked here, in the way of the update
            f.write("mine\n")
        c = self.check(update=True)
        self.assertEqual(c["problems"], [])
        self.assertIsNone(c["updated"])
        self.assertTrue(c["not_updated"])
        self.assertEqual(self.head(), old)
        with open(os.path.join(self.work, "d.txt")) as f:
            self.assertEqual(f.read(), "mine\n")

    def test_github_unreachable_the_last_fetched_main_stands_in(self):
        self.check(update=True)  # fetched once: GITHUB_REF
        self.commit(self.seed, "e.txt", "x\n", push=True)
        os.rename(self.hub, self.hub + ".away")
        c = self.check(update=True)
        self.assertEqual(c["problems"], [])
        self.assertEqual(c["github_from"], "fetched last")
        self.assertIn("GitHub not reached", c["note"])

    def test_github_unreachable_and_never_fetched_stops_it(self):
        git(self.work, "remote", "remove", "origin")
        os.rename(self.hub, self.hub + ".away")
        c = self.check(update=True)
        self.assertIn("GitHub's main could not be read", c["problems"][0])


class CheckoutWorld(Fake):
    """The fake world with a checkout: `c` is what check_checkout would return."""

    def __init__(self, *a, checkout=None, **kw):
        super().__init__(*a, **kw)
        self.c = checkout

    def checkout(self, update):
        self.calls.append(("checkout", update))
        return json.loads(json.dumps(self.c))

    def restart(self, c):
        self.calls.append(("restart",))


def look(problems=(), fixes=(), behind=0, **kw):
    c = {"branch": "main", "head": "a" * 40, "main": "a" * 40, "github": "b" * 40, "github_from": "fetched from GitHub now",
         "behind": behind, "changed": [], "problems": list(problems), "fixes": list(fixes), "updated": None,
         "not_updated": None, "note": None}
    c.update(kw)
    return c


class TheNightLooksFirst(NightCase):
    def test_a_checkout_not_ready_starts_nothing_writes_its_state_asks_and_notifies(self):
        fake = CheckoutWorld(bucharest(0, 23), fixture_site(codex=2, devin=1), checkout=look(
            ["on the branch other, not main"], ["git switch main"], branch="other"))
        n = self.night(fake)
        self.assertEqual([c[0] for c in fake.calls], ["checkout"])  # no site, no key, no login, no run
        self.assertFalse(os.path.exists(os.path.join(self.home, f"night-{DATE}", "weekly.json")))  # no lock
        with open(os.path.join(self.home, f"night-{DATE}", "state.json")) as f:
            state = json.load(f)
        self.assertEqual((state["started"], state["reason"]), (False, "checkout not ready"))
        ask = self.asks("checkout-not-ready")[0]
        self.assertEqual(ask["command"].split("   #")[0],
                         "git switch main && python3 harness/weekly.py --date <today> --go night")
        self.assertIn("on the branch other, not main", ask["first_line"])
        self.assertEqual(len(fake.notes), 1)
        self.assertFalse(n.state_out["started"])
        # Mended: the next start (the ask's command) runs the night and closes the ask.
        fixed = CheckoutWorld(bucharest(0, 23, 30), fixture_site(codex=1, devin=0), checkout=look())
        self.night(fixed, only=["codex"])
        self.assertEqual(self.asks("checkout-not-ready"), [])
        self.assertTrue(fixed.started("cx-"))

    def test_the_dry_run_reports_the_same_check_and_goes_on(self):
        fake = CheckoutWorld(bucharest(0, 23), fixture_site(codex=1, devin=0), checkout=look(
            ["1 tracked files changed (a.txt)"], ['git stash push -m "kept before the weekly night"']))
        n = self.night(fake, dry=True, only=["codex"])
        self.assertEqual(fake.calls[0], ("checkout", False))
        text = n.state_out["dry_report"]
        self.assertIn("## The checkout", text)
        self.assertIn("NOT READY: 1 tracked files changed (a.txt)", text)
        self.assertIn("On the night it would not start", text)
        self.assertIn("The night of 2026-11-30 did not start: the checkout is not ready", text)
        self.assertIn("## codex: 1 of at most 6", text)
        self.assertEqual(os.listdir(self.home), [])

    def test_a_fast_forward_starts_the_night_again_on_the_new_code(self):
        fake = CheckoutWorld(bucharest(0, 23), fixture_site(codex=1, devin=0),
                             checkout=look(updated=["a" * 40, "b" * 40]))
        self.night(fake)
        self.assertEqual([c[0] for c in fake.calls], ["checkout", "restart"])
        self.assertFalse(os.path.exists(os.path.join(self.home, f"night-{DATE}", "weekly.json")))

    def test_an_update_refused_runs_the_night_and_asks_without_stopping_anything(self):
        fake = CheckoutWorld(bucharest(0, 23), fixture_site(codex=1, devin=0),
                             checkout=look(behind=2, not_updated="untracked d.txt would be overwritten"))
        self.night(fake, only=["codex"])
        self.assertTrue(fake.started("cx-"))
        self.assertEqual(self.asks("checkout-not-updated")[0]["stops"], "nothing")
        self.assertIn("## The checkout", self.report())

    def test_a_started_night_s_state_is_never_overwritten_by_a_failed_look(self):
        self.night(CheckoutWorld(bucharest(0, 23), fixture_site(codex=1, devin=0), checkout=look()), only=["codex"])
        path = os.path.join(self.home, f"night-{DATE}", "state.json")
        with open(path) as f:
            before = f.read()
        self.night(CheckoutWorld(bucharest(0, 23, 5), fixture_site(codex=1, devin=0),
                                 checkout=look(["on the branch x, not main"], ["git switch main"])), only=["codex"])
        with open(path) as f:
            self.assertEqual(f.read(), before)

    def test_a_leftover_not_measured_file_stops_nothing(self):
        os.makedirs(os.path.join(self.root, "plan"))
        with open(os.path.join(self.root, "plan", "not-measured.md"), "w") as f:
            f.write("| Value | Decided | By | Reason |\n|---|---|---|---|\n| gpt-6-cyber | yesterday | me | dear |\n")
        fake = CheckoutWorld(bucharest(0, 23), fixture_site(codex=1, devin=0), checkout=look())
        self.night(fake)
        self.assertEqual(self.asks("checkout-not-ready"), [])
        self.assertIn(("site",), fake.calls)


# --- 2. no value left out for what it costs ---------------------------------------------------------------------------

def dear_site():
    """openai-api `dear`: a cache run of $5.22 and a window check of $22.02 (both above the retired caps);
    openrouter `x/mid`: a cache run of $2.61."""
    es = [entry("openai", "dear", price_in=20.0), entry("openrouter", "x/mid", price_in=10.0),
          entry("openrouter", "a/cheap", price_in=0.1)]
    return {"dataset": "fixture", "entries": {f"{e['provider']}/{e['model']}": e for e in es}}


class NoCapOnMoney(NightCase):
    def test_the_record_of_values_too_dear_is_gone(self):
        self.assertFalse(os.path.exists(os.path.join(ROOT, "plan", "not-measured.md")))
        for name in ("DECISIONS", "load_decisions", "ABOVE_CAPS", "decision_line", "cap_of"):
            self.assertFalse(hasattr(P, name), name)

    def test_the_values_once_too_dear_are_planned_and_sent(self):
        fake = Fake(bucharest(0, 23), dear_site())
        n = self.night(fake, only=["keys"])
        planned = {i["key"] for i in n.plan["planned"]}
        self.assertTrue({"openai-api|dear|cache", "openai-api|dear|window", "openrouter|x/mid|cache"} <= planned)
        self.assertIn(("window", "oa-dear-window"), fake.calls)
        self.assertIn("oa-dear", fake.started())
        self.assertIn("or-x-mid", fake.started())
        self.assertEqual(self.asks(), [])
        with open(os.path.join(self.root, "results", f"night-{DATE}", "PLAN.md")) as f:
            plan_md = f.read()
        self.assertNotIn("above the caps", plan_md)
        self.assertIn("| openai-api | `dear` | cache | new", plan_md)

    def test_the_old_options_are_gone(self):
        r = subprocess.run([sys.executable, os.path.join(ROOT, "harness", "weekly.py"), "--date", DATE, "--dry-run",
                            "night", "--week-cap", "20"], capture_output=True, text=True,
                           env=dict(os.environ, GROUNDTRUTH_CLIENT_HOME=self.home))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("--week-cap", r.stderr)


if __name__ == "__main__":
    unittest.main()
