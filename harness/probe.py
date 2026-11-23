#!/usr/bin/env python3
"""Cache-lifetime probe through real coding harnesses (Claude Code, Codex CLI, Devin CLI, Muse Code).

The clients themselves (how each is driven and how its output is read) are in harness/clients.py.

Each sample starts a new harness session whose first message carries a unique block of ~N tokens, then, after a fixed
age, resumes that session with a short message and reads the cached-token count the harness reports. Harnesses share a
large system prompt between sessions, so a check is warm only when the cache covers the shared part *and* at least half
of the sample's unique block: cached >= baseline + unique / 2, where baseline is the prompt size of a session without
the block (measured once at start). One check per sample, like the TypeScript probe in src/.

Five rules for every client (docs/own-clients.md, section 1):
1. One model request per check. A check whose turn was not one model request (a tool call, then the answer) is
   logged as `check-invalid` and left out: the second request would read what the first one wrote.
2. A check is never sent twice. A check that fails is logged as `check-failed` and its sample is lost. A priming may
   be tried again (3 tries, 30 seconds apart).
3. The control comes first: it is primed, checked at 30 seconds, and only then are the others primed. A control that
   misses gets one more control, in a fresh session (another unique block); the run ends (`stop`,
   `no-observable-cache`) only when both miss, after five requests, and both are recorded. A control checked late
   (more than 30 x 1.1 + 90 s after its priming) ends the run (`stop`, `control-late`): a late control shows nothing.
4. A quota refusal (a plan's limit) ends the run (`stop`, `quota`), never retried; the samples already primed are not
   checked. A rate limit that says when it resets (`rate-limited`, clients.classify) is no quota: the request waits
   for the reset plus a few random seconds and is sent again (a `rate-wait` event per wait), at most 5 tries for one
   request and 10 minutes of such waits for one sample; then the request is lost as any refused one (a priming
   `prime-refused`, a check `check-failed`, both of kind `rate-limited`). The vendor refused it before any model
   read it, so a check sent again after it reads no write of its own; one that the waits made late is `late`.
5. A client with a request budget (harness/pacing.py, --pace-rpm) asks the budget, shared by every run of the
   client that night, before each request.
Also: ages count from the start of the priming request; a check more than age x 1.1 + 90 s after it is `late`; a run
whose replies change the lifetime they write (Claude Code in overage) ends (`stop`, `tier-changed`).

Usage:
  harness/probe.py --harness claude|codex|devin|muse --model ID [--schedule std|long | --ages 30m,1h] --replicas 3 \
      --label H1 --out DIR [--filler random|list] [--dry-run]
"""
import argparse, heapq, json, os, random, re, shutil, sys, tempfile, time
sys.dont_write_bytecode = True  # a dry run writes nothing, not even the interpreter's cache
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import clients as C  # noqa: E402
import pacing  # noqa: E402

OK_PROMPT = C.OK_PROMPT


# Where every evaluation starts: the control (sent again at once) is always made, then these ages, whatever else
# is asked for. The same lists as src/schedule.ts (test/schedule.test.ts checks it).
LADDER_START = ["2.5m", "5m", "7.5m"]
STD_REST = ["10m", "15m", "20m", "25m", "30m", "40m", "50m", "60m", "75m", "90m", "120m"]
LONG_REST = ["4h", "8h", "12h"]
SCHEDULES = {"std": LADDER_START + STD_REST, "long": LADDER_START + STD_REST + LONG_REST}
CONTROL_AGE = 30.0
PRIME_TRIES, RETRY_WAIT = 3, 30
# A rate limit that says when it resets (rule 4): tries of one request, seconds of waits for one sample, and the random
# seconds added to each wait (so that the runs of a night do not all come back at the reset's second).
RATE_TRIES, RATE_WAIT_MAX, RATE_JITTER = 5, 600.0, (1.0, 5.0)
CONTROLS = 2  # rule 3: a cold control gets one more, in a fresh session


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


# --- the public record: every line of results/<folder>/<id>.jsonl is written by Public.line, and only so ------------

# What a public line may hold: these keys only, each a number, a boolean, or a string of a fixed set (an event name, a
# reason, an error kind) or of the run's own plan (an age label). Anything else, and every string a client or vendor
# reported, never reaches the public file: it goes to the run's console log (private, mode 600), for the audit.
NUMBER, BOOL, AGE = "number", "bool", "age"
EVENTS = ("start", "baseline", "prime", "check", "check-invalid", "check-failed", "retry", "rate-wait", "prime-refused",
          "prime-failed", "model-scan", "stop", "done")
STOP_REASONS = ("baseline-failed", "control-failed", "control-late", "no-observable-cache", "quota", "tier-changed",
                "other-model", "unreadable-session")
REASONS = tuple(dict.fromkeys(STOP_REASONS + C.MODEL_ISSUES + ("not-one-call",)))
# A reply's usage. The model a client or vendor reported is never kept as text: Public.line turns it into
# `model_matches` (whether it is the run's requested model: clients.same_model).
USAGE = {"total": NUMBER, "cached": NUMBER, "write": NUMBER, "calls": NUMBER, "write_5m": NUMBER, "write_1h": NUMBER,
         "model_matches": BOOL, "model_issue": C.MODEL_ISSUES, "model_evidence": ("own-turn",),
         "raw": {"total": NUMBER, "cached": NUMBER, "write": NUMBER}}
FIELDS = {"event": EVENTS, "age": AGE, "ageSec": NUMBER, "realAgeSec": NUMBER, "rep": NUMBER, "wave": NUMBER,
          "try": NUMBER, "waitSec": NUMBER, "unique": NUMBER, "session": NUMBER, "late": BOOL, "warm": BOOL, "final": BOOL,
          "unreadable": BOOL, "other_models": NUMBER, "reason": REASONS, "kind": C.ERROR_KINDS,
          "error_kind": C.ERROR_KINDS, "usage": USAGE, "prime": USAGE}


class Public:
    """The writer of a run's public record. `plan` is the run's start record, built from its arguments and the code
    before any client is invoked; it is frozen here and is the only `start` line ever written (whatever the caller
    passes with it). Every other event is passed through FIELDS: a key not listed, a value of another type, a string
    outside its fixed set, and the client-reported model (made `model_matches`) are left out of the line and told to
    `private` (the console log). `scrub` is a last redaction of the whole line."""

    def __init__(self, path, plan, private=None, scrub=None, now=None):
        self.path, self.plan = path, json.loads(json.dumps(plan))
        self.ages = {"baseline", "control", *str(plan.get("ages", "")).split(",")}
        self.private = private or (lambda text: None)
        self.scrub = scrub or (lambda text: text)
        self.now = now or (lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))

    def keep(self, spec, value):
        if spec == NUMBER:
            return type(value) in (int, float)
        if spec == BOOL:
            return type(value) is bool
        if spec == AGE:
            return type(value) is str and value in self.ages
        return isinstance(spec, tuple) and type(value) is str and value in spec

    def clean(self, ev, schema, where):
        out = {}
        for k, v in ev.items():
            spec = schema.get(k)
            if schema is USAGE and k == "model":
                out["model_matches"] = type(v) is str and C.same_model(v, self.plan["model"],
                                                                        exact=self.plan["harness"] == "codex")
                if not out["model_matches"]:
                    self.private(f"{where}: the model the client reported, kept private: {v!r}")
            elif isinstance(spec, dict) and isinstance(v, dict):
                out[k] = self.clean(v, spec, f"{where}.{k}")
            elif spec is not None and self.keep(spec, v):
                out[k] = v
            else:
                self.private(f"{where}: {k} kept private: {v!r}")
        return out

    def line(self, ev):
        """Writes one public line (appended to `path`), and returns it."""
        if ev.get("event") == "start":
            rec = dict(self.plan)
        else:
            rec = self.clean(ev, FIELDS, str(ev.get("event")))
            if "event" not in rec:
                return None  # not an event of this record: told to `private`, nothing written
        rec["at"] = self.now()
        text = self.scrub(json.dumps(rec))
        with open(self.path, "a") as f:
            f.write(text + "\n")
        return text


def late_after(age):
    """A check made more than this many seconds after its priming started is `late`."""
    return age * 1.1 + 90


def run_probe(h, *, ages, labels, replicas, words, salt, log, clock=None, filler="random", cumulative=None,
              waves=WAVES, wave_gap=WAVE_GAP, detail=None, pace=None, rng=None):
    """The loop. `h` has start(prompt) -> (handle, usage dict) and resume(handle, prompt) -> usage dict and raises
    clients.Refused / another exception; `log` takes one event (public); `detail` takes a failure's text (the console
    log only: a public event carries only its kind, one of clients.ERROR_KINDS); `clock` has now() and sleep();
    `pace(kind, until=None)`, when given, returns True once a request of kind "prime" or "check" may go, or False when
    `until` comes first (harness/pacing.py Pacer.acquire); `rng` draws the jitter of rate-limit waits. Returns the
    stop reason or None."""
    clock = clock or Clock()
    detail = detail or (lambda text: None)
    rng = rng or random.Random()
    waited = {}  # (age label, replica) -> seconds this sample waited on rate limits (rule 4)
    sessions = []  # every session the run started (baseline, control, samples): read whole by the model scans
    cumulative = getattr(h, "cumulative", False) if cumulative is None else cumulative
    seen_ttl = [None]

    def number(handle):
        """The session's number in this run (1: the baseline): what a public line names it by. The client's own id
        for it goes to the console log (detail) only, once, for the audit."""
        if handle not in sessions:
            sessions.append(handle)
            detail(f"session {len(sessions)}: {handle}")
        return sessions.index(handle) + 1

    def failed(where, e):
        kind = C.error_kind(e)
        detail(f"{where}: {kind}: {type(e).__name__}: {e}")
        return kind

    def watch(usage):
        t = written_ttl(usage)
        if t == "mixed" or (t and seen_ttl[0] and t != seen_ttl[0]):
            raise Stop("tier-changed", f"a reply wrote {t} after {seen_ttl[0]}")
        seen_ttl[0] = seen_ttl[0] or t

    def send(call, kind, name, rep, latest=None, paced=False):
        """(what `call()` returned, the moment the request that answered went out). The budget first (`pace`). A
        `rate-limited` refusal waits for the reset the vendor named plus RATE_JITTER seconds, as a `rate-wait` event,
        and the request goes again: at most RATE_TRIES tries, and RATE_WAIT_MAX seconds of such waits for the sample
        (`name`, `rep`); past either, the refusal is raised as it came. `latest`: the control's last moment; a control
        that the budget or a wait would send later ends the run (`control-late`). `paced`: the first try's turn is
        taken already (the sample loop takes it, so that waiting for it never holds a check that falls due)."""
        for i in range(1, RATE_TRIES + 1):
            if pace and not (paced and i == 1):
                pace(kind)
            if latest is not None and clock.now() > latest:
                raise Stop("control-late", "the control's check could not go in time (rate limit or budget)")
            t = clock.now()
            try:
                return call(), t
            except C.Refused as e:
                if e.kind != "rate-limited" or i == RATE_TRIES:
                    raise
                wait = C.reset_wait(e.reset, clock.now()) + rng.uniform(*RATE_JITTER)
                spent = waited.get((name, rep), 0.0)
                if spent + wait > RATE_WAIT_MAX:
                    detail(f"{kind} {name}: rate-limited, {spent:.0f} s waited already for this sample: no more")
                    raise
                waited[(name, rep)] = spent + wait
                detail(f"{kind} {name}: rate-limited (try {i}), waiting {wait:.1f} s: {e.text}")
                log({"event": "rate-wait", "age": name, "rep": rep, "try": i, "waitSec": round(wait, 1)})
                clock.sleep(wait)

    def prime(prompt, name, rep, paced=False):
        """(handle, usage, start time) or None. Tried again on an error, never on a refusal (a rate limit's wait
        aside: send). A priming that was not one explicit model request (Muse's `calls: 0`, or no count) is no
        priming: tried again too."""
        for i in range(PRIME_TRIES):
            try:
                (handle, usage), t0 = send(lambda: h.start(prompt), "prime", name, rep, paced=paced and i == 0)
                if usage.get("calls") != 1:
                    raise C.ClientError(f"the priming made {usage.get('calls')!r} model requests, not 1",
                                        kind="not-one-call")
            except C.Refused as e:
                kind = failed(f"priming {name}", e)
                if e.kind == "quota":
                    raise Stop("quota")
                log({"event": "prime-refused", "age": name, "kind": kind})
                return None
            except Exception as e:  # noqa: BLE001 - any client failure: try the priming again
                log({"event": "retry", "age": name, "error_kind": failed(f"priming {name}", e), "try": i + 1})
                clock.sleep(RETRY_WAIT)
                continue
            watch(usage)
            number(handle)
            return handle, usage, t0
        log({"event": "prime-failed", "age": name})
        return None

    def scan(handles, final=False):
        """The run-level model check (Codex): each session's whole record, after every check and at the run's end. A
        model other than the requested one anywhere, or a record that cannot all be read, excludes the whole run
        (scripts/build_observed.py), and a check that finds either stops it (`stop`, `other-model` or
        `unreadable-session`). Nothing for a client that keeps no such record. The public event carries no text from
        any session file: `final`, how many other models were named (`other_models`, a count) and `unreadable`; the
        names go to the console log (detail, private) only, for the audit."""
        read = getattr(h, "other_models", None)
        if read is None:
            return
        other, unreadable = set(), False
        for x in handles:
            found = read(x)
            if found is None:
                return
            names, bad = found
            other |= set(names)
            unreadable = unreadable or bool(bad)
        if other:
            detail(f"model-scan: other models named in the session files: {sorted(other)!r}")
        log({"event": "model-scan", "final": bool(final), "other_models": len(other), "unreadable": bool(unreadable)})
        if not final and (other or unreadable):
            raise Stop("other-model" if other else "unreadable-session")

    def check(name, age, handle, primed, t0, baseline, rep=0, latest=None):
        warm = check_once(name, age, handle, primed, t0, baseline, rep, latest)
        scan([handle])
        return warm

    def check_once(name, age, handle, primed, t0, baseline, rep=0, latest=None):
        """True / False for a counted check, None for one that is not (failed, invalid). Sent once (a rate limit's
        refusal aside: no model read it; send)."""
        base = {"age": name, "ageSec": age, "realAgeSec": round(clock.now() - t0), "session": number(handle)}
        try:
            r, started = send(lambda: h.resume(handle, OK_PROMPT), "check", name, rep, latest)
            real = started - t0
            base["realAgeSec"] = round(real)
        except C.Refused as e:
            kind = failed(f"check {name}", e)
            if e.kind == "quota":
                raise Stop("quota")
            log({"event": "check-failed", **base, "kind": kind})
            return None
        except Stop:
            raise
        except Exception as e:  # noqa: BLE001 - a failed check is never sent again
            log({"event": "check-failed", **base, "error_kind": failed(f"check {name}", e)})
            return None
        if cumulative:
            r = dict(r, raw={k: r.get(k) for k in ("total", "cached", "write")},
                     **{k: (r.get(k) or 0) - (primed.get(k) or 0) for k in ("total", "cached", "write")})
        if r.get("calls") != 1:
            log({"event": "check-invalid", **base, "reason": "not-one-call", "usage": r, "prime": primed})
            watch(r)
            return None
        issue = r.get("model_issue")
        if issue or not r.get("model"):
            # No model evidence of this turn's own, evidence that is not certainly this turn's, or another model than
            # the one asked for (Codex: clients.codex_answer): not a measurement of the requested model.
            log({"event": "check-invalid", **base, "reason": issue if issue in C.MODEL_ISSUES else "no-model",
                 "usage": r, "prime": primed})
            watch(r)
            return None
        watch(r)
        unique = max(primed["total"] - baseline, 1)
        warm = r["cached"] >= baseline + unique / 2
        log({"event": "check", **base, "late": real > late_after(age), "warm": warm, "usage": r, "prime": primed,
             "unique": unique})
        return warm

    try:
        b = prime(baseline_prompt(salt), "baseline", 0)
        if not b:
            raise Stop("baseline-failed")
        baseline = b[1]["total"]
        log({"event": "baseline", "usage": b[1]})

        def control(k):
            """The k-th control (0, then 1): its own session and unique block, primed, checked at 30 seconds."""
            c = prime(prime_prompt(f"{salt}-0" if k == 0 else f"{salt}-c{k}", words, filler), "control", k)
            if not c:
                raise Stop("control-failed")
            handle, primed, t0 = c
            log({"event": "prime", "age": "control", "rep": k, "session": number(handle), "usage": primed})
            clock.sleep(t0 + CONTROL_AGE - clock.now())
            if clock.now() - t0 > late_after(CONTROL_AGE):
                # Checked late (a slow priming): the check would show nothing; it is not sent.
                raise Stop("control-late", f"the control could be checked only {round(clock.now() - t0)} s after its "
                                           "priming")
            warm = check("control", CONTROL_AGE, handle, primed, t0, baseline, k, t0 + late_after(CONTROL_AGE))
            if warm is None:
                raise Stop("control-failed")
            return warm

        # The control first: primed, checked at 30 seconds, and only then the others. One cold sample is not enough to
        # give up on a model: a cold control gets one more, in a fresh session; both cold end the run.
        k = 0
        while not control(k):
            k += 1
            if k >= CONTROLS:
                raise Stop("no-observable-cache")
            detail("the control was cold: one more control, in a fresh session")

        # The samples of one age are primed in waves (replica r in wave r mod `waves`), a wave starting at least
        # `wave_gap` seconds after the one before, and two replicas of one age primed at least `wave_gap` seconds
        # apart, whatever a slow priming did to the wave (M-3 of the parity design). Within a wave, long ages first,
        # so the short checks do not wait behind a long queue of primings; a check that falls due is made before the
        # next priming.
        waves = max(1, min(waves, replicas or 1))
        samples = sorted([(x, ag, r, r % waves) for r in range(replicas) for x, ag in zip(labels, ages)],
                         key=lambda s: (s[3], -s[1]))
        queue, due, n, wave_start, age_primed = list(samples), [], 0, {}, {}
        while queue or due:
            now = clock.now()
            if due and due[0][0] <= now:
                _, _, name, age, rep, handle, primed, t0 = heapq.heappop(due)
                check(name, age, handle, primed, t0, baseline, rep)
                continue
            if queue:
                name, age, rep, wave = queue[0]
                ready = wave_start[wave - 1] + wave_gap if wave and wave - 1 in wave_start else None
                if name in age_primed:
                    ready = max(ready or 0, age_primed[name] + wave_gap)
                if ready is not None and now < ready:
                    clock.sleep(min(ready, due[0][0]) - now if due else ready - now)
                    continue
                if pace and not pace("prime", due[0][0] if due else None):
                    continue  # a check fell due while this priming waited for its turn: the check first
                queue.pop(0)
                n += 1
                p = prime(prime_prompt(f"{salt}-{n}", words, filler), name, rep, paced=bool(pace))
                if p:
                    handle, primed, t0 = p
                    wave_start.setdefault(wave, t0)
                    age_primed[name] = t0
                    log({"event": "prime", "age": name, "rep": rep, "wave": wave, "session": number(handle),
                         "usage": primed})
                    heapq.heappush(due, (t0 + age, n, name, age, rep, handle, primed, t0))
                else:
                    wave_start.setdefault(wave, clock.now())
            else:
                clock.sleep(due[0][0] - now)
    except Stop as s:
        if s.text:
            detail(f"stop {s.reason}: {s.text}")
        scan(sessions, final=True)
        log({"event": "stop", "reason": s.reason})
        return s.reason
    scan(sessions, final=True)
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

    def other_models(s, handle):
        if handle is None:
            return set(), True
        return s.session.client.other_models(s.session.home, handle)


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
                    help="keep every invocation's output, redacted, in DIR, under --client-home (never a link, never in "
                         "the repository, a checkout, an everyday or a synced folder; mode 700, files 600): for the "
                         "smoke runs, to correct the fixtures")
    ap.add_argument("--delay", type=float, default=0.0,
                    help="seconds to wait before the run's checks and first request (harness/night.py staggers starts)")
    ap.add_argument("--launch-id", help="harness/night.py's mark of the launch this run belongs to (process identity)")
    ap.add_argument("--pace-rpm", type=int, default=0,
                    help="the client's request budget per minute, shared by every run that names the same --pace-dir "
                         "(harness/pacing.py); 0: none")
    ap.add_argument("--pace-dir", metavar="DIR",
                    help="the folder of the shared budget, under --client-home (harness/night.py: "
                         "<client-home>/night-<date>/pacing; mode 700, files 600)")
    ap.add_argument("--dry-run", action="store_true", help="print the run's start event and plan; run nothing, send nothing")
    return ap


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# home: the state folder; HOME: a throwaway home beside it (clients.throwaway_home); work: the working folder.
ISOLATION = {"home": "dedicated", "HOME": "throwaway", "work": "temporary"}
CONFINEMENT = ("sandbox-exec: no file write under the home folder but the state folder, the throwaway HOME and the "
               "temporary folder")


def settings_of(pairs):
    out = {}
    for p in pairs:
        if "=" not in p:
            raise SystemExit(f"--client-env {p}: KEY=VALUE")
        k, v = p.split("=", 1)
        out[k] = v
    return out


def private_capture_folder(keep, client_home, root, user_home=None):
    """The folder of a run's redacted raw output (finding 13): under <client-home>, reached through no link at any
    level below it, outside the repository, every checkout, every everyday and every synced folder; made mode 700,
    and refused when it exists with any access for others."""
    user_home = os.path.realpath(user_home or os.path.expanduser("~"))
    if not client_home:
        raise SystemExit("--keep-raw: --client-home (GROUNDTRUTH_CLIENT_HOME) is required: the raw output stays there")
    base, keep = os.path.abspath(client_home), os.path.abspath(keep)
    if not C.inside(keep, base) or keep == base:
        raise SystemExit("--keep-raw: a folder under <client-home> (the raw output is never published)")
    p = base
    for part in os.path.relpath(keep, base).split(os.sep):
        p = os.path.join(p, part)
        if os.path.islink(p):
            raise SystemExit(f"--keep-raw: <client-home>/{os.path.relpath(p, base)} is a link: refused")
        if os.path.lexists(p) and not os.path.isdir(p):
            raise SystemExit(f"--keep-raw: <client-home>/{os.path.relpath(p, base)} is not a folder: refused")
    if not C.inside(os.path.realpath(keep), os.path.realpath(base)):
        raise SystemExit("--keep-raw: the folder resolves outside <client-home>: refused")
    C.check_folder("--keep-raw", base, root, user_home)
    C.check_folder("--keep-raw", keep, root, user_home)
    p = base
    for part in os.path.relpath(keep, base).split(os.sep):
        p = os.path.join(p, part)
        if not os.path.isdir(p):
            os.mkdir(p, 0o700)
            os.chmod(p, 0o700)
    C.check_private("--keep-raw: the raw folder", keep)
    return keep


PRIVATE_RUNS = "private-runs"


def private_record(client_home, label, salt, record):
    """The run's private record, <client-home>/private-runs/<label>-<salt>.json (folder 700, file 600; checked as the
    raw-output folder is): what a public result never carries (the client's version as it printed it)."""
    folder = private_capture_folder(os.path.join(client_home, PRIVATE_RUNS), client_home, ROOT)
    record = dict(record, at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    C.write_private(os.path.join(folder, f"{label}-{salt}.json"), json.dumps(record) + "\n")


def main(argv=None):
    """The probe; any failure before or outside the run's own log reaches the console redacted (the console log of a
    launched run is kept, mode 600, beside the results): never a traceback, a child-only value or a folder."""
    redact = C.Redactor(os.environ, [os.environ.get("GROUNDTRUTH_CLIENT_HOME"), os.path.expanduser("~")])
    try:
        return _main(argv)
    except SystemExit as e:
        if isinstance(e.code, str):
            raise SystemExit(redact.scrub(e.code)) from None  # printed by Python, exit 1
        raise
    except Exception as e:  # noqa: BLE001 - reported redacted, never as a traceback
        raise SystemExit(redact.scrub(f"probe: {type(e).__name__}: {e}")) from None


# Seconds a launched run waits for its pid to be in the launch's lock before its first client call.
RECORD_WAIT = 5.0
LAUNCH_ID = re.compile(r"(\d{4}-\d{2}-\d{2})-([a-z]+)-[0-9a-f]{12}")


class NightStop:
    """A launched run's guard (harness/night.py): the night's stop mark is the authority. `run` is the runner of every
    client invocation of the run (status, version, each priming and check): it looks for the mark immediately before
    each one and exits (SystemExit) without calling the client once the mark exists. `wait_recorded` holds the run
    before its first client call until its own pid is in the lock under its label and launch id, and exits if it is
    not there within RECORD_WAIT seconds (a launcher ended before recording it) or the mark appears meanwhile."""

    def __init__(self, client_home, launch_id, label, harness):
        m = LAUNCH_ID.fullmatch(launch_id or "")
        if not client_home or not m or m.group(2) != harness:
            raise SystemExit(f"{label}: --launch-id {launch_id!r} is not a launch of {harness} under <client-home>: "
                             "not run")
        folder = os.path.join(client_home, f"night-{m.group(1)}", "launch")
        self.lock, self.mark = os.path.join(folder, harness + ".json"), os.path.join(folder, harness + ".stop")
        self.launch_id, self.label = launch_id, label

    def check(self):
        if os.path.lexists(self.mark):
            raise SystemExit(f"{self.label}: the night's stop mark is set: no client call; the run ends here")

    def recorded(self):
        try:
            with open(self.lock) as f:
                lock = json.load(f)
            run = lock["runs"][self.label]
            return lock["launch_id"] == self.launch_id and run["pid"] == os.getpid()
        except (OSError, ValueError, KeyError, TypeError):
            return False

    def wait_recorded(self, wait=RECORD_WAIT):
        end = time.monotonic() + wait
        while True:
            self.check()
            if self.recorded():
                return
            if time.monotonic() >= end:
                raise SystemExit(f"{self.label}: its pid is not in the launch's lock after {wait:g} s: no client call; "
                                 "the run ends here")
            time.sleep(0.05)

    def run(self, *a, **kw):
        self.check()
        return C._run(*a, **kw)


def stay_awake_and_stoppable(launched):
    """A launched run (harness/night.py) is its own process: `stop` signals its pid alone. SIGTERM, SIGINT and SIGHUP
    are taken out of any inherited blocked set and end the probe through an exception, so that the client invocation
    under way is killed with it (subprocess.run kills its child on any exception) and the temporary folder removed.
    On macOS it keeps the computer awake for as long as this pid lives (`caffeinate -i -w <pid>`, which ends with it)."""
    if not launched:
        return  # a run in the foreground (smoke, a test): Ctrl-C interrupts it as usual
    import signal

    def end(signum, frame):
        raise SystemExit(128 + signum)
    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(sig, end)
    signal.pthread_sigmask(signal.SIG_UNBLOCK, {signal.SIGTERM, signal.SIGINT, signal.SIGHUP})
    if sys.platform == "darwin" and shutil.which("caffeinate"):
        import subprocess
        subprocess.Popen(["caffeinate", "-i", "-w", str(os.getpid())], stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


def _main(argv=None):
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
        start["confinement"] = CONFINEMENT if C.CONFINED else "none (not macOS): the environment's isolation only"
    start["waves"] = {"waves": max(1, min(a.waves, a.replicas or 1)), "gap_s": a.wave_gap}
    if a.pace_rpm < 0 or (a.pace_rpm and not a.pace_dir):
        raise SystemExit("--pace-rpm: a number of requests per minute (0: none), with --pace-dir")
    if a.pace_rpm:
        start["pacing"] = {"rpm": a.pace_rpm, "reserve_for_checks": pacing.reserve_of(a.pace_rpm)}
    if client.run_info():
        start[a.harness] = client.run_info()
    # The commands as the plan has them (no folder of this machine): the start record is complete before any client
    # is invoked, and is the plan Public writes.
    plan = C.Session(client, env=None, io="<io>", work="<work>", create=False)
    start.update(command={"prime": plan.plan(), "check": plan.plan(resume="<session>")})
    frozen = json.dumps(start)  # the plan, before any client is invoked
    if a.dry_run:
        env = client.environment("<client-home>/" + client.client_id, base={k: "<" + k + ">" for k in C.ALLOW})
        requests = 1 + 2 * CONTROLS + 2 * a.replicas * len(ages)
        print(json.dumps(start))
        print(f"{a.label}: {a.harness} {a.model}: baseline, control (checked at 30 s; a second one in a fresh session "
              f"if it is cold), then {a.replicas} x {len(ages)} samples ({', '.join(labels)}): at most {requests} "
              f"requests ({requests - 2} with a warm first control), and up to {RATE_TRIES - 1} more tries of one "
              "request on a rate limit that names its reset.")
        if a.pace_rpm:
            print(f"{a.label}: paced: at most {a.pace_rpm} {a.harness} requests a minute with every run sharing "
                  f"{a.pace_dir} (primings {a.pace_rpm - pacing.reserve_of(a.pace_rpm)} of them).")
        if a.delay:
            print(f"{a.label}: starts {a.delay:g} s after its launch.")
        if client.isolated:
            print(f"{a.label}: environment {json.dumps(env)}; working folder: a new empty folder under the system's "
                  "temporary folder. Dry run: nothing run, nothing sent.")
        else:
            print(f"{a.label}: the caller's environment (a proxy client). Dry run: nothing run, nothing sent.")
        return
    stay_awake_and_stoppable(bool(a.launch_id))
    night = NightStop(a.client_home, a.launch_id, a.label, a.harness) if a.launch_id else None
    if night:
        night.wait_recorded()
    run = night.run if night else None  # every client invocation of a launched run passes the stop mark first
    if a.delay > 0:
        # A staggered start (harness/night.py): waits first, so that the checks below are made just before the run.
        time.sleep(a.delay)
    keep = private_capture_folder(a.keep_raw, a.client_home, ROOT) if a.keep_raw else None
    pace = None
    if a.pace_rpm:
        # The client's budget, shared with every run of the night (pacing.py): its folder checked as the raw output's.
        folder = private_capture_folder(a.pace_dir, a.client_home, ROOT)
        pace = pacing.Pacer(pacing.FileStore(folder, a.harness), a.pace_rpm, Clock()).acquire
    home = None
    if client.isolated:
        home = C.state_folder(client, a.client_home, ROOT, run=run)
        env = client.environment(home)
        import scan_secrets
        for k in client.passthrough:  # a value only the child knows: its fingerprint, for the scan at commit time
            scan_secrets.remember(env.get(k), k)
    else:
        env = None
    # A new empty working folder outside every repository (a client reads CLAUDE.md / AGENTS.md from the folders above
    # it), kept until the last check: a session is resumed from the folder it was started in. The folder it is made in
    # is checked first (outside every checkout and every everyday folder, whatever TMPDIR says), then the folder itself.
    user_home = os.path.realpath(os.path.expanduser("~"))
    C.check_folder("the working folder (TMPDIR)", tempfile.gettempdir(), ROOT, user_home)
    tmp = tempfile.mkdtemp(prefix=f"groundtruth-{a.label}-")
    try:
        C.check_folder("the working folder (TMPDIR)", tmp, ROOT, user_home)
        writable = None
        if env is not None:
            # The client's TMPDIR is its own under <client-home> (clients.throwaway_tmp), never the shell's.
            writable = [home, env.get("HOME"), env.get("TMPDIR"), tmp]  # what the client may write (confine)
        session = C.Session(client, env=env, io=os.path.join(tmp, "io"), work=os.path.join(tmp, "work"),
                            home=home, keep=keep, writable=writable, run=run)
        # The client's version is its own text: never in a public result. It goes to the console log (mode 600) and to
        # the run's private record under <client-home> (private_record), for the audit.
        version = client.version(env, run=run, writable=writable)
        print(f"detail: client version: {version}", file=sys.stderr, flush=True)
        if a.client_home:
            private_record(a.client_home, a.label, salt, {"label": a.label, "salt": salt, "client": client.client_id,
                                                          "model": a.model, "launch_id": a.launch_id,
                                                          "client_version": version, "results": a.out})
        os.makedirs(a.out, exist_ok=True)
        path = os.path.join(a.out, f"{a.label}.jsonl")

        def note(text):
            # A failure's detail: only on the console (the launched run's log, mode 600), redacted whole and only then
            # clipped; a public event carries its kind alone.
            print(f"detail: {session.redact(str(text))[-1500:]}", file=sys.stderr, flush=True)

        # The only writer of the public record; the last guard, the scrub, leaves no value of the child's secret
        # variables in any field.
        public = Public(path, json.loads(frozen), private=note, scrub=session.redact.scrub)

        def log(ev):
            line = public.line(ev)
            if line:
                print(line, flush=True)

        log({"event": "start"})
        run_probe(Harness(session), ages=ages, labels=labels, replicas=a.replicas, words=a.words, salt=salt, log=log,
                  filler=a.filler, waves=a.waves, wave_gap=a.wave_gap, detail=note, pace=pace)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
