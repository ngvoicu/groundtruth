#!/usr/bin/env python3
"""The run plan of docs/own-clients.md, section 4, narrowed for the first night, with the parity pairs of Provimux's
client-parity.md, section 7. The owner's steps are docs/own-clients-RUN.md.

    python3 harness/night.py --date 2026-11-23 --dry-run all            # every command, each tool's own dry run
    python3 harness/night.py --date 2026-11-23 --go smoke               # the owner's go only
    python3 harness/night.py --date 2026-11-23 untouched --save|--compare|--accept-keychain-added
    python3 harness/night.py --date 2026-11-23 smoke-reviewed           # after reading the smoke results
    python3 harness/night.py --date 2026-11-23 stop <id>                # stop one detached run
    python3 harness/night.py --date 2026-11-23 --go window <model>      # one OpenRouter window request

Parts, in the night's order: openrouter (OR1 - OR5, straight to OpenRouter), windows (OW1 - OW9), smoke (S1 - S4, S3b,
SP), claude (CC1 - CC4 and the pi runs of pairs CC-1, CC-2), claude-5m (CC5 - CC8), codex (CX1 - CX6 and the pi runs
of CX-1 to CX-3), codex-plain (CX-S, the plain probe through Provimux), devin (DV1 - DV17, DV9d and the pi runs of
DV-1 to DV-4), devin-terra-pi (DV-6's pi run, only if S3b showed cached tokens), muse (MC1 - MC3 and MC-1's pi run
without the 24 h rule), muse-rule (MC-1's pi run with it).

Not in the first night: no input-limit walk through an own client (harness/client_limits.py is not yet trusted), no
Antigravity run, no second run of pair CX-3, no second OpenRouter run at 8,000 tokens.

Nothing is sent without --go. --dry-run prints each command and runs the tool's own --dry-run, which runs no client
and sends nothing. --go refuses `all`, refuses the smoke runs with anything else, refuses a login's part until the
smoke results were reviewed, and first compares the everyday folders and the Keychain items with the snapshot taken
before the logins: any difference stops it and says what changed. A step already done (a raw file, a pid file, a
window row) is skipped on a rerun. Keys come from the Keychain only at --go, straight into the one process that
needs them, and are never printed or written (their fingerprints are left for the commit scan). OpenRouter is
reached directly, never through a proxy of the environment.
"""
import argparse
import glob
import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import scan_secrets  # noqa: E402

OPENROUTER = "https://openrouter.ai/api/v1"
PROVIMUX = "http://127.0.0.1:8317/v1"  # the owner's proxy: only the plain-probe pair CX-S goes there
# The owner's Keychain items for this campaign (generic passwords, account = the user name). Read only, at --go.
KEYCHAIN = {"META_API_KEY": "groundtruth META_API_KEY", "OPENROUTER": "groundtruth OPENROUTER_API_KEY",
            "PROVIMUX": "groundtruth PROVIMUX_KEY"}
MONEY_STOP = 4.00  # USD on the campaign's OpenRouter key (its own limit is 5)
STD65 = "10m,15m,20m,25m,30m,40m,50m,60m,65m,75m,90m,120m"
PROXY_VARS = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY", "http_proxy", "https_proxy", "all_proxy", "no_proxy",
              "NODE_USE_ENV_PROXY", "GLOBAL_AGENT_HTTP_PROXY", "GLOBAL_AGENT_HTTPS_PROXY")
SECRETS = ("CACHE_PROBE_KEY", "META_API_KEY", "OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY")


def probe(id_, harness, model, ages=None, schedule=None, filler=None, env=None, extra=(), pair=None):
    args = ["--harness", harness, "--model", model, "--replicas", "3", "--label", id_]
    args += ["--ages", ages] if ages else ["--schedule", schedule or "std"]
    if filler:
        args += ["--filler", filler]
    for k, v in (env or {}).items():
        args += ["--client-env", f"{k}={v}"]
    args += list(extra)
    return {"id": id_, "kind": "probe", "harness": harness, "model": model, "args": args, "pair": pair}


def twin(own, pi_model, pair):
    """The pi-through-Provimux run of a pair: the own client's schedule, ages and filler, started beside it."""
    a = own["args"]
    keep = []
    for flag in ("--ages", "--schedule", "--filler"):
        if flag in a:
            keep += [flag, a[a.index(flag) + 1]]
    step = {"id": "P-" + own["id"], "kind": "probe", "harness": "pi", "model": pi_model, "pair": pair,
            "args": ["--harness", "pi", "--model", pi_model, "--replicas", "3", "--label", "P-" + own["id"], *keep]}
    own["pair"] = pair
    return step


def smoke(id_, harness, model, filler=None):
    """Baseline and the control checked at 30 s; the output kept, redacted, outside the repository."""
    return {"id": id_, "kind": "smoke", "harness": harness, "model": model,
            "args": ["--harness", harness, "--model", model, "--replicas", "0", "--waves", "1", "--label", id_,
                     "--schedule", "std", *(["--filler", filler] if filler else [])]}


CC = [probe(f"CC{i}", "claude", m, ages=STD65, filler="list") for i, m in enumerate(
    ["claude-fable-5-2", "claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"], 1)]
CX = [probe(f"CX{i}", "codex", m, schedule="long") for i, m in enumerate(
    ["gpt-6.2-sol", "gpt-6.2-astra", "gpt-6.1-sol", "gpt-6.1-terra", "gpt-6-astra", "gpt-6-luna"], 1)]
DEVIN = [("DV1", "claude-opus-5-5-low", "std"), ("DV2", "claude-sonnet-5-5-low", "std"), ("DV3", "claude-haiku-5-5-low", "std"),
         ("DV4", "gpt-6-1-sol-low", "std"), ("DV5", "gpt-6-1-terra-low", "std"), ("DV6", "gpt-6-astra-low", "std"),
         ("DV7", "gpt-6-luna-low", "std"),
         ("DV8", "deepseek-v4-1-flash-1017-low", "long"), ("DV9", "glm-5-3-low", "std"), ("DV10", "kimi-k3-1-pro-low", "long"),
         ("DV11", "nemotron-3-5-super-none", "long"),
         ("DV12", "deepseek-v4-pro-low", "std"), ("DV13", "gemini-4-argon-low", "std"), ("DV14", "grok-4-7-low", "std"),
         ("DV15", "kimi-k3-low", "std"), ("DV16", "muse-wonder-1-0-low", "std"), ("DV17", "swe-2-medium", "std")]
DV = {i: probe(i, "devin", m, schedule=s) for i, m, s in DEVIN}
MC = [probe(f"MC{i}", "muse", m) for i, m in enumerate(["muse-wonder-1.0", "muse-ember-1.0", "muse-spark-1.3"], 1)]
P_MC1B = twin(dict(MC[0]), "muse-wonder-1.0", "MC-1 (with the 24 h rule)")
P_MC1B["id"] = "P-MC1b"
P_MC1B["args"][P_MC1B["args"].index("--label") + 1] = "P-MC1b"


def with_twins(runs, twins):
    out = []
    for r in runs:
        out.append(r)
        if r["id"] in twins:
            out.append(twin(r, *twins[r["id"]]))
    return out


PARTS = {
    "openrouter": [{"id": f"OR{i}", "kind": "openrouter", "model": m} for i, m in enumerate(
        ["openai/gpt-6-astra", "openai/gpt-6-luna", "meta/muse-spark-1.3", "deepseek/deepseek-v4.1-flash",
         "z-ai/glm-5.3-flash"], 1)],
    # Cheapest first; an answer instead of a refusal ends the list.
    "windows": [{"id": f"OW{i}", "kind": "window", "model": m} for i, m in enumerate(
        ["anthropic/claude-haiku-5.5", "anthropic/claude-opus-5.5", "anthropic/claude-sonnet-5.5",
         "deepseek/deepseek-v4.1-flash", "google/gemini-4-argon", "meta/muse-wonder", "moonshotai/kimi-k3.1-pro",
         "openai/gpt-6.1-sol", "openai/gpt-6.1-terra"], 1)],
    "smoke": [smoke("S1", "claude", "claude-haiku-5-5", filler="list"), smoke("S2", "codex", "gpt-6-luna"),
              smoke("S3", "devin", "claude-haiku-5-5-low"), smoke("S3b", "devin", "gpt-6-1-terra-low"),
              smoke("S4", "muse", "muse-spark-1.3"), smoke("SP", "pi", "gpt-6-luna")],
    "claude": with_twins(CC, {"CC3": ("claude-sonnet-5-5", "CC-1"), "CC4": ("claude-haiku-5-5", "CC-2")}),
    "claude-5m": [probe(f"CC{i}", "claude", m, ages="10m,15m", filler="list", env={"CLAUDE_CODE_PROMPT_CACHE_TTL": "5m"})
                  for i, m in enumerate(["claude-fable-5-2", "claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"], 5)],
    "codex": with_twins(CX, {"CX1": ("gpt-6.2-sol", "CX-3"), "CX3": ("gpt-6.1-sol", "CX-2"),
                             "CX4": ("gpt-6.1-terra", "CX-1")}),
    # CX-S (a): the plain probe through Provimux on GPT-6.1 Terra, to 30 minutes. CX-S (b), a request shaped like
    # pi's, needs a probe change that is not built: not in the plan.
    "codex-plain": [{"id": "CXS-a", "kind": "proxy-plain", "model": "gpt-6.1-terra", "pair": "CX-S (a)"}],
    "devin": with_twins([DV[i] for i, _, _ in DEVIN] + [probe("DV9d", "devin", "glm-5-3-low", schedule="std",
                                                              extra=["--devin-daemon"], pair="DV-5")],
                        {"DV1": ("devin/claude-opus-5-5-low", "DV-1"), "DV9": ("devin/glm-5-3-low", "DV-2"),
                         "DV11": ("devin/nemotron-3-5-super-none", "DV-3"), "DV14": ("devin/grok-4-7-low", "DV-4")}),
    "devin-terra-pi": [twin(dict(DV["DV5"]), "devin/gpt-6-1-terra-low", "DV-6")],
    "muse": with_twins(MC, {"MC1": ("muse-wonder-1.0", "MC-1 (without the 24 h rule)")}),
    "muse-rule": [P_MC1B],
}
ORDER = ["openrouter", "windows", "smoke", "claude", "claude-5m", "codex", "codex-plain", "devin", "devin-terra-pi",
         "muse", "muse-rule"]
LOGIN_PARTS = {"claude", "claude-5m", "codex", "codex-plain", "devin", "devin-terra-pi", "muse", "muse-rule"}
ALL_STEPS = {s["id"]: s for part in ORDER for s in PARTS[part]}
PART_OF = {s["id"]: part for part in ORDER for s in PARTS[part]}
POSITION = {}
for _part in ORDER:
    for _s in PARTS[_part]:
        POSITION.setdefault(_s["id"], len(POSITION))
for _id in list(POSITION):
    if _id.startswith("P-") and _id[2:] in POSITION and PART_OF[_id] != PART_OF[_id[2:]]:
        POSITION[_id] = POSITION[_id[2:]] + 0.5  # a pair's pi run starts beside its own-client run
# Seconds between two detached starts (a pair's two runs start within 15 s; Devin's as on 8 November).
SPACING = {"devin": 20}


def folders(date):
    own = os.path.join("results", f"own-clients-{date}")
    return {"own": own, "smoke": os.path.join(own, "smoke"), "or": os.path.join("results", f"openrouter-direct-{date}")}


def folder_of(step, date):
    f = folders(date)
    return f["or"] if step["kind"] in ("openrouter", "window") else f["smoke"] if step["kind"] == "smoke" else f["own"]


def night_dir(date, client_home=None):
    base = client_home or os.environ.get("GROUNDTRUTH_CLIENT_HOME")
    return os.path.join(base, f"night-{date}") if base else f"<client-home>/night-{date}"


def command(step, date, client_home=None):
    """The argument list of a step, run from the repository's root."""
    folder = folder_of(step, date)
    if step["kind"] == "probe":
        return [sys.executable, "harness/probe.py", *step["args"], "--out", folder]
    if step["kind"] == "smoke":
        return [sys.executable, "harness/probe.py", *step["args"], "--out", folder,
                "--keep-raw", os.path.join(night_dir(date, client_home), "raw", step["id"])]
    if step["kind"] in ("openrouter", "proxy-plain"):
        base = OPENROUTER if step["kind"] == "openrouter" else PROVIMUX
        ages = ["--schedule", "quick", "--ages", "15m,20m,25m,30m"] if step["kind"] == "proxy-plain" else []
        return ["node", "src/cli.ts", "--base-url", base, "--format", "responses", "--model", step["model"], *ages,
                "--stop-on-refusal", "--label", step["id"], "--out", folder,
                "--usage-log", os.path.join(folder, "logs", step["id"] + ".usage.jsonl")]
    if step["kind"] == "window":
        return [sys.executable, "harness/night.py", "--date", date, "--go", "window", step["model"]]
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
            steps += [s for s in PARTS[n] if s not in steps]
        elif n in ALL_STEPS:
            steps.append(ALL_STEPS[n])
        else:
            raise SystemExit(f"{n}: not a part ({', '.join(ORDER)}) nor an id of the plan")
    return sorted(steps, key=lambda s: POSITION[s["id"]])


def shown(argv):
    return " ".join(a if a and " " not in a else json.dumps(a) for a in ["python3" if argv[0] == sys.executable else argv[0], *argv[1:]])


def clean_env(extra=None):
    """The launcher's children: no key, no proxy of the shell, then what this step needs."""
    env = {k: v for k, v in os.environ.items() if k not in SECRETS and k not in PROXY_VARS}
    env.update(extra or {})
    return env


def dry_run(steps, date, out=print):
    for step in steps:
        argv = command(step, date)
        pair = f"  [pair {step['pair']}]" if step.get("pair") else ""
        out(f"== {step['id']}{pair}: {shown(argv)}")
        if step["kind"] == "window":
            body = window_body(step["model"], 3)
            out(f"   POST {OPENROUTER}/chat/completions {json.dumps(body).replace('hello hello hello', 'hello × 1,200,000')}"
                " (direct, no proxy; refused by OpenRouter itself, not billed). Dry run: nothing sent.")
            continue
        p = subprocess.run([*argv, "--dry-run"], cwd=ROOT, capture_output=True, text=True, timeout=120, env=clean_env())
        text = (p.stdout + p.stderr).strip()
        if step["kind"] in ("openrouter", "proxy-plain"):
            text = "\n".join(text.splitlines()[:2])  # the plan and the address; the body is the probe's usual one
        out("\n".join("   " + line for line in text.splitlines()))
        if p.returncode:
            raise SystemExit(f"{step['id']}: its dry run failed")


# --- the everyday state: folders (recursively) and the Keychain's item names --------------------------------------

EVERYDAY = ["~/.claude", "~/.claude.json", "~/.codex", "~/.devin", "~/.config/devin", "~/.local/share/devin",
            "~/.config/muse", "~/.local/share/muse", "~/.muse", "~/.pi"]


def snapshot_files(user_home=None):
    """Path, size and modification time of every file, folder and link under the everyday folders (nothing read)."""
    home = user_home or os.path.expanduser("~")
    out = {}
    for d in EVERYDAY:
        top = home + d[1:]
        if not os.path.lexists(top):
            continue
        st = os.lstat(top)
        out[d] = [st.st_size, st.st_mtime_ns]
        if os.path.isdir(top) and not os.path.islink(top):
            for root, dirs, files in os.walk(top, followlinks=False):
                for name in dirs + files:
                    p = os.path.join(root, name)
                    st = os.lstat(p)
                    out[d + "/" + os.path.relpath(p, top)] = [st.st_size, st.st_mtime_ns]
    return out


def keychain_items(run=None):
    """The Keychain's items by class, service, account, label and modification date: `security dump-keychain`
    without -d lists attributes only, never a secret."""
    run = run or (lambda: subprocess.run(["security", "dump-keychain"], capture_output=True, text=True, timeout=120).stdout)
    items, cur = [], None
    for line in run().splitlines():
        line = line.strip()
        if line.startswith("keychain:"):
            if cur:
                items.append(cur)
            cur = {}
        elif cur is not None and line.startswith("class:"):
            cur["class"] = line.split(":", 1)[1].strip()
        elif cur is not None and "=" in line and line.startswith('"'):
            key = line.split('"')[1]
            if key in ("svce", "acct", "labl", "mdat", "srvr"):
                cur[key] = line.split("=", 1)[1].strip()
    if cur:
        items.append(cur)
    return sorted(json.dumps(i, sort_keys=True) for i in items)


def everyday_path(date):
    return os.path.join(night_dir(date), "everyday-before.json")


def compare_everyday(before, now):
    """What changed, as lines (empty: nothing)."""
    lines = []
    bf, nf = before["files"], now["files"]
    for p in sorted(set(bf) | set(nf)):
        if p not in nf:
            lines.append(f"removed: {p}")
        elif p not in bf:
            lines.append(f"added: {p}")
        elif bf[p] != nf[p]:
            lines.append(f"changed: {p}")
    accepted = set(before.get("keychain_accepted", []))
    bk, nk = set(before["keychain"]), set(now["keychain"])
    for item in sorted(bk - nk):
        lines.append(f"Keychain item removed or changed: {describe_item(item)}")
    for item in sorted(nk - bk - accepted):
        lines.append(f"Keychain item added or changed: {describe_item(item)}")
    return lines


def describe_item(item):
    d = json.loads(item)
    return ", ".join(f"{k} {d[k]}" for k in ("class", "svce", "labl", "srvr") if k in d)


def untouched(date, mode, user_home=None, lister=None, out=print):
    path = everyday_path(date)
    if path.startswith("<"):
        raise SystemExit("untouched: GROUNDTRUTH_CLIENT_HOME is not set")
    now = {"files": snapshot_files(user_home), "keychain": keychain_items(lister)}
    if mode == "save":
        if os.path.exists(path):
            raise SystemExit(f"untouched: a snapshot of {date} exists already; it is taken once, before the logins")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(now, f)
        os.chmod(path, 0o600)
        out(f"saved: {len(now['files'])} paths under the everyday folders, {len(now['keychain'])} Keychain items")
        return True
    with open(path) as f:
        before = json.load(f)
    changed = compare_everyday(before, now)
    if mode == "accept":
        added = sorted(set(now["keychain"]) - set(before["keychain"]))
        if [c for c in changed if not c.startswith("Keychain item added")]:
            out("\n".join(changed))
            raise SystemExit("untouched: something else changed too; nothing accepted")
        before["keychain_accepted"] = sorted(set(before.get("keychain_accepted", [])) | set(added))
        with open(path, "w") as f:
            json.dump(before, f)
        out("accepted as the night's own: " + ("; ".join(describe_item(i) for i in added) or "nothing"))
        return True
    out("unchanged: every everyday folder and Keychain item" if not changed else "CHANGED:\n" + "\n".join(changed))
    return not changed


# --- --go: the owner's night only -----------------------------------------------------------------------------------

def keychain(item):
    return subprocess.run(["security", "find-generic-password", "-a", os.environ["USER"], "-s", item, "-w"],
                          check=True, capture_output=True, text=True).stdout.strip()


# Direct: no proxy of the environment (HTTPS_PROXY could name the owner's proxy), ever.
DIRECT = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def openrouter_get(path, key):
    req = urllib.request.Request(OPENROUTER + path, headers={"Authorization": "Bearer " + key, "User-Agent": "groundtruth"})
    with DIRECT.open(req, timeout=60) as r:
        return json.load(r)


def openrouter_post(path, body, key, timeout=900):
    req = urllib.request.Request(OPENROUTER + path, data=json.dumps(body).encode(),
                                 headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    t = time.time()
    try:
        with DIRECT.open(req, timeout=timeout) as r:
            return r.status, json.loads(r.read() or b"{}"), time.time() - t
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(raw), time.time() - t
        except ValueError:
            return e.code, {"raw": raw[:2000]}, time.time() - t


def done(step, date):
    """A step already done or running: its raw file, its pid file, its window row."""
    folder = os.path.join(ROOT, folder_of(step, date))
    if step["kind"] == "window":
        rows = os.path.join(folder, "windows.jsonl")
        if not os.path.exists(rows):
            return False
        with open(rows) as f:
            return any(json.loads(x).get("model") == step["model"] for x in f if x.strip())
    if os.path.exists(os.path.join(folder, "logs", step["id"] + ".pid")):
        return True
    return os.path.exists(os.path.join(folder, step["id"] + ".jsonl")) or bool(glob.glob(os.path.join(folder, step["id"] + "-20*.json")))


def estimate(step, key, get):
    """The most an OpenRouter cache run can cost: 90 requests of 3,000 prompt tokens and 32 output tokens at the dearest
    endpoint's price (a cache write billed as input). A window request is refused, so free."""
    if step["kind"] != "openrouter":
        return 0.0
    eps = (get(f"/models/{step['model']}/endpoints", key).get("data") or {}).get("endpoints") or []
    if not eps:
        return None
    price_in = max(float((e.get("pricing") or {}).get("prompt") or 0) for e in eps)
    price_out = max(float((e.get("pricing") or {}).get("completion") or 0) for e in eps)
    return round(90 * (3000 * price_in + 32 * price_out), 4)


def committed(date, steps_running):
    """The estimates of OpenRouter runs started and not finished (no result file yet)."""
    total = 0.0
    folder = os.path.join(ROOT, folders(date)["or"])
    for path in glob.glob(os.path.join(folder, "logs", "*.estimate")):
        rid = os.path.basename(path)[:-len(".estimate")]
        if not glob.glob(os.path.join(folder, rid + "-20*.json")):
            with open(path) as f:
                total += float(f.read().strip() or 0)
    return total + sum(steps_running)


def budget(step, key, date, get):
    """Checked before every OpenRouter request or run: what the key has spent, plus what runs already started may
    still spend, plus this one's worst case, must stay under the stop. An unknown spend stops."""
    usage = (get("/key", key).get("data") or {}).get("usage")
    if not isinstance(usage, (int, float)):
        raise SystemExit("OpenRouter: the key's spend is unknown: nothing started")
    est = estimate(step, key, get)
    if est is None:
        return None  # no longer offered
    owed = committed(date, [])
    if usage + owed + est > MONEY_STOP:
        raise SystemExit(f"{step['id']}: {usage:.2f} USD spent + {owed:.2f} committed + {est:.2f} for this run would pass "
                         f"the {MONEY_STOP:.2f} USD stop: not started")
    return est


def reviewed_path(date):
    return os.path.join(night_dir(date), "smoke-reviewed")


def guard(names, steps, date):
    parts = {PART_OF[s["id"]] for s in steps}
    if names == ["all"]:
        raise SystemExit("--go all: no; name the parts in the order of docs/own-clients-RUN.md")
    if "smoke" in parts and len(parts) > 1:
        raise SystemExit("--go: the smoke runs go alone; read their results, then `smoke-reviewed`, then the rest")
    if parts & LOGIN_PARTS and not os.path.exists(reviewed_path(date)):
        raise SystemExit("--go: a login's runs wait until the smoke results were read (`night.py --date ... smoke-reviewed`)")
    if night_dir(date).startswith("<"):
        raise SystemExit("--go: GROUNDTRUTH_CLIENT_HOME is not set")


def last_event(path):
    try:
        with open(path) as f:
            lines = [x for x in f if x.strip()]
        return json.loads(lines[-1]) if lines else None
    except (OSError, ValueError):
        return None


def go(steps, date, popen=None, run=None, sleep=None, get=None, check_everyday=True, out=print):
    popen, run = popen or subprocess.Popen, run or subprocess.run
    sleep, get = sleep or time.sleep, get or openrouter_get
    if check_everyday:
        if not untouched(date, "compare", out=out):
            raise SystemExit("the everyday folders or the Keychain changed since the snapshot: the night stops here")
    keys = {}

    def key(name):
        if name not in keys:
            keys[name] = keychain(KEYCHAIN[name])
            scan_secrets.remember(keys[name], name)
        return keys[name]
    failed = []
    for i, step in enumerate(steps):
        if done(step, date):
            out(f"{step['id']}: done or running already (a raw file, a pid file or a window row): skipped")
            continue
        argv = command(step, date)
        extra = {}
        if step["kind"] in ("openrouter", "window"):
            est = budget(step, key("OPENROUTER"), date, get)
            if est is None:
                out(f"{step['id']}: {step['model']} is no longer offered: written down, not run")
                continue
            extra["CACHE_PROBE_KEY"] = key("OPENROUTER")
        if step["kind"] == "proxy-plain":
            extra["CACHE_PROBE_KEY"] = key("PROVIMUX")
        if step.get("harness") == "muse":
            extra["META_API_KEY"] = key("META_API_KEY")
        env = clean_env(extra)
        logs = os.path.join(ROOT, folder_of(step, date), "logs")
        os.makedirs(logs, exist_ok=True)
        if step["kind"] in ("smoke", "window"):
            # In the foreground, one after the other: the launcher waits for each, and a failure stops it.
            out(f"== {step['id']}: {shown(argv)}")
            code = run(["caffeinate", "-i", *argv], cwd=ROOT, env=env).returncode
            if step["kind"] == "window":
                if code == 3:
                    out("a window request was answered: the list ends here, the next one waits for a decision")
                    return failed
                if code:
                    raise SystemExit(f"{step['id']}: exited {code}: the night stops here")
                continue
            ev = last_event(os.path.join(ROOT, folder_of(step, date), step["id"] + ".jsonl"))
            if code or not ev or ev.get("event") != "done":
                failed.append(step["id"])
                out(f"{step['id']}: exit {code}, last event {json.dumps(ev)[:200] if ev else 'none'}")
            continue
        with open(os.path.join(logs, step["id"] + ".log"), "a") as log:
            p = popen(["nohup", "caffeinate", "-i", *argv], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
                      stdin=subprocess.DEVNULL, start_new_session=True)
        with open(os.path.join(logs, step["id"] + ".pid"), "w") as f:
            f.write(f"{p.pid}\n")
        if step["kind"] == "openrouter":
            with open(os.path.join(logs, step["id"] + ".estimate"), "w") as f:
                f.write(f"{est}\n")
        line = f"{step['id']} pid {p.pid} started {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} {step.get('model')}"
        with open(os.path.join(logs, "launches.txt"), "a") as f:
            f.write(line + "\n")
        out(line)
        nxt = steps[i + 1] if i + 1 < len(steps) else None
        if nxt and nxt["kind"] in ("probe", "openrouter", "proxy-plain"):
            sleep(SPACING.get(step.get("harness"), 15))
    if failed:
        raise SystemExit(f"smoke runs that did not end with `done`: {', '.join(failed)}: read them before going on")
    return failed


def window(model, date, live, out=print, post=None, get=None):
    """One window request straight to OpenRouter (never through a proxy): only with --go, inside the money stop."""
    body = window_body(model)
    if not live:
        out(f"POST {OPENROUTER}/chat/completions {json.dumps(window_body(model, 3)).replace('hello hello hello', 'hello × 1,200,000')}"
            " (direct). Not sent: add --go to send it.")
        return
    key = os.environ.get("CACHE_PROBE_KEY")
    if not key:
        raise SystemExit("window: run it through `night.py --go windows`, which reads the campaign's key")
    step = {"id": "window " + model, "kind": "window", "model": model}
    if budget(step, key, date, get or openrouter_get) is None:
        raise SystemExit(f"{model}: no longer offered")
    out_path = os.path.join(ROOT, folders(date)["or"], "windows.jsonl")
    if done(step, date):
        raise SystemExit(f"{model}: its window request was sent already")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    code, data, secs = (post or openrouter_post)("/chat/completions", body, key)
    sys.path.insert(0, HERE)
    import limits as L
    row = {"kind": "context", "model": model, "n": 1_200_000, "status": code, "seconds": round(secs, 1),
           "promptTokens": L.prompt_tokens("chat", data) if code == 200 else None,
           "message": None if code == 200 else L.message(data),
           "metadata": (data.get("error") or {}).get("metadata") if isinstance(data.get("error"), dict) else None, "at": at}
    with open(out_path, "a") as f:
        f.write(json.dumps(row) + "\n")
    out(json.dumps(row)[:800])
    if code == 200:
        sys.exit(3)


def stop(step_id, date, ps=None, killpg=None, out=print):
    """Stop one detached run: its pid file in its own folder, the process checked to be that run before the signal."""
    step = ALL_STEPS.get(step_id)
    if not step:
        raise SystemExit(f"{step_id}: not an id of the plan")
    pid_file = os.path.join(ROOT, folder_of(step, date), "logs", step_id + ".pid")
    if not os.path.exists(pid_file):
        raise SystemExit(f"{step_id}: no pid file at {os.path.relpath(pid_file, ROOT)}")
    with open(pid_file) as f:
        pid = int(f.read().strip())
    def group(p):
        lines = subprocess.run(["ps", "-ax", "-o", "pgid=,command="], capture_output=True, text=True).stdout.splitlines()
        return "\n".join(x.split(None, 1)[1] for x in lines if x.split(None, 1)[0] == str(p) and len(x.split(None, 1)) > 1)
    seen = (ps or group)(pid)
    if f"--label {step_id} " not in seen + " ":
        raise SystemExit(f"{step_id}: process group {pid} is not this run (it ended, or the pid was reused): nothing sent")
    (killpg or os.killpg)(pid, signal.SIGTERM)
    out(f"{step_id}: process group {pid} stopped")


def main(argv=None):
    ap = argparse.ArgumentParser(description="The run plan of docs/own-clients.md, section 4")
    ap.add_argument("--date", required=True, help="the night's date, YYYY-MM-DD: names the results folders")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="print every command and each tool's own dry run; send nothing")
    mode.add_argument("--go", action="store_true", help="run them (the owner's go only)")
    ap.add_argument("what", nargs="+", help="parts or ids (all = every part, for a dry run); or: untouched, "
                                             "smoke-reviewed, stop <id>, window <model>")
    ap.add_argument("--save", action="store_true")
    ap.add_argument("--compare", action="store_true")
    ap.add_argument("--accept-keychain-added", action="store_true")
    a = ap.parse_args(argv)
    head = a.what[0]
    if head == "untouched":
        m = "save" if a.save else "accept" if a.accept_keychain_added else "compare" if a.compare else None
        if not m:
            raise SystemExit("untouched: --save (before the logins), --compare, or --accept-keychain-added (after them)")
        sys.exit(0 if untouched(a.date, m) else 1)
    if head == "smoke-reviewed":
        os.makedirs(night_dir(a.date), exist_ok=True)
        with open(reviewed_path(a.date), "w") as f:
            f.write(time.strftime("%Y-%m-%dT%H:%M:%SZ\n", time.gmtime()))
        print("the smoke results are marked as read: the logins' parts may start")
        return
    if head == "stop":
        stop(a.what[1], a.date)
        return
    if head == "window":
        window(a.what[1], a.date, live=a.go)
        return
    steps = select(a.what)
    if a.dry_run:
        dry_run(steps, a.date)
        print(f"Dry run of {len(steps)} steps: nothing run, nothing sent.")
    elif a.go:
        guard(a.what, steps, a.date)
        go(steps, a.date)
    else:
        for s in steps:
            print(f"{s['id']}: {shown(command(s, a.date))}")
        print("Listed only: --dry-run runs each tool's dry run, --go runs them.")


if __name__ == "__main__":
    main()
