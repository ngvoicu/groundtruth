#!/usr/bin/env python3
"""Cache-lifetime probe through real coding harnesses (Claude Code, Codex CLI, Devin CLI, Muse Code, pi).

The clients themselves (how each is driven and how its output is read) are in harness/clients.py.

Each sample starts a new harness session whose first message carries a unique block of ~N tokens, then, after a fixed
age, resumes that session with a short message and reads the cached-token count the harness reports. Harnesses share a
large system prompt between sessions, so a check is warm only when the cache covers the shared part *and* at least half
of the sample's unique block: cached >= baseline + unique / 2, where baseline is the prompt size of a session without
the block (measured once at start). One check per sample, like the TypeScript probe in src/.

Four rules for every client (docs/own-clients.md, section 1):
1. One model request per check. A check whose turn was not one model request (a tool call, then the answer) is
   logged as `check-invalid` and left out: the second request would read what the first one wrote.
2. A check is never sent twice. A check that fails is logged as `check-failed` and its sample is lost. A priming may
   be tried again (3 tries, 30 seconds apart).
3. The control comes first: it is primed, checked at 30 seconds, and only then are the others primed. A control that
   misses ends the run (`stop`, `no-observable-cache`) after three requests.
4. A quota refusal ends the run (`stop`, `quota`), never retried; the samples already primed are not checked.
Also: ages count from the start of the priming request; a check more than age x 1.1 + 90 s after it is `late`; a run
whose replies change the lifetime they write (Claude Code in overage) ends (`stop`, `tier-changed`).

Usage:
  harness/probe.py --harness claude|codex|devin|muse|pi --model ID [--schedule std|long | --ages 30m,1h] --replicas 3 \
      --label H1 --out DIR [--filler random|list] [--dry-run]
"""
import argparse, heapq, json, os, random, shutil, sys, tempfile, time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import clients as C  # noqa: E402

OK_PROMPT = C.OK_PROMPT


# Where every evaluation starts: the control (sent again at once) is always made, then these ages, whatever else
# is asked for. The same lists as src/schedule.ts (test/schedule.test.ts checks it).
LADDER_START = ["2.5m", "5m", "7.5m"]
STD_REST = ["10m", "15m", "20m", "25m", "30m", "40m", "50m", "60m", "75m", "90m", "120m"]
LONG_REST = ["4h", "8h", "12h"]
SCHEDULES = {"std": LADDER_START + STD_REST, "long": LADDER_START + STD_REST + LONG_REST}
CONTROL_AGE = 30.0
PRIME_TRIES, RETRY_WAIT = 3, 30


def parse_age(s):
    s = s.strip()
    if s.endswith("h"): return float(s[:-1]) * 3600
    if s.endswith("m"): return float(s[:-1]) * 60
    if s.endswith("s"): return float(s[:-1])
    return float(s)


def ages_of(schedule, extra):
    """Custom ages are added to the start of the ladder, never put in its place; each age once, shortest first."""
    wanted = LADDER_START + [x.strip() for x in extra.split(",")] if extra else SCHEDULES[schedule]
    by_age = {}
    for x in wanted:
        by_age.setdefault(parse_age(x), x)
    ages = sorted(by_age)
    return ages, [by_age[x] for x in ages]


def unique_block(salt, words):
    rnd = random.Random(salt)
    cons, vows = "bcdfghjklmnprstvz", "aeiou"
    out = []
    for _ in range(words):
        out.append("".join(rnd.choice(cons) + rnd.choice(vows) for _ in range(rnd.randint(2, 4))))
    return " ".join(out)


def list_block(salt, words):
    """Plain numbered lines, every one naming the sample (for a model that refuses the random filler)."""
    return "\n".join(f"{i}. Entry {i} of list {salt}: item {salt}-{i}." for i in range(1, max(words // 6, 1) + 1))


FILLERS = {"random": unique_block, "list": list_block}


# The first line of every new session names the measurement, so that a vendor that lists sessions in the account
# (Devin) shows them as groundtruth's, not as the owner's work.
FIRST_LINE = "groundtruth cache measurement {salt} (an automated test, not a task)."


def baseline_prompt(salt):
    return FIRST_LINE.format(salt=salt) + "\n" + OK_PROMPT


def prime_prompt(salt, words, filler="random"):
    return (FIRST_LINE.format(salt=salt) + f"\nReference document {salt}, keep it for later. Do not use any tools. "
            "Reply with OK only.\n\n<doc>\n" + FILLERS[filler](salt, words) + "\n</doc>")


class Clock:
    def now(self):
        return time.time()

    def sleep(self, seconds):
        if seconds > 0:
            time.sleep(seconds)


class Stop(Exception):
    def __init__(self, reason, text=None):
        super().__init__(reason)
        self.reason, self.text = reason, text


def written_ttl(usage):
    """The lifetime a reply's cache write had, where the client says (Claude Code): 1h, 5m, mixed, or None."""
    h1, m5 = usage.get("write_1h") or 0, usage.get("write_5m") or 0
    if h1 and m5:
        return "mixed"
    return "1h" if h1 else "5m" if m5 else None


WAVES, WAVE_GAP = 3, 300.0


def run_probe(h, *, ages, labels, replicas, words, salt, log, clock=None, filler="random", cumulative=None,
              waves=WAVES, wave_gap=WAVE_GAP):
    """The loop. `h` has start(prompt) -> (handle, usage dict) and resume(handle, prompt) -> usage dict and raises
    clients.Refused / another exception; `log` takes one event; `clock` has now() and sleep(). Returns the stop reason
    or None."""
    clock = clock or Clock()
    cumulative = getattr(h, "cumulative", False) if cumulative is None else cumulative
    seen_ttl = [None]

    def watch(usage):
        t = written_ttl(usage)
        if t == "mixed" or (t and seen_ttl[0] and t != seen_ttl[0]):
            raise Stop("tier-changed", f"a reply wrote {t} after {seen_ttl[0]}")
        seen_ttl[0] = seen_ttl[0] or t

    def prime(prompt, name, rep):
        """(handle, usage, start time) or None. Tried again on an error, never on a refusal."""
        for i in range(PRIME_TRIES):
            t0 = clock.now()
            try:
                handle, usage = h.start(prompt)
            except C.Refused as e:
                if e.kind == "quota":
                    raise Stop("quota", e.text[:300])
                log({"event": "prime-refused", "age": name, "kind": e.kind, "error": e.text[:300]})
                return None
            except Exception as e:  # noqa: BLE001 - any client failure: try the priming again
                log({"event": "retry", "age": name, "error": str(e)[:300], "try": i + 1})
                clock.sleep(RETRY_WAIT)
                continue
            watch(usage)
            return handle, usage, t0
        log({"event": "prime-failed", "age": name})
        return None

    def check(name, age, handle, primed, t0, baseline):
        """True / False for a counted check, None for one that is not (failed, invalid). Sent once."""
        started = clock.now()
        real = started - t0
        base = {"age": name, "ageSec": age, "realAgeSec": round(real), "handle": handle}
        try:
            r = h.resume(handle, OK_PROMPT)
        except C.Refused as e:
            if e.kind == "quota":
                raise Stop("quota", e.text[:300])
            log({"event": "check-failed", **base, "kind": e.kind, "error": e.text[:300]})
            return None
        except Exception as e:  # noqa: BLE001 - a failed check is never sent again
            log({"event": "check-failed", **base, "error": str(e)[:300]})
            return None
        if cumulative:
            r = dict(r, raw={k: r.get(k) for k in ("total", "cached", "write")},
                     **{k: (r.get(k) or 0) - (primed.get(k) or 0) for k in ("total", "cached", "write")})
        if r.get("calls") != 1:
            log({"event": "check-invalid", **base, "reason": f"the turn made {r.get('calls')} model requests, not 1",
                 "usage": r, "prime": primed})
            watch(r)
            return None
        watch(r)
        unique = max(primed["total"] - baseline, 1)
        warm = r["cached"] >= baseline + unique / 2
        log({"event": "check", **base, "late": real > age * 1.1 + 90, "warm": warm, "usage": r, "prime": primed,
             "unique": unique})
        return warm

    try:
        b = prime(baseline_prompt(salt), "baseline", 0)
        if not b:
            raise Stop("baseline-failed")
        baseline = b[1]["total"]
        log({"event": "baseline", "usage": b[1]})

        # The control first: primed, checked at 30 seconds, and only then the others.
        c = prime(prime_prompt(f"{salt}-0", words, filler), "control", 0)
        if not c:
            raise Stop("control-failed")
        handle, primed, t0 = c
        log({"event": "prime", "age": "control", "rep": 0, "handle": handle, "usage": primed})
        clock.sleep(t0 + CONTROL_AGE - clock.now())
        warm = check("control", CONTROL_AGE, handle, primed, t0, baseline)
        if warm is None:
            raise Stop("control-failed")
        if not warm:
            raise Stop("no-observable-cache")

        # The samples of one age are primed in waves (replica r in wave r mod `waves`), a wave starting at least
        # `wave_gap` seconds after the one before, so the checks of an age fall at different moments (M-3 of the
        # parity design). Within a wave, long ages first, so the short checks do not wait behind a long queue of
        # primings; a check that falls due is made before the next priming.
        waves = max(1, min(waves, replicas or 1))
        samples = sorted([(x, ag, r, r % waves) for r in range(replicas) for x, ag in zip(labels, ages)],
                         key=lambda s: (s[3], -s[1]))
        queue, due, n, wave_start = list(samples), [], 0, {}
        while queue or due:
            now = clock.now()
            if due and due[0][0] <= now:
                _, _, name, age, handle, primed, t0 = heapq.heappop(due)
                check(name, age, handle, primed, t0, baseline)
                continue
            if queue:
                name, age, rep, wave = queue[0]
                ready = wave_start[wave - 1] + wave_gap if wave and wave - 1 in wave_start else None
                if ready is not None and now < ready:
                    clock.sleep(min(ready, due[0][0]) - now if due else ready - now)
                    continue
                queue.pop(0)
                n += 1
                p = prime(prime_prompt(f"{salt}-{n}", words, filler), name, rep)
                if p:
                    handle, primed, t0 = p
                    wave_start.setdefault(wave, t0)
                    log({"event": "prime", "age": name, "rep": rep, "wave": wave, "handle": handle, "usage": primed})
                    heapq.heappush(due, (t0 + age, n, name, age, handle, primed, t0))
                else:
                    wave_start.setdefault(wave, clock.now())
            else:
                clock.sleep(due[0][0] - now)
    except Stop as s:
        log({"event": "stop", "reason": s.reason, **({"error": s.text} if s.text else {})})
        return s.reason
    log({"event": "done"})
    return None


class Harness:
    """start/resume as run_probe calls them, over a client of harness/clients.py."""

    def __init__(s, session):
        s.session, s.cumulative = session, session.client.cumulative

    def start(s, prompt):
        handle, u = s.session.start(prompt)
        return handle, u.record()

    def resume(s, handle, prompt):
        return s.session.resume(handle, prompt).record()


HARNESSES = C.CLIENTS


def parser():
    ap = argparse.ArgumentParser()
    ap.add_argument("--harness", required=True, choices=HARNESSES)
    ap.add_argument("--model", required=True)
    ap.add_argument("--schedule", choices=sorted(SCHEDULES), default="std", help="std: 2.5m to 2h; long: std + 4h, 8h, 12h")
    ap.add_argument("--ages", help="more ages instead of --schedule, e.g. 30m,1h; 2.5m, 5m and 7.5m are always added")
    ap.add_argument("--replicas", type=int, default=3)
    ap.add_argument("--label", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--words", type=int, default=3000, help="unique block size in words (~2 tokens each)")
    ap.add_argument("--filler", choices=sorted(FILLERS), default="random", help="random syllables, or plain numbered lines")
    ap.add_argument("--effort", default="low")
    ap.add_argument("--client-home", default=os.environ.get("GROUNDTRUTH_CLIENT_HOME"),
                    help="the folder of the clients' state folders (<client-home>/<client id>, logged in once by the owner); "
                         "default: GROUNDTRUTH_CLIENT_HOME. Required for an own client")
    ap.add_argument("--client-env", action="append", default=[], metavar="KEY=VALUE",
                    help="a setting the run makes for the client (Claude Code: CLAUDE_CODE_PROMPT_CACHE_TTL=5m); recorded")
    ap.add_argument("--waves", type=int, default=WAVES,
                    help=f"prime an age's samples in this many waves (default {WAVES}; M-3 of the parity design)")
    ap.add_argument("--wave-gap", type=float, default=WAVE_GAP, help=f"seconds between two waves (default {WAVE_GAP:g})")
    ap.add_argument("--devin-daemon", action="store_true",
                    help="Devin only (pair DV-5): leave the process model and the cache keepalive as the client has them")
    ap.add_argument("--keep-raw", metavar="DIR",
                    help="keep every invocation's output, redacted, in DIR (outside the repository): for the smoke runs, "
                         "to correct the fixtures")
    ap.add_argument("--dry-run", action="store_true", help="print the run's start event and plan; run nothing, send nothing")
    return ap


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ISOLATION = {"home": "dedicated", "work": "temporary"}


def settings_of(pairs):
    out = {}
    for p in pairs:
        if "=" not in p:
            raise SystemExit(f"--client-env {p}: KEY=VALUE")
        k, v = p.split("=", 1)
        out[k] = v
    return out


def main(argv=None):
    a = parser().parse_args(argv)
    ages, labels = ages_of(a.schedule, a.ages)
    settings = settings_of(a.client_env)
    client = HARNESSES[a.harness](a.model, a.effort, settings=settings)
    if a.devin_daemon:
        if a.harness != "devin":
            raise SystemExit("--devin-daemon is for the Devin CLI only")
        client.daemon = True
    salt = os.urandom(4).hex()
    start = {"event": "start", "harness": a.harness, "client": client.client_id, "model": a.model,
             "ages": ",".join(labels), "replicas": a.replicas, "words": a.words, "filler": a.filler, "effort": client.effective_effort(),
             "salt": salt}
    if settings:
        start["client_env"] = settings
    fixed = client.run_vars()
    if fixed:
        start["client_settings"] = fixed  # what the run sets for every invocation (no secret, no path)
    if client.retries_note:
        start["retries"] = client.retries_note
    if client.isolated:
        start["isolation"] = dict(ISOLATION)
    start["waves"] = {"waves": max(1, min(a.waves, a.replicas or 1)), "gap_s": a.wave_gap}
    if client.run_info():
        start[a.harness] = client.run_info()
    if a.dry_run:
        plan = C.Session(client, env=None, io="<io>", work="<work>", create=False)
        start.update(command={"prime": plan.plan(), "check": plan.plan(resume="<session>")})
        env = client.environment("<client-home>/" + (getattr(client, "state_name", None) or client.client_id), base={k: "<" + k + ">" for k in C.ALLOW})
        requests = 3 + 2 * a.replicas * len(ages)
        print(json.dumps(start))
        print(f"{a.label}: {a.harness} {a.model}: baseline, control (checked at 30 s), then {a.replicas} x "
              f"{len(ages)} samples ({', '.join(labels)}): at most {requests} requests.")
        if client.isolated:
            print(f"{a.label}: environment {json.dumps(env)}; working folder: a new empty folder under the system's "
                  "temporary folder. Dry run: nothing run, nothing sent.")
        else:
            print(f"{a.label}: the caller's environment (a proxy client). Dry run: nothing run, nothing sent.")
        return
    keep = os.path.abspath(a.keep_raw) if a.keep_raw else None
    if keep and (keep + os.sep).startswith(os.path.realpath(ROOT) + os.sep):
        raise SystemExit("--keep-raw: a folder outside the repository (the raw output is never published)")
    home = None
    if client.isolated:
        home = C.state_folder(client, a.client_home, ROOT)
        env = client.environment(home)
        import scan_secrets
        for k in client.passthrough:  # a value only the child knows: its fingerprint, for the scan at commit time
            scan_secrets.remember(env.get(k), k)
    else:
        env = None
    # A new empty working folder outside every repository (a client reads CLAUDE.md / AGENTS.md from the folders above
    # it), kept until the last check: a session is resumed from the folder it was started in.
    tmp = tempfile.mkdtemp(prefix=f"groundtruth-{a.label}-")
    try:
        # The working folder must be outside every checkout (a client reads CLAUDE.md / AGENTS.md above it), whatever
        # TMPDIR says.
        C.check_folder("the working folder (TMPDIR)", tmp, ROOT, os.path.realpath(os.path.expanduser("~")))
        if env is not None:
            os.makedirs(os.path.join(tmp, "tmp"))
            env["TMPDIR"] = os.path.join(tmp, "tmp")
        session = C.Session(client, env=env, io=os.path.join(tmp, "io"), work=os.path.join(tmp, "work"),
                            home=home, keep=keep)
        if a.harness == "pi":
            start["pi"] = client.describe(home, env)
        start.update(client_version=client.version(env),
                     command={"prime": session.plan(), "check": session.plan(resume="<session>")})
        os.makedirs(a.out, exist_ok=True)
        path = os.path.join(a.out, f"{a.label}.jsonl")

        def log(ev):
            ev["at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            with open(path, "a") as f:
                f.write(json.dumps(ev) + "\n")
            print(json.dumps(ev), flush=True)

        log(start)
        run_probe(Harness(session), ages=ages, labels=labels, replicas=a.replicas, words=a.words, salt=salt, log=log,
                  filler=a.filler, waves=a.waves, wave_gap=a.wave_gap)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
