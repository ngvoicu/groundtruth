#!/usr/bin/env python3
"""Start the lifetime runs of one login one after another, and stop them all at that login's refusal.

    python3 results/logins-long-2026-11-17/sequence.py <group> [--prime-timeout <s>] [--devin-rate]
        <label>=<model>[@<probe option>@<value>...] ...

Each run is the probe (src/cli.ts, 0.3.3) through the local CLIProxyAPI with --stop-on-refusal and 3 samples per
age, its output in logs/<label>.log. The next run starts only after the one before has logged `priming done` (or has
ended), so only one run of a login primes at a time (the request-rate limits of Devin and Antigravity, 2026-11-17).

- A quota or rate refusal in any run's log ends every other run of this login (only processes this script started,
  by process id) and nothing more is started.
- --devin-rate: the chief's rule for Devin. A first refusal that names the request rate ("request rate limit ...
  reset in N seconds") is waited out once (N + 60 s); then the refused model is started again (label suffix `b`) and
  every run after it at half the pace (twice the --prime-pause). A second refusal, or one about the plan, quota or
  credits, ends Devin.
- --prime-timeout <s>: a run that has not logged `priming done` this long after its start is ended (Antigravity:
  ten minutes, the chief's rule for Google's capacity errors) and the next model is started.

Its log is logs/sequence-<group>.log with every process id it started; logs/status.md is rewritten every minute
(status.py). The client key is read by the caller into CACHE_PROBE_KEY (run.sh) and never written anywhere.
"""
import os, re, signal, subprocess, sys, time

R = "results/logins-long-2026-11-17"
args = sys.argv[1:]
group = args.pop(0)
prime_timeout = None
devin_rate = False
while args and args[0].startswith("--"):
    flag = args.pop(0)
    if flag == "--prime-timeout":
        prime_timeout = int(args.pop(0))
    elif flag == "--devin-rate":
        devin_rate = True
    else:
        sys.exit(f"unknown flag {flag}")
specs = args
os.makedirs(f"{R}/logs", exist_ok=True)
log = open(f"{R}/logs/sequence-{group}.log", "a")


def say(line):
    log.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} {line}\n"); log.flush()


def status():
    subprocess.run([sys.executable, f"{R}/status.py"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


procs = {}        # label -> Popen
stopped = False   # the login is finished: nothing more is sent
rate_waited = False
pace_factor = 1
REFUSAL = "quota or rate refusal, not retried"


def text(label):
    try:
        return open(f"{R}/logs/{label}.log", errors="replace").read()
    except FileNotFoundError:
        return ""


def end_all(reason):
    global stopped
    say(f"{reason}: ending the other runs of this login, starting no more")
    for other, q in procs.items():
        if q.poll() is None:
            q.send_signal(signal.SIGTERM)
            say(f"sent SIGTERM to {other} pid {q.pid}")
    stopped = True


seen_refusals = set()


def watch():
    """Returns ('stop', None), ('rate', (label, seconds)) or (None, None)."""
    for label in list(procs):
        if label in seen_refusals:
            continue
        t = text(label)
        if REFUSAL in t:
            seen_refusals.add(label)
            line = next(l for l in t.splitlines() if REFUSAL in l)
            say(f"{label} refused: {line.strip()[:400]}")
            m = re.search(r"reset in (\d+) seconds?", line)
            about_rate = re.search(r"request rate limit", line, re.I) and not re.search(r"plan|quota|credit", line, re.I)
            if devin_rate and not rate_waited and about_rate and m:
                return "rate", (label, int(m.group(1)))
            return "stop", None
    return None, None


def handle(event):
    global rate_waited, pace_factor
    kind, info = event
    if kind == "stop":
        end_all("a quota or rate refusal")
        return None
    if kind == "rate":
        label, secs = info
        # The refused run has ended by itself (--stop-on-refusal); the others are left running: their checks are
        # single requests. Nothing new is started during the wait.
        rate_waited = True
        pace_factor = 2
        say(f"{label}: first rate refusal, waiting {secs} + 60 s once, then half the pace")
        time.sleep(secs + 60)
        return label
    return None


def start(label, model, extra):
    pause = None
    if "--prime-pause" in extra:
        i = extra.index("--prime-pause")
        pause = int(extra[i + 1]) * pace_factor
        extra = extra[:i] + ["--prime-pause", str(pause)] + extra[i + 2:]
    defaults = [] if "--ages" in extra or "--schedule" in extra else ["--schedule", "std"]
    cmd = ["node", "src/cli.ts", "--base-url", "http://127.0.0.1:8317/v1", "--model", model, "--label", label,
           "--replicas", "3", "--stop-on-refusal", "--record-header", "x-cpa-auth-kind", "--out", R] + defaults + extra
    out = open(f"{R}/logs/{label}.log", "a")
    p = subprocess.Popen(cmd, stdout=out, stderr=subprocess.STDOUT)
    procs[label] = p
    say(f"started {label} pid {p.pid}: {' '.join(cmd[2:])}")
    status()
    return p


queue = [(s.split("=", 1)[0], *s.split("=", 1)[1].partition("@")[::2]) for s in specs]
queue = [(label, model, extra.replace("@", " ").split()) for label, model, extra in queue]
say(f"sequence {group}: {len(queue)} runs; pid {os.getpid()}")
i = 0
while i < len(queue) and not stopped:
    label, model, extra = queue[i]
    p = start(label, model, extra)
    t0 = time.time()
    # Wait for this run's priming to finish (or the run to end) before the next one starts.
    while True:
        time.sleep(5)
        again = handle(watch())
        if stopped:
            break
        if again:
            # the refused model once more, under a new label, at half the pace
            base = next(q for q in queue if q[0] == again)
            queue.insert(i + 1, (again + "b", base[1], base[2]))
            break
        if "priming done" in text(label) or p.poll() is not None:
            say(f"{label}: {'priming done' if 'priming done' in text(label) else f'ended with {p.returncode}'} after {int(time.time() - t0)} s")
            break
        if prime_timeout and time.time() - t0 > prime_timeout:
            p.send_signal(signal.SIGTERM)
            say(f"{label}: not primed after {prime_timeout} s: ended (SIGTERM pid {p.pid}), going on with the next model")
            break
        if int(time.time() - t0) % 60 < 5:
            status()
    i += 1

while any(q.poll() is None for q in procs.values()):
    time.sleep(30)
    if not stopped:
        handle(watch()) if not devin_rate else (end_all("a refusal after the last start") if watch()[0] else None)
    status()
for label, q in procs.items():
    say(f"{label} exited with {q.returncode}")
status()
say("done")
