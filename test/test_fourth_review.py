"""The final check of the own-client night (at ed5e07e), and the owner's decision of 2026-11-22: the first night is
Codex CLI and Devin CLI only. Each test here fails at ed5e07e. Nothing is sent and no real client is run: stand-in
programs and stand-in workers, in temporary folders.

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
fx, write, DATE = R2.fx, R2.write, R2.DATE


class Removed(unittest.TestCase):
    """1: Claude Code and Muse Code are out of every night command; their drivers stay, tested, in clients.py."""

    def test_no_night_command_reaches_them(self):
        self.assertEqual(sorted(s["id"] for s in night.PARTS["smoke"]), ["S2", "S3", "S3b"])
        self.assertEqual(night.CLIENT_PARTS, ("codex", "devin"))
        self.assertFalse(any(s.get("harness") in ("claude", "muse") for s in night.ALL_STEPS.values()))
        for argv in (["--go", "claude"], ["--go", "muse"], ["login", "claude"], ["stop", "muse"], ["--dry-run", "claude"]):
            with self.subTest(argv=argv), self.assertRaisesRegex(SystemExit, "not in the first night"):
                night.main(["--date", DATE, *argv])
        for gone in ("KEYCHAIN", "key_reader", "claude_overage", "overage_args"):
            self.assertFalse(hasattr(night, gone), gone)
        self.assertNotIn("--allow-overage", probe.parser().format_help())
        self.assertIn("claude", C.CLIENTS)  # the driver stays
        self.assertIn("muse", C.CLIENTS)


class Point2PublicErrors(Owner):
    """2: a public result carries no client error text at all, only its kind from a closed list; the detail goes to
    the console log only, redacted whole before any clipping."""

    VALUE = "synthetic.review." + "0123456789abcdef"  # 33 characters, as the review's
    EXTERNAL = "/Volumes/FixtureOwnerDrive/PrivateCustomer/Diagnostics/muse.log"

    def run_probe(self, variant):
        self.client_home()
        out = os.path.join(self.repo, "results", variant)

        def reader(argv, **kw):
            if "--version" in argv:
                return 0, "fixture v1", ""
            if variant == "private-path":
                return 1, "", "fixture could not load " + self.EXTERNAL
            padding = (" detail" * 120)[:600 - len(self.VALUE) + 1 - len("\nexit 1")]  # the review's clipping limit
            return 1, "", "fixture key " + self.VALUE + padding
        err = io.StringIO()
        with mock.patch.dict(os.environ, {"META_API_KEY": self.VALUE}), mock.patch.object(C, "_run", side_effect=reader), \
                mock.patch.object(probe.Clock, "sleep", lambda s, n: None), redirect_stdout(io.StringIO()), \
                redirect_stderr(err):
            probe.main(["--harness", "muse", "--model", "muse-wonder-1.0", "--label", "S4", "--out", out,
                        "--replicas", "0"])
        with open(os.path.join(out, "S4.jsonl")) as f:
            return f.read(), err.getvalue()

    def assert_clean(self, text):
        for n in range(8, len(self.VALUE) + 1):  # no fragment of the key of 8 characters or more, anywhere
            for i in range(0, len(self.VALUE) - n + 1):
                self.assertNotIn(self.VALUE[i:i + n], text)
        self.assertNotIn("/Volumes/", text)
        self.assertNotIn("PrivateCustomer", text)

    def test_the_review_s_two_cases(self):
        for variant in ("key-at-limit", "private-path"):
            with self.subTest(variant=variant):
                public, console = self.run_probe(variant)
                self.assert_clean(public)
                events = [json.loads(x) for x in public.splitlines()]
                retries = [e for e in events if e["event"] == "retry"]
                self.assertEqual(len(retries), 3)
                for e in events:
                    self.assertNotIn("error", e)
                    if "error_kind" in e:
                        self.assertIn(e["error_kind"], C.ERROR_KINDS)
                self.assertEqual({e["error_kind"] for e in retries}, {"exit-nonzero"})
                for n in range(8, len(self.VALUE) + 1):  # the console's detail: redacted whole, then clipped
                    for i in range(0, len(self.VALUE) - n + 1):
                        self.assertNotIn(self.VALUE[i:i + n], console)
                self.assertIn("detail:", console)

    def test_a_version_diagnostic_at_the_clipping_limit(self):
        env = {"META_API_KEY": self.VALUE}
        tail = "x" * (300 - len(self.VALUE) + 1)

        def run(argv, **kw):
            return 1, "", "fixture " + self.VALUE + tail
        with self.assertRaises(C.ClientError) as e:
            C.Muse("m").version(env, run=run)
        self.assert_clean(str(e.exception))
        self.assertEqual(e.exception.kind, "exit-nonzero")


class Point5Stop(Owner):
    """3 (the review's 5): the launcher's pid is in the lock before any worker; it looks for the stop mark before
    each start; `stop all` writes the mark, signals the launcher, then the workers."""

    def setUp(self):
        super().setUp()
        self.worker = os.path.join(self.tmp, "worker.py")
        write(self.worker, "import time\ntime.sleep(60)\n")
        self.client_home()
        night.make_night_dir(DATE)
        for p in (night.everyday_path(DATE), night.reviewed_path(DATE)):
            write(p, "fixture")
        self.addCleanup(self.cleanup)

    def cleanup(self):
        for d, dirs, files in os.walk(os.path.join(night.night_dir(DATE), "launch")):
            for name in files:
                if name.endswith(".json"):
                    try:
                        lock = json.load(open(os.path.join(d, name)))
                    except ValueError:
                        continue
                    for info in lock.get("runs", {}).values():
                        try:
                            os.killpg(info["pid"], signal.SIGKILL)
                        except (ProcessLookupError, PermissionError):
                            pass

    def command(self, step, date, launch_id=None, delay=None):
        return [sys.executable, "-B", self.worker, "--label", step["id"], "--launch-id", launch_id]

    def gone(self, pid):
        for _ in range(200):
            if not night.process_command(pid):
                return True
            time.sleep(0.02)
        return False

    def test_the_launcher_s_pid_is_in_the_lock_before_any_worker(self):
        seen = []

        def popen(argv, **kw):
            seen.append(night.read_lock(DATE, "codex").get("launcher_pid"))
            return mock.Mock(pid=7000 + len(seen))
        night.go_clients(["codex"], DATE, popen=popen, out=lambda *_: None)
        self.assertEqual(seen[0], os.getpid())

    def test_the_review_s_active_launch_case(self):
        # `stop all` while the launcher is still starting (right after CX1): no further worker starts.
        started = []

        def popen(argv, **kw):
            p = subprocess.Popen(argv[2:] if argv[0] == "caffeinate" else argv, **kw)
            started.append(p)
            return p

        def out(line):
            if line.startswith("CX1 pid "):
                self.signalled = night.stop("all", DATE, out=lambda *_: None)
        with mock.patch.object(night, "command", self.command), \
                self.assertRaisesRegex(SystemExit, "stopped .* after 1 of 6 runs"):
            night.go_clients(["codex"], DATE, popen=popen, out=out)
        self.assertEqual(len(started), 1)
        self.assertEqual(self.signalled, [started[0].pid])
        started[0].wait(timeout=10)
        self.assertEqual(sorted(night.read_lock(DATE, "codex")["runs"]), ["CX1"])
        with self.assertRaisesRegex(SystemExit, "stopped"):
            night.go_clients(["devin"], DATE, popen=popen, out=lambda *_: None)  # stop all: devin too
        self.assertEqual(len(started), 1)

    def test_stop_from_another_process_ends_the_launcher_first(self):
        # A launcher in its own process, slow between starts; `stop all` from here: it ends, and no worker is left.
        script = os.path.join(self.tmp, "launcher.py")
        write(script, f"""import sys, time
sys.path.insert(0, {os.path.join(ROOT, 'harness')!r})
import night
night.ROOT = {self.repo!r}
night.command = lambda step, date, launch_id=None, delay=None: [sys.executable, "-B", {self.worker!r}, "--label",
                                                               step["id"], "--launch-id", launch_id]
def out(line):
    print(line, flush=True)
    time.sleep(1.0)
night.go_clients(["codex"], {DATE!r}, out=out)
""")
        # Its command line must look like the night's launcher: harness/night.py ... --date <date> ... --go
        shim = os.path.join(self.tmp, "night.py")
        write(shim, open(script).read())
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        p = subprocess.Popen([sys.executable, shim, "--date", DATE, "--go", "codex"], env=env, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True, start_new_session=True)
        try:
            self.assertTrue(p.stdout.readline().startswith("CX1 pid "))
            lock = night.read_lock(DATE, "codex")
            self.assertEqual(lock["launcher_pid"], p.pid)
            signalled = night.stop("all", DATE, out=lambda *_: None)
            # Since the fifth review `stop` waits for the launcher, which ends by itself on the stop mark (exit 1);
            # one that does not is signalled.
            self.assertIn(p.wait(timeout=10), (1, -signal.SIGTERM))
            lock = night.read_lock(DATE, "codex")
            self.assertEqual(sorted(signalled), sorted(info["pid"] for info in lock["runs"].values()))
            for info in lock["runs"].values():
                self.assertTrue(self.gone(info["pid"]))
            self.assertEqual(night.status(DATE, out=lambda *_: None), {"ended": len(lock["runs"])})
            self.assertLess(len(lock["runs"]), 6)
        finally:
            if p.poll() is None:
                p.kill()


class Point6Model(Owner):
    """4 (the review's 6): a check without its own model evidence is invalid in the probe and never emitted by the
    builder; no model is carried from one turn to the next. The review's two end-to-end cases."""

    def run_case(self, variant):
        base = self.client_home()
        state = os.path.join(base, "codex-cli")
        model = "gpt-6-luna"
        clock = FakeClock()
        sessions = {}

        def append(sid, events):
            path = os.path.join(state, "sessions", "2099", "01", "01", f"rollout-2099-01-01T00-00-00-{sid}.jsonl")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "a") as f:
                f.write("".join(json.dumps(e) + "\n" for e in events))

        def ev(kind, turn, **kv):
            return {"type": "event_msg", "payload": dict(type=kind, turn_id=turn, **kv)}

        def standin(argv, env, cwd, stdin, timeout):
            if "--version" in argv:
                return 0, "fixture version 1", ""
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
            timed = s["n"] >= 2 and not new
            changed = timed and age == 150  # at 150 s Astra answers
            turn = str(uuid.uuid4())
            if changed and variant == "complete-only":
                roll = [ev("task_complete", turn)]
            elif changed and variant == "no-model":
                roll = [ev("task_started", turn), ev("task_complete", turn)]
            else:
                roll = [ev("task_started", turn), {"type": "turn_context", "payload": {"turn_id": turn, "model": model}},
                        ev("task_complete", turn)]
            append(sid, roll)
            total = (18000 if s["n"] == 0 else 25000) if new else 50020
            cached = 0 if new and s["n"] == 0 else (18000 if new else 43000)
            events = [{"type": "thread.started", "thread_id": sid}, {"type": "turn.started"},
                      {"type": "item.completed", "item": {"type": "agent_message", "id": "m", "text": "OK"}},
                      {"type": "turn.completed", "usage": {"input_tokens": total, "cached_input_tokens": cached,
                                                           "cache_write_input_tokens": total - cached, "output_tokens": 5}}]
            return 0, "".join(json.dumps(x) + "\n" for x in events), ""
        out = os.path.join(self.repo, "results", variant)
        with mock.patch.object(C, "_run", side_effect=standin), mock.patch.object(probe, "Clock", return_value=clock), \
                redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            probe.main(["--harness", "codex", "--model", model, "--label", "CX6", "--ages", "2.5m", "--words", "20",
                        "--replicas", "1", "--out", out])
        path = os.path.join(out, "CX6.jsonl")
        events = [json.loads(x) for x in open(path)]
        return path, events

    def test_the_review_s_two_cases(self):
        for variant in ("no-model", "complete-only"):
            with self.subTest(variant=variant):
                path, events = self.run_case(variant)
                row = next(e for e in events if e["event"] in ("check", "check-invalid") and e["age"] == "2.5m")
                self.assertEqual((row["event"], row.get("reason")), ("check-invalid", "no-model"))
                self.assertIsNone(row["usage"].get("model"))
                with self.assertRaises(SystemExit):
                    B.build_cache({"runs": [{"id": "CX6", "route": "codex-subscription", "file": path,
                                             "model": "gpt-6-luna"}]})

    def test_a_check_without_model_evidence_is_never_published(self):
        start = {"event": "start", "harness": "codex", "client_version": "f", "isolation": probe.ISOLATION,
                 "model": "gpt-6-luna", "at": "2026-11-23T20:00:00Z"}
        u = {"total": 50020, "cached": 43000, "calls": 1}
        rows = [start, {"event": "check", "age": "control", "warm": True, "late": False, "usage": dict(u, model="gpt-6-luna")},
                {"event": "check", "age": "2.5m", "warm": True, "late": False, "usage": u}, {"event": "done"}]
        with tempfile.TemporaryDirectory() as t:
            path = os.path.join(t, "CX6.jsonl")
            write(path, "".join(json.dumps(x) + "\n" for x in rows))
            with self.assertRaisesRegex(SystemExit, "no model evidence"):
                B.build_cache({"runs": [{"id": "CX6", "route": "codex-subscription", "file": path, "model": "gpt-6-luna"}]})


class Point5RunDocument(unittest.TestCase):
    """5: the owner's part is step 1, two logins (Codex, Devin), no Muse key, the report."""

    def test_the_owner_part(self):
        with open(os.path.join(ROOT, "docs", "own-clients-RUN.md")) as f:
            text = f.read()
        owner = text.split("## The night", 1)[0]
        self.assertTrue("login codex" in owner and "login devin" in owner)
        self.assertFalse("login claude" in owner or "META_API_KEY" in owner or "security add-generic-password" in owner)
        self.assertTrue("**2. The two logins**" in owner)
        self.assertTrue("Up to about 820 Devin sessions" in owner)  # the fifth review's wording


if __name__ == "__main__":
    unittest.main()
