#!/usr/bin/env python3
"""Cache-lifetime probe through real coding harnesses (Claude Code, Codex CLI, Devin CLI, Muse Code, pi).

The clients themselves (how each is driven and how its output is read) are in harness/clients.py.

Each sample starts a new harness session whose first message carries a unique block of ~N tokens, then, after a fixed
age, resumes that session with a short message and reads the cached-token count the harness reports. Harnesses share a
large system prompt between sessions, so a check is warm only when the cache covers the shared part *and* at least half
of the sample's unique block: cached >= baseline + unique / 2, where baseline is the prompt size of a session without
the block (measured once at start). One check per sample, like the TypeScript probe in src/.

Usage:
  harness/probe.py --harness claude|codex|devin|muse|pi --model ID [--schedule std|long | --ages 30m,1h] --replicas 3 --label H1 --out DIR
"""
import argparse, heapq, json, os, random, sys, threading, time, uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import clients as C  # noqa: E402

OK_PROMPT = "Reply with OK only. Do not use any tools."


# Where every evaluation starts: the control (sent again at once) is always made, then these ages, whatever else
# is asked for. The same lists as src/schedule.ts (test/schedule.test.ts checks it).
LADDER_START = ["2.5m", "5m", "7.5m"]
STD_REST = ["10m", "15m", "20m", "25m", "30m", "40m", "50m", "60m", "75m", "90m", "120m"]
LONG_REST = ["4h", "8h", "12h"]
SCHEDULES = {"std": LADDER_START + STD_REST, "long": LADDER_START + STD_REST + LONG_REST}


def parse_age(s):
    s = s.strip()
    if s.endswith("h"): return float(s[:-1]) * 3600
    if s.endswith("m"): return float(s[:-1]) * 60
    if s.endswith("s"): return float(s[:-1])
    return float(s)


def unique_block(salt, words):
    rnd = random.Random(salt)
    cons, vows = "bcdfghjklmnprstvz", "aeiou"
    out = []
    for _ in range(words):
        out.append("".join(rnd.choice(cons) + rnd.choice(vows) for _ in range(rnd.randint(2, 4))))
    return " ".join(out)


def prime_prompt(salt, words):
    return (f"Reference document {salt}, keep it for later. Do not use any tools. Reply with OK only.\n\n<doc>\n"
            + unique_block(salt, words) + "\n</doc>")


class Harness:
    """start/resume as the loop below calls them, over a client of harness/clients.py."""
    def __init__(s, session):
        s.session, s.cumulative = session, session.client.cumulative
    def start(s, prompt):
        handle, u = s.session.start(prompt)
        return handle, u.record()
    def resume(s, handle, prompt):
        return s.session.resume(handle, prompt).record()


HARNESSES = C.CLIENTS


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--harness", required=True, choices=HARNESSES)
    ap.add_argument("--model", required=True)
    ap.add_argument("--schedule", choices=sorted(SCHEDULES), default="std", help="std: 2.5m to 2h; long: std + 4h, 8h, 12h")
    ap.add_argument("--ages", help="more ages instead of --schedule, e.g. 30m,1h; 2.5m, 5m and 7.5m are always added")
    ap.add_argument("--replicas", type=int, default=3)
    ap.add_argument("--label", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--words", type=int, default=3000, help="unique block size in words (~2 tokens each)")
    ap.add_argument("--effort", default="low")
    ap.add_argument("--checkers", type=int, default=1)
    a = ap.parse_args()

    os.makedirs(a.out, exist_ok=True)
    work = os.path.abspath(os.path.join(a.out, f"work-{a.label}")); os.makedirs(work, exist_ok=True)
    h = Harness(C.Session(HARNESSES[a.harness](a.model, a.effort), env=None, io=work, work=work))
    salt = uuid.uuid4().hex[:8]
    path = os.path.join(a.out, f"{a.label}.jsonl")
    lock = threading.Lock()

    def log(ev):
        ev["at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with lock:
            with open(path, "a") as f: f.write(json.dumps(ev) + "\n")
            print(json.dumps(ev), flush=True)

    def attempt(fn, *args):
        for i in range(3):
            try: return fn(*args)
            except Exception as e:
                log({"event": "retry", "error": str(e)[:300], "try": i + 1}); time.sleep(30)
        return None

    # Custom ages are added to the start of the ladder, never put in its place; each age once, shortest first.
    wanted = LADDER_START + [x.strip() for x in a.ages.split(",")] if a.ages else SCHEDULES[a.schedule]
    by_age = {}
    for x in wanted: by_age.setdefault(parse_age(x), x)
    ages = sorted(by_age); labels = [by_age[x] for x in ages]
    a.ages = ",".join(labels)
    log({"event": "start", "harness": a.harness, "model": a.model, "ages": a.ages, "replicas": a.replicas,
         "words": a.words, "effort": a.effort, "salt": salt})
    b = attempt(h.start, OK_PROMPT)
    if not b: log({"event": "abort", "reason": "baseline failed"}); return
    baseline = b[1]["total"]
    log({"event": "baseline", "usage": b[1]})

    samples = [("control", 30.0, 0)] + [(x, ag, r) for r in range(a.replicas) for x, ag in zip(labels, ages)]
    # long ages first, so the short checks do not wait behind a long priming queue
    samples = [samples[0]] + sorted(samples[1:], key=lambda s: -s[1])
    heap, hlock, cv = [], threading.Lock(), threading.Condition()
    pending = [len(samples)]

    def checker():
        while True:
            with cv:
                while True:
                    if not heap and pending[0] == 0: return
                    if heap and heap[0][0] <= time.time(): item = heapq.heappop(heap); break
                    cv.wait(timeout=5)
            due, n, name, age, handle, prime, t0 = item
            r = attempt(h.resume, handle, OK_PROMPT)
            real = time.time() - t0
            if r and getattr(h, "cumulative", False):
                r = dict(r, raw={k: r[k] for k in ("total", "cached", "write")},
                         **{k: r[k] - prime.get(k, 0) for k in ("total", "cached", "write")})
            if r:
                unique = max(prime["total"] - baseline, 1)
                warm = r["cached"] >= baseline + unique / 2
                log({"event": "check", "age": name, "ageSec": age, "realAgeSec": round(real), "late": real > age * 1.1 + 90,
                     "warm": warm, "usage": r, "prime": prime, "unique": unique, "handle": handle})
            else:
                log({"event": "check-failed", "age": name, "handle": handle})
            with cv:
                pending[0] -= 1; cv.notify_all()

    threads = [threading.Thread(target=checker, daemon=True) for _ in range(a.checkers)]
    for t in threads: t.start()
    for i, (name, age, rep) in enumerate(samples):
        r = attempt(h.start, prime_prompt(f"{salt}-{i}", a.words))
        if not r:
            log({"event": "prime-failed", "age": name})
            with cv: pending[0] -= 1; cv.notify_all()
            continue
        handle, prime = r
        t0 = time.time()
        log({"event": "prime", "age": name, "rep": rep, "handle": handle, "usage": prime})
        with cv:
            heapq.heappush(heap, (t0 + age, i, name, age, handle, prime, t0)); cv.notify_all()
    for t in threads: t.join()
    log({"event": "done"})


if __name__ == "__main__":
    main()
