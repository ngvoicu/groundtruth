#!/usr/bin/env python3
"""The run plan of docs/own-clients.md, section 4, as commands (the owner's steps: docs/own-clients-RUN.md).

    python3 harness/night.py --date 2026-11-23 --dry-run all          # every command, and each tool's own dry run
    python3 harness/night.py --date 2026-11-23 --dry-run claude CX1   # some parts or ids
    python3 harness/night.py --date 2026-11-23 --go smoke             # runs them (the owner's go only)
    python3 harness/night.py --date 2026-11-23 untouched --save | --compare

Parts, in the night's order: openrouter (OR1 - OR5 cache, straight to OpenRouter), windows (OW1 - OW9), smoke (S1 - S4
and the refused request of each), claude (CC1 - CC4, then CC5 - CC8), codex (CX1 - CX6), devin (DV1 - DV17), muse
(MC1 - MC3), limits (CL1 - CL4). limits-devin (DL1 - DL12) and limits-muse (ML1 - ML3) only once the smoke runs show
the provider's own refusal (decision 3). Antigravity has no own-client run (decision 6); OR1b - OR5b are not in the
plan: a second OpenRouter run at 8,000 tokens is decided after the first one.

--dry-run prints each command and runs the tool's own --dry-run (harness/probe.py, harness/client_limits.py,
node src/cli.ts), which runs no client and sends nothing; the OpenRouter windows print their request. Without
--dry-run or --go nothing happens.

--go: cache runs start detached, each kept awake by its own `caffeinate -i`, with their log and pid in
results/<folder>/logs/ (never committed); a label that has a pid file or a raw file is not started again. Limits
walks and windows run one after the other, in the foreground. Keys come from the Keychain only at --go, straight into
the one process that needs them: META_API_KEY for Muse Code, the OpenRouter key for the OpenRouter parts; they are
never printed or written.
"""
import argparse
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OPENROUTER = "https://openrouter.ai/api/v1"
# The owner's Keychain items for this campaign (generic passwords, account = the user name). Read only, at --go.
KEYCHAIN = {"META_API_KEY": "groundtruth META_API_KEY", "OPENROUTER": "groundtruth OPENROUTER_API_KEY"}
MONEY_STOP = 4.00  # USD on the campaign's OpenRouter key (its own limit is 5)
STD65 = "10m,15m,20m,25m,30m,40m,50m,60m,65m,75m,90m,120m"


def probe(id_, harness, model, ages=None, schedule=None, filler=None, env=None):
    args = ["--harness", harness, "--model", model, "--replicas", "3", "--label", id_]
    args += ["--ages", ages] if ages else ["--schedule", schedule or "std"]
    if filler:
        args += ["--filler", filler]
    for k, v in (env or {}).items():
        args += ["--client-env", f"{k}={v}"]
    return {"id": id_, "kind": "probe", "harness": harness, "model": model, "args": args}


def limit(id_, harness, model, accepted=None, refused=None, only_refusal=False):
    args = ["--harness", harness, "--model", model]
    if accepted:
        args += ["--accepted", str(accepted)]
    if refused:
        args += ["--refused", str(refused)]
    if only_refusal:
        args += ["--only-refusal"]
    return {"id": id_, "kind": "limits", "harness": harness, "model": model, "args": args}


def smoke(id_, harness, model):
    """Baseline, the control checked at 30 s (no other sample), then one request far above the window."""
    p = probe(id_, harness, model, ages=None)
    p["args"] = ["--harness", harness, "--model", model, "--replicas", "0", "--label", id_, "--schedule", "std"]
    return [p, limit(id_ + "-refusal", harness, model, only_refusal=True)]


DEVIN = [("DV1", "claude-opus-5-5-low", "std"), ("DV2", "claude-sonnet-5-5-low", "std"), ("DV3", "claude-haiku-5-5-low", "std"),
         ("DV4", "gpt-6-1-sol-low", "std"), ("DV5", "gpt-6-1-terra-low", "std"), ("DV6", "gpt-6-astra-low", "std"),
         ("DV7", "gpt-6-luna-low", "std"),
         ("DV8", "deepseek-v4-1-flash-1017-low", "long"), ("DV9", "glm-5-3-low", "long"), ("DV10", "kimi-k3-1-pro-low", "long"),
         ("DV11", "nemotron-3-5-super-none", "long"),
         ("DV12", "deepseek-v4-pro-low", "std"), ("DV13", "gemini-4-argon-low", "std"), ("DV14", "grok-4-7-low", "std"),
         ("DV15", "kimi-k3-low", "std"), ("DV16", "muse-wonder-1-0-low", "std"), ("DV17", "swe-2-medium", "std")]
# The proxy's rows (observed.json): input_accepted, input_refused, in tokens.
DEVIN_LIMITS = [("claude-opus-5-5", 999500, 1000300), ("claude-sonnet-5-5", 999500, 1000300), ("claude-haiku-5-5", 999500, 1000300),
                ("deepseek-v4-1-flash-1017", 1048076, 1048876), ("deepseek-v4-pro", 1048076, 1048876),
                ("gemini-4-argon", 1048076, 1048876), ("glm-5-3", 1047470, 1052845), ("gpt-6-1-sol", 921500, 922300),
                ("gpt-6-1-terra", 921500, 922300), ("gpt-6-astra", 921500, 922300), ("gpt-6-luna", 921500, 922300),
                ("swe-2", 300499, None)]
DEVIN_SUFFIX = {"swe-2": "-medium"}

PARTS = {
    "openrouter": [{"id": f"OR{i}", "kind": "openrouter", "model": m} for i, m in enumerate(
        ["openai/gpt-6-astra", "openai/gpt-6-luna", "meta/muse-spark-1.3", "deepseek/deepseek-v4.1-flash",
         "z-ai/glm-5.3-flash"], 1)],
    # Cheapest first; an answer instead of a refusal ends the list.
    "windows": [{"id": f"OW{i}", "kind": "window", "model": m} for i, m in enumerate(
        ["anthropic/claude-haiku-5.5", "anthropic/claude-opus-5.5", "anthropic/claude-sonnet-5.5",
         "deepseek/deepseek-v4.1-flash", "google/gemini-4-argon", "meta/muse-wonder", "moonshotai/kimi-k3.1-pro",
         "openai/gpt-6.1-sol", "openai/gpt-6.1-terra"], 1)],
    "smoke": smoke("S1", "claude", "claude-haiku-5-5") + smoke("S2", "codex", "gpt-6-luna")
    + smoke("S3", "devin", "claude-haiku-5-5-low") + smoke("S3b", "devin", "gpt-6-1-terra-low")
    + smoke("S4", "muse", "muse-spark-1.3"),
    "claude": [probe(f"CC{i}", "claude", m, ages=STD65, filler="list") for i, m in enumerate(
        ["claude-fable-5-2", "claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"], 1)],
    "claude-5m": [probe(f"CC{i}", "claude", m, ages="10m,15m", filler="list", env={"CLAUDE_CODE_PROMPT_CACHE_TTL": "5m"})
                  for i, m in enumerate(["claude-fable-5-2", "claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"], 5)],
    "codex": [probe(f"CX{i}", "codex", m, schedule="long") for i, m in enumerate(
        ["gpt-6.2-sol", "gpt-6.2-astra", "gpt-6.1-sol", "gpt-6.1-terra", "gpt-6-astra", "gpt-6-luna"], 1)],
    "devin": [probe(i, "devin", m, schedule=s) for i, m, s in DEVIN],
    "muse": [probe(f"MC{i}", "muse", m) for i, m in enumerate(["muse-wonder-1.0", "muse-ember-1.0", "muse-spark-1.3"], 1)],
    "limits": [limit(f"CL{i}", "claude", m) for i, m in enumerate(
        ["claude-fable-5-2", "claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"], 1)],
    "limits-devin": [limit(f"DL{i}", "devin", m + DEVIN_SUFFIX.get(m, "-low"), a, r) for i, (m, a, r) in enumerate(DEVIN_LIMITS, 1)],
    "limits-muse": [limit(f"ML{i}", "muse", m) for i, m in enumerate(["muse-wonder-1.0", "muse-ember-1.0", "muse-spark-1.3"], 1)],
}
ORDER = ["openrouter", "windows", "smoke", "claude", "claude-5m", "codex", "devin", "muse", "limits"]
ALL_STEPS = {s["id"]: s for part in PARTS.values() for s in part}
# Seconds between two detached starts of one part (Devin: as on 8 November).
SPACING = {"devin": 20}


def folders(date):
    return {"own": os.path.join("results", f"own-clients-{date}"), "or": os.path.join("results", f"openrouter-direct-{date}")}


def command(step, date):
    """The argument list of a step, run from the repository's root."""
    f = folders(date)
    if step["kind"] == "probe":
        out = os.path.join(f["own"], "smoke") if step["id"].startswith("S") else f["own"]
        return [sys.executable, "harness/probe.py", *step["args"], "--out", out]
    if step["kind"] == "limits":
        name = "smoke/refusals.jsonl" if step["id"].startswith("S") else "client-limits.jsonl"
        return [sys.executable, "harness/client_limits.py", *step["args"], "--out", os.path.join(f["own"], name)]
    if step["kind"] == "openrouter":
        return ["node", "src/cli.ts", "--base-url", OPENROUTER, "--format", "responses", "--model", step["model"],
                "--stop-on-refusal", "--label", step["id"], "--out", f["or"],
                "--usage-log", os.path.join(f["or"], "logs", step["id"] + ".usage.jsonl")]
    if step["kind"] == "window":
        return [sys.executable, "harness/night.py", "--date", date, "window", step["model"]]
    raise ValueError(step)


def window_body(model, n=1_200_000):
    return {"model": model, "max_tokens": 16, "transforms": [],
            "messages": [{"role": "user", "content": "Reply with just OK." + " hello" * n}]}


def select(names):
    if names == ["all"]:
        names = ORDER
    steps = []
    for n in names:
        if n in PARTS:
            steps += PARTS[n]
        elif n in ALL_STEPS:
            steps.append(ALL_STEPS[n])
        else:
            raise SystemExit(f"{n}: not a part ({', '.join(PARTS)}) nor an id of the plan")
    return steps


def shown(argv):
    return " ".join(a if a and " " not in a else json.dumps(a) for a in ["python3" if argv[0] == sys.executable else argv[0], *argv[1:]])


def dry_run(steps, date, out=print):
    for step in steps:
        argv = command(step, date)
        out(f"== {step['id']}: {shown(argv)}")
        if step["kind"] == "window":
            body = window_body(step["model"], 3)
            out(f"   POST {OPENROUTER}/chat/completions {json.dumps(body).replace('hello hello hello', 'hello × 1,200,000')}"
                " (refused by OpenRouter itself, not billed). Dry run: nothing sent.")
            continue
        p = subprocess.run([*argv, "--dry-run"], cwd=ROOT, capture_output=True, text=True, timeout=120,
                           env={k: v for k, v in os.environ.items() if k not in ("CACHE_PROBE_KEY", "META_API_KEY")})
        text = (p.stdout + p.stderr).strip()
        if step["kind"] == "openrouter":
            text = "\n".join(text.splitlines()[:2])  # the plan and the address; the body is the probe's usual one
        out("\n".join("   " + line for line in text.splitlines()))
        if p.returncode:
            raise SystemExit(f"{step['id']}: its dry run failed")


# --- --go: the owner's night only --------------------------------------------------------------------------------

def keychain(item):
    return subprocess.run(["security", "find-generic-password", "-a", os.environ["USER"], "-s", item, "-w"],
                          check=True, capture_output=True, text=True).stdout.strip()


def openrouter_get(path, key):
    import urllib.request
    req = urllib.request.Request(OPENROUTER + path, headers={"Authorization": "Bearer " + key, "User-Agent": "groundtruth"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def started(step, date):
    f = folders(date)
    folder = f["or"] if step["kind"] == "openrouter" else (os.path.join(f["own"], "smoke") if step["id"].startswith("S") else f["own"])
    logs = os.path.join(ROOT, folder, "logs")
    raw = [x for x in (os.listdir(os.path.join(ROOT, folder)) if os.path.isdir(os.path.join(ROOT, folder)) else [])
           if x == step["id"] + ".jsonl" or x.startswith(step["id"] + "-20")]
    return logs, os.path.exists(os.path.join(logs, step["id"] + ".pid")) or bool(raw)


def go(steps, date):
    env = {k: v for k, v in os.environ.items() if k not in ("CACHE_PROBE_KEY", "META_API_KEY")}
    or_key = None
    if any(s["kind"] in ("openrouter", "window") for s in steps):
        or_key = keychain(KEYCHAIN["OPENROUTER"])
        usage = openrouter_get("/key", or_key).get("data", {}).get("usage") or 0
        print(f"OpenRouter key: {usage:.2f} USD used (stop at {MONEY_STOP:.2f})")
        if usage >= MONEY_STOP:
            raise SystemExit("the money stop is reached: nothing started")
    for i, step in enumerate(steps):
        argv = command(step, date)
        logs, done = started(step, date)
        if done and step["kind"] in ("probe", "openrouter"):
            print(f"{step['id']}: started once already (a pid file or a raw file exists): not started again")
            continue
        os.makedirs(logs, exist_ok=True)
        child = dict(env)
        if step["kind"] in ("openrouter", "window"):
            if step["kind"] == "openrouter":
                ok = openrouter_get(f"/models/{step['model']}/endpoints", or_key).get("data", {}).get("endpoints")
                if not ok:
                    print(f"{step['id']}: {step['model']} is no longer offered: written down, not run")
                    continue
            child["CACHE_PROBE_KEY"] = or_key
        if step.get("harness") == "muse":
            child["META_API_KEY"] = keychain(KEYCHAIN["META_API_KEY"])
        if step["kind"] in ("probe", "openrouter"):
            with open(os.path.join(logs, step["id"] + ".log"), "a") as log:
                p = subprocess.Popen(["nohup", "caffeinate", "-i", *argv], cwd=ROOT, env=child, stdout=log,
                                     stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True)
            with open(os.path.join(logs, step["id"] + ".pid"), "w") as f:
                f.write(f"{p.pid}\n")
            line = f"{step['id']} pid {p.pid} started {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} {step.get('model')}"
            with open(os.path.join(logs, "launches.txt"), "a") as f:
                f.write(line + "\n")
            print(line)
            nxt = steps[i + 1] if i + 1 < len(steps) else None
            if nxt and nxt["kind"] in ("probe", "openrouter"):
                time.sleep(SPACING.get(step.get("harness"), 15))
        else:
            print(f"== {step['id']}: {shown(argv)}", flush=True)
            code = subprocess.run(["caffeinate", "-i", *argv], cwd=ROOT, env=child).returncode
            if step["kind"] == "window" and code == 3:
                print("a window request was answered: the list ends here, the next one waits for a decision")
                return


def window(model, date):
    """One window request straight to OpenRouter (the owner's go only): the answer appended to windows.jsonl."""
    sys.path.insert(0, os.path.join(ROOT, "harness"))
    import limits as L
    out = os.path.join(ROOT, folders(date)["or"], "windows.jsonl")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    if os.path.exists(out) and any(json.loads(x)["model"] == model for x in open(out) if x.strip()):
        raise SystemExit(f"{model}: its window request was sent already")
    L.BASE, L.KEY = OPENROUTER, os.environ["CACHE_PROBE_KEY"]
    at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    code, data, secs = L.post("/chat/completions", window_body(model), timeout=900)
    row = {"kind": "context", "model": model, "n": 1_200_000, "status": code, "seconds": round(secs, 1),
           "promptTokens": L.prompt_tokens("chat", data) if code == 200 else None,
           "message": None if code == 200 else L.message(data),
           "metadata": (data.get("error") or {}).get("metadata") if isinstance(data.get("error"), dict) else None, "at": at}
    with open(out, "a") as f:
        f.write(json.dumps(row) + "\n")
    print(json.dumps(row)[:800])
    if code == 200:
        sys.exit(3)


# Every-day folders of the clients: their modification times are read (stat only, nothing opened) before and after the
# smoke runs, and must not change.
EVERYDAY = ["~/.claude", "~/.claude.json", "~/.codex", "~/.devin", "~/.config/devin", "~/.local/share/devin",
            "~/.config/muse", "~/.local/share/muse"]


def mtimes(user_home=None):
    home = user_home or os.path.expanduser("~")
    out = {}
    for d in EVERYDAY:
        p = home + d[1:]
        out[d] = os.stat(p).st_mtime if os.path.exists(p) else None
    return out


def untouched(date, save, user_home=None):
    path = os.path.join(ROOT, folders(date)["own"], "logs", "everyday-mtimes.json")
    now = mtimes(user_home)
    if save:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(now, f)
        print(f"saved the modification times of {len(now)} everyday folders")
        return True
    with open(path) as f:
        before = json.load(f)
    changed = [d for d in EVERYDAY if before.get(d) != now.get(d)]
    print("unchanged: every everyday folder" if not changed else "CHANGED: " + ", ".join(changed))
    return not changed


def main(argv=None):
    ap = argparse.ArgumentParser(description="The run plan of docs/own-clients.md, section 4")
    ap.add_argument("--date", required=True, help="the night's date, YYYY-MM-DD: names the results folders")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="print every command and each tool's own dry run; send nothing")
    mode.add_argument("--go", action="store_true", help="run them (the owner's go only)")
    ap.add_argument("what", nargs="+", help="parts or ids (all = every part in the night's order); "
                                             "or: untouched --save|--compare; or: window <model>")
    ap.add_argument("--save", action="store_true")
    ap.add_argument("--compare", action="store_true")
    a = ap.parse_args(argv)
    if a.what[0] == "untouched":
        if not (a.save or a.compare):
            raise SystemExit("untouched: --save before the smoke runs, --compare after")
        sys.exit(0 if untouched(a.date, a.save) else 1)
    if a.what[0] == "window":
        window(a.what[1], a.date)
        return
    steps = select(a.what)
    if a.dry_run:
        dry_run(steps, a.date)
        print(f"Dry run of {len(steps)} steps: nothing run, nothing sent.")
    elif a.go:
        go(steps, a.date)
    else:
        for s in steps:
            print(f"{s['id']}: {shown(command(s, a.date))}")
        print("Listed only: --dry-run runs each tool's dry run, --go runs them.")


if __name__ == "__main__":
    main()
