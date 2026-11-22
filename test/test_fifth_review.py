"""The final check of the first night at 7cc500c (the fifth review): the cases that remain after the sixth review's
change of approach (the per-turn Codex model rule, the stop race, Devin's status, the RUN wording), each replayed from
the review's receipts. The fifth review's version parsing and the stop's date-pattern search were removed with what
they tested (test_sixth_review). Every test here failed at 7cc500c. Nothing is sent and no real client is
run: stand-in programs, stand-in workers and stand-in launchers, in temporary folders.

    python3 -m unittest discover -s test -p "test_*.py"
"""
import io
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from contextlib import redirect_stdout, redirect_stderr
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
import test_second_review as R2  # noqa: E402  (as a module: its tests are not collected twice)
from test_probe import FakeClock  # noqa: E402

Owner = R2.Owner
write, DATE = R2.write, R2.DATE
SAVED = os.path.join(HERE, "fixtures", "review5")  # the review's own probe output at 7cc500c (publication.log)
MODEL = "gpt-6-luna"
NIGHT = "results/own-clients-2099-06-19"


def ps_table():
    """(pid, process group, command line) of every process: the tests' own view, to find and clean up their workers
    (harness/night.py looks up no process table)."""
    p = subprocess.run(["ps", "-ax", "-o", "pid=,pgid=,command="], capture_output=True, text=True)
    rows = []
    for line in p.stdout.splitlines():
        parts = line.split(None, 2)
        if len(parts) == 3 and parts[0].isdigit() and parts[1].isdigit():
            rows.append((int(parts[0]), int(parts[1]), parts[2]))
    return rows


def build(path, model=MODEL):
    return B.build_cache({"runs": [{"id": "CX6", "route": "codex-subscription", "file": path, "model": model}]})[0]


def build_in_night(rows, model=MODEL, audit=True):
    """The rows as a run of an audited night (results/own-clients-<date>/AUDIT.md, the publication gate), built."""
    with tempfile.TemporaryDirectory() as root:
        os.makedirs(os.path.join(root, NIGHT))
        if audit:
            write(os.path.join(root, NIGHT, "AUDIT.md"), B.AUDIT_FIRST_LINE + "\nfixture\n")
        write(os.path.join(root, NIGHT, "CX6.jsonl"), "".join(json.dumps(r) + "\n" for r in rows))
        with mock.patch.object(B, "ROOT", root):
            return build(NIGHT + "/CX6.jsonl", model)


class CodexNight(Owner):
    """The review's end-to-end replay (end_to_end.py): the real probe and builder, a stand-in Codex whose session file
    each variant writes; at 150 s the stand-in's answer comes from gpt-6-astra (except `matching-evidence`).
    VERSION is what its `--version` prints; `console` keeps what the probe printed to the console log."""

    VERSION = "codex-cli 0.171.0"
    PRIVATE = ("19.28.3746", "<model unavailable in fixture workspace>", "sk-" + "t345syntheticCanary1234567890",
               "/Volumes/FixtureData/test-campaign/" + "codex" + "-cli", "<unavailable in ~/.codex/" + "auth" + ".json>", "Gpt-Upper")

    def run_case(self, variant):
        base = self.client_home()
        state = os.path.join(base, "codex-cli")
        write(os.path.join(state, "auth.json"), "{}", 0o600)
        clock, sessions = FakeClock(), {}

        def append(sid, events):
            path = os.path.join(state, "sessions", "2099", "01", "01", f"rollout-2099-01-01T00-00-00-{sid}.jsonl")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "a") as f:
                f.write("".join(json.dumps(e) + "\n" for e in events))

        def ev(kind, turn, **kv):
            payload = dict(type=kind, **kv)
            if turn:
                payload["turn_id"] = turn
            return {"type": "event_msg", "payload": payload}

        def ctx(turn, model=MODEL):
            return {"type": "turn_context", "payload": {"turn_id": turn, "model": model}}

        def standin(argv, env, cwd, stdin, timeout):
            if "--version" in argv:
                return 0, self.VERSION, ""
            if "status" in argv:
                return 0, "Logged in using ChatGPT", ""
            new = "resume" not in argv
            sid = str(uuid.uuid4()) if new else argv[argv.index("resume") + 1]
            stdin.read()
            now = clock.now()
            if new:
                sessions[sid] = {"at": now, "n": len(sessions)}
            s = sessions[sid]
            age = round(now - s["at"])
            clock.t += 1
            changed = s["n"] >= 2 and not new and age == 150
            turn = str(uuid.uuid4())
            if new:
                s["prime_turn"] = turn
            astra = "gpt-6-astra"
            cases = {
                "old-context-after-complete": [ev("task_started", turn), ev("task_complete", turn), ctx(s["prime_turn"])],
                "context-after-reroute": [ev("task_started", turn), ctx(turn),
                                          ev("model_reroute", turn, from_model=MODEL, to_model=astra), ctx(turn),
                                          ev("task_complete", turn)],
                "explicit-reroute": [ev("task_started", turn), ctx(turn),
                                     ev("model_reroute", turn, from_model=MODEL, to_model=astra), ev("task_complete", turn)],
                # Codex's own ModelRerouteEvent has no turn id (from_model, to_model, reason).
                "reroute-without-id": [ev("task_started", turn), ctx(turn),
                                       ev("model_reroute", None, from_model=MODEL, to_model=astra),
                                       ev("task_complete", turn)],
                "other-model": [ev("task_started", turn), ctx(turn, astra), ev("task_complete", turn)],
                "two-turns": [ev("task_started", turn), ctx(turn), ev("task_complete", turn),
                              ev("task_started", turn + "b"), ctx(turn + "b"), ev("task_complete", turn + "b")],
                "no-model": [ev("task_started", turn), ev("task_complete", turn)],
                "complete-only": [ev("task_complete", turn)],
                "unchanged-rollout": [],
            }
            roll = cases[variant] if changed and variant in cases else \
                [ev("task_started", turn), ctx(turn), ev("task_complete", turn)]
            # The sixth review's run-level cases: the measured turn's own evidence is Luna, but the session file names
            # Astra elsewhere: in a record of no turn, before the saved offset after a rewrite, or in another session.
            if changed and variant == "astra-record-elsewhere":
                roll.insert(1, {"type": "event_msg", "payload": {"type": "token_count", "info": {"model": astra}}})
            if changed and variant == "rewrite-before-offset":
                path = os.path.join(state, "sessions", "2099", "01", "01", f"rollout-2099-01-01T00-00-00-{sid}.jsonl")
                with open(path) as f:
                    old = f.read()
                with open(path, "w") as f:
                    f.write(json.dumps(ev("model_reroute", None, from_model=MODEL, to_model=astra)) + "\n" + old)
            if new and s["n"] == 0 and variant == "astra-in-the-baseline":
                roll = [ev("task_started", turn), ctx(turn, astra), ev("task_complete", turn)]
            if new and s["n"] == 0 and variant == "private-strings":
                # The seventh review's fixtures (calendar-fixtures.log:2, path-test.log): model fields holding a
                # version, a diagnostic, a key-shaped value and paths, in a record of the never-checked baseline.
                roll = roll + [{"type": "diagnostic", "payload": {"m": [{"model": m} for m in self.PRIVATE]}}]
            append(sid, roll)
            total = (18000 if s["n"] == 0 else 25000) if new else 50020
            cached = 0 if new and s["n"] == 0 else (18000 if new else 43000)
            events = [{"type": "thread.started", "thread_id": sid}, {"type": "turn.started"},
                      {"type": "item.completed", "item": {"type": "agent_message", "id": "m", "text": "OK"}},
                      {"type": "turn.completed", "usage": {"input_tokens": total, "cached_input_tokens": cached,
                                                           "cache_write_input_tokens": total - cached, "output_tokens": 5}}]
            return 0, "".join(json.dumps(x) + "\n" for x in events), ""
        out = os.path.join(self.repo, "results", variant)
        console = io.StringIO()
        with mock.patch.object(C, "_run", side_effect=standin), mock.patch.object(probe, "Clock", return_value=clock), \
                redirect_stdout(io.StringIO()), redirect_stderr(console):
            probe.main(["--harness", "codex", "--model", MODEL, "--label", "CX6", "--ages", "2.5m", "--words", "20",
                        "--replicas", "1", "--out", out])
        self.console = console.getvalue()
        path = os.path.join(out, "CX6.jsonl")
        with open(path) as f:
            text = f.read()
        events = [json.loads(x) for x in text.splitlines()]
        row = next(e for e in events if e["event"] in ("check", "check-invalid") and e["age"] == "2.5m")
        return path, text, events, row


class Case3Model(CodexNight):
    """3: a Codex check counts only on exactly one new turn whose own model record (its id) names the requested model,
    with no other model record since the invocation began; anything else is check-invalid, and the builder refuses
    it."""

    def test_the_review_s_two_cases_and_their_kin(self):
        expected = {"old-context-after-complete": "ambiguous-model", "context-after-reroute": "ambiguous-model",
                    "explicit-reroute": "ambiguous-model", "reroute-without-id": "ambiguous-model",
                    "two-turns": "ambiguous-model", "other-model": "other-model", "no-model": "no-model",
                    "complete-only": "no-model", "unchanged-rollout": "no-model"}
        for variant, reason in expected.items():
            with self.subTest(variant=variant):
                path, text, events, row = self.run_case(variant)
                self.assertEqual((row["event"], row.get("reason")), ("check-invalid", reason))
                self.assertNotEqual(row["usage"].get("model_evidence"), "own-turn")
                if reason != "other-model":
                    self.assertIsNone(row["usage"].get("model"))
                with self.assertRaises(SystemExit):
                    build(path)

    def test_a_bound_answer_of_the_requested_model_still_counts(self):
        path, text, events, row = self.run_case("matching-evidence")
        self.assertEqual((row["event"], row["usage"]["model"], row["usage"]["model_evidence"]),
                         ("check", MODEL, "own-turn"))
        entry = build_in_night(events)
        self.assertEqual(entry["model"], MODEL)
        self.assertNotIn("client_version", entry)
        self.assertEqual(next(c for c in entry["checks"] if c["age_s"] == 150)["total"], 1)

    def test_the_review_s_published_artifacts_are_refused(self):
        # publication.log:2: the 7cc500c probe's output for the two cases, which its builder published as Luna.
        for variant in ("old-context-after-complete", "context-after-reroute"):
            with self.subTest(variant=variant), self.assertRaisesRegex(SystemExit, "bound to its own turn"):
                build(os.path.join(SAVED, f"CX6-{variant}.jsonl"))

    def test_the_builder_refuses_an_uncertain_or_other_model(self):
        with open(os.path.join(SAVED, "CX6-old-context-after-complete.jsonl")) as f:
            rows = [json.loads(x) for x in f]
        for r in rows:
            if r["event"] == "check":
                r["usage"]["model_evidence"] = "own-turn"
        last = max(i for i, r in enumerate(rows) if r["event"] == "check")
        rows.insert(-1, {"event": "model-scan", "final": True, "other_models": 0, "unreadable": False})
        self.assertEqual(build_in_night(rows)["model"], MODEL)  # bound evidence of the requested model: published
        for change, message in (({"model_issue": "ambiguous-model"}, "not certain"),
                                ({"model": "gpt-6-astra"}, "answered by"),
                                ({"model_evidence": None}, "bound to its own turn")):
            with self.subTest(change=change):
                changed = [dict(r, usage=dict(r["usage"], **change)) if i == last else r for i, r in enumerate(rows)]
                with self.assertRaisesRegex(SystemExit, message):
                    build_in_night(changed)
        rows[0]["model"] = "gpt-6-astra"  # a run of another model listed under this one
        with self.assertRaises(SystemExit):
            build_in_night(rows)

    def test_the_reader_s_rules(self):
        def lines(*records):
            return "".join(r + "\n" if isinstance(r, str) else json.dumps(r) + "\n" for r in records)

        def ctx(tid, m=MODEL):
            return {"type": "turn_context", "payload": {"turn_id": tid, "model": m}}
        with tempfile.TemporaryDirectory() as t:
            path = os.path.join(t, "rollout.jsonl")
            write(path, lines(ctx("p")))
            mark = C.codex_mark(path)
            self.assertEqual(mark["ids"], ["p"])
            for added, answer in (([ctx("m")], (MODEL, None, "own-turn")),
                                  ([ctx("p")], (None, "ambiguous-model", None)),
                                  ([{"type": "turn_context", "payload": {"model": MODEL}}], (None, "ambiguous-model", None)),
                                  (["not json"], (None, "ambiguous-model", None)),
                                  ([], (None, "no-model", None))):
                with self.subTest(added=added):
                    write(path, lines(ctx("p"), *added))
                    self.assertEqual(C.codex_answer(path, mark, MODEL), answer)
            write(path, "")  # the file shrank under the mark
            self.assertEqual(C.codex_answer(path, mark, MODEL)[1], "ambiguous-model")
            self.assertEqual(C.codex_answer(os.path.join(t, "other.jsonl"), mark, MODEL)[1], "ambiguous-model")


class Case2Stop(Owner):
    """2: `stop` writes the mark before any lookup, then signals the pids the lock records (since the eighth review it
    no longer waits for the launcher: the mark is the authority, and each run looks for it before every client call)."""

    def setUp(self):
        super().setUp()
        self.worker = os.path.join(self.tmp, "worker.py")
        write(self.worker, "import time\ntime.sleep(60)\n")
        self.client_home()
        night.make_night_dir(DATE)
        for p in (night.everyday_path(DATE), night.reviewed_path(DATE)):
            write(p, "fixture")
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
        for pid, _, cmd in ps_table():
            if self.worker in cmd:
                try:
                    os.killpg(pid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    pass

    def ours(self):
        """The pids of the stand-in workers of this night still alive."""
        return [pid for pid, _, cmd in ps_table() if self.worker in cmd and f"--launch-id {DATE}-" in cmd]

    def settle(self):
        for _ in range(200):
            if not self.ours():
                return []
            time.sleep(0.02)
        return self.ours()

    def test_the_review_s_race_replay(self):
        # stop-race.log: the launcher creates the lock and starts CX1 right after `stop`'s first lock lookup.
        launcher = os.path.join(self.tmp, "night.py")
        write(launcher, f"""import sys
sys.path.insert(0, {os.path.join(ROOT, 'harness')!r})
import night
night.ROOT = {self.repo!r}
night.hook_problem = lambda *a, **k: None
night.command = lambda step, date, launch_id=None, delay=None: [sys.executable, "-B", {self.worker!r}, "--label",
                                                               step["id"], "--launch-id", launch_id]
print("at-start", flush=True)
input()
def progress(line):
    if line.startswith("CX1 pid "):
        print(line, flush=True)
        input()
night.go_clients(["codex"], {DATE!r}, out=progress)
""")
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        p = subprocess.Popen([sys.executable, "-B", launcher, "--date", DATE, "--go", "codex"], env=env,
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                             start_new_session=True)
        self.procs.append(p)
        self.assertEqual(p.stdout.readline().strip(), "at-start")
        real, released = night.read_lock_any, []

        def observe(day, client):
            value = real(day, client)
            if client == "codex" and not released:
                released.append(True)
                try:
                    p.stdin.write("continue\n")
                    p.stdin.flush()
                except (BrokenPipeError, OSError):
                    return value
                p.stdout.readline()  # `CX1 pid …` (the launcher started it), or nothing (it ended)
            return value
        with mock.patch.object(night, "read_lock_any", side_effect=observe):
            signalled = night.stop("all", DATE, out=lambda *_: None)
        self.assertEqual(self.settle(), [], "a worker of the night survived a stop that returned")
        try:
            p.stdin.write("continue\n")
            p.stdin.flush()
        except (BrokenPipeError, OSError):
            pass
        p.wait(timeout=10)
        self.assertEqual(self.settle(), [])
        lock = night.read_lock(DATE, "codex") or {"runs": {}}
        self.assertEqual(sorted(signalled), sorted(info["pid"] for info in lock["runs"].values()))

    def test_stop_writes_the_mark_before_it_looks_anything_up(self):
        seen = []

        def looked(*a, **k):
            seen.append(all(os.path.lexists(night.stop_path(DATE, c)) for c in night.CLIENT_PARTS))
            return None if a else []
        with mock.patch.object(night, "read_lock_any", side_effect=looked), \
                mock.patch.object(night, "read_lock", side_effect=looked):
            night.stop("all", DATE, out=lambda *_: None)
        self.assertTrue(seen)
        self.assertTrue(all(seen), seen)

    def test_the_launcher_starts_nothing_after_the_run_it_was_starting(self):
        # The mark appears while CX1 is being started (between the look before the start and the start itself). Since
        # the eighth review the launcher sends no signal: CX1 is recorded and ends by itself on the mark, before any
        # client call (harness/probe.py, NightStop; test_eighth_review).
        sent, started = [], []

        def popen(argv, **kw):
            started.append(argv)
            C.write_private(night.stop_path(DATE, "codex"), "now\n")
            return mock.Mock(pid=987654)
        with mock.patch.object(night.os, "kill", side_effect=lambda pid, sig: sent.append((pid, sig))), \
                self.assertRaisesRegex(SystemExit, "stopped"):
            night.go_clients(["codex"], DATE, popen=popen, out=lambda *_: None)
        self.assertEqual(len(started), 1)
        self.assertEqual(sent, [])
        self.assertEqual(sorted(night.read_lock(DATE, "codex")["runs"]), ["CX1"])


class DevinStatus(unittest.TestCase):
    """Devin's status must say it is logged in; an exit code of 0 alone is never a login (owner.log:16)."""

    def test_the_review_s_status_replies(self):
        devin = C.Devin("m")
        for code, reply, ok in ((0, "", False), (0, "Not logged in", False),
                                (0, "Not logged in. Run `devin auth login`", False),
                                (0, "Logged in with an API key", False), (0, "Logged in with provided API key.", False),
                                (0, "Logged in (via WINDSURF_API_KEY)", False), (1, "Logged in", False),
                                (0, "Logged out successfully", False), (0, "Logged in", True), (0, "Logged in.", True),
                                (0, "Logged in as someone", True)):
            with self.subTest(code=code, reply=reply):
                self.assertEqual(C.login_ok(devin, code, reply, "") is None, ok)


class RunWording(unittest.TestCase):
    """The RUN document: what the Keychain report shows (not that no key was written), and Devin's session count."""

    def test_the_two_notes(self):
        with open(os.path.join(ROOT, "docs", "own-clients-RUN.md")) as f:
            text = " ".join(f.read().split())
        self.assertIn("Up to about 820 Devin sessions", text)
        self.assertIn("fewer if a control misses", text)
        self.assertNotIn("823", text)
        self.assertIn("It cannot prove that no key was written", text)
        self.assertNotIn("No key goes in the Keychain", text)
        self.assertNotIn("Nothing of the night's should appear in your Keychain", text)


if __name__ == "__main__":
    unittest.main()
