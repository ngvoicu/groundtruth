#!/usr/bin/env python3
"""Build observed.json: every published measurement in one machine-readable file.

    python3 scripts/build_observed.py           # write observed.json
    python3 scripts/build_observed.py --check   # fail if observed.json is out of date

observed/manifest.json says which raw files count and what each one measured (route, model, request
options). Everything else in observed.json (dates, counts per age, the summary numbers) is computed here
from the raw files under results/, so the file can't drift from the data.
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "harness"))
from clients import same_model  # noqa: E402  (one rule for the probe's model_matches and for the manifest's model)
MANIFEST = "observed/manifest.json"
OUT = "observed.json"

ROUTES = {
    "anthropic-api": "Anthropic API key",
    "claude-subscription": "Claude Pro/Max login (the Claude Code subscription)",
    "codex-subscription": "ChatGPT plan through the Codex login",
    "devin": "Devin subscription",
    "meta-subscription": "Muse Code subscription key on Meta's Model API",
    "openai-api": "OpenAI API key",
    "openrouter": "OpenRouter API key",
    "antigravity": "Google Antigravity login",
}
CLIENTS = {
    "pi+cliproxyapi": "the pi coding agent through CLIProxyAPI: real sessions, resumed once (harness/probe.py)",
    "cliproxyapi": "plain HTTP requests through CLIProxyAPI (the TypeScript probe)",
    "direct": "plain HTTP requests straight to the vendor (the TypeScript probe)",
    "codex-cli": "OpenAI's Codex CLI (harness/probe.py)",
    "devin-cli": "the Devin CLI (harness/probe.py)",
    "muse-code": "Meta's Muse Code CLI (harness/probe.py)",
    "claude-code": "Anthropic's Claude Code (harness/probe.py)",
    "antigravity-cli": "Google's Antigravity CLI (harness/probe.py)",
}
HARNESS_CLIENT = {"pi": "pi+cliproxyapi", "codex": "codex-cli", "devin": "devin-cli", "muse": "muse-code",
                  "claude": "claude-code"}
# What each client and route is (docs/own-clients.md, section 3). providers.dev applies the rule: on an api_key route
# only direct runs count; on a login, for one value, the lowest kind present (direct, then own_client, then proxy).
CLIENT_KINDS = {
    "direct": "direct",
    "claude-code": "own_client", "codex-cli": "own_client", "devin-cli": "own_client", "muse-code": "own_client",
    "antigravity-cli": "own_client",
    "cliproxyapi": "proxy", "pi+cliproxyapi": "proxy",
}
ROUTE_KINDS = {
    "anthropic-api": "api_key", "openai-api": "api_key", "openrouter": "api_key",
    "claude-subscription": "login", "codex-subscription": "login", "devin": "login", "meta-subscription": "login",
    "antigravity": "login",
}
# The one route an own client may measure: its vendor's login.
OWN_CLIENT_ROUTE = {"claude-code": "claude-subscription", "codex-cli": "codex-subscription", "devin-cli": "devin",
                    "muse-code": "meta-subscription", "antigravity-cli": "antigravity"}
# Own-client limits rows: refused until harness/client_limits.py is trusted (the first night measures none).
OWN_CLIENT_LIMITS = False
# From this design on, an own-client run must record its state folder, its throwaway HOME and its empty working folder.
OWN_CLIENTS_SINCE = "2026-11-22"
ISOLATION = {"home": "dedicated", "HOME": "throwaway", "work": "temporary"}
UNIT = {"s": 1, "m": 60, "h": 3600}


def age_seconds(label):
    m = re.fullmatch(r"(\d+(?:\.\d+)?)([smh])", label)
    if not m:
        raise ValueError(f"bad age {label!r}")
    return round(float(m.group(1)) * UNIT[m.group(2)])


def age_label(seconds):
    for unit, size in (("h", 3600), ("m", 60)):
        if seconds % size == 0:
            return f"{seconds // size}{unit}"
        if unit == "m" and seconds % 30 == 0 and seconds >= 60:
            return f"{seconds / 60:g}m"
    return f"{seconds}s"


# The publication gate of an own-client night (docs/own-clients-RUN.md, "The morning"): nothing of a night (no run,
# no `excluded` entry, no raw file in a commit) is published until a person has audited its raw results, the Codex
# session files and the console logs, and written results/own-clients-<date>/AUDIT.md with exactly this first line.
# No symbolic link is accepted anywhere under results/own-clients-*: a file is the night's only where it lies.
AUDIT_FIRST_LINE = "# Own-client night audit: passed"
NIGHT_FOLDER = re.compile(r"^results/own-clients-(\d{4}-\d{2}-\d{2})(?:/|$)")
NIGHT_NAME = re.compile(r"own-clients-(\d{4}-\d{2}-\d{2})")


def night_links(root):
    """Every symbolic link under results/own-clients-* of `root` (the night folders themselves included), relative."""
    results, found = os.path.join(root, "results"), []
    if not os.path.isdir(results):
        return found
    for name in sorted(os.listdir(results)):
        top = os.path.join(results, name)
        if not name.startswith("own-clients-"):
            continue
        if os.path.islink(top):
            found.append(os.path.relpath(top, root))
            continue
        for d, dirs, files in os.walk(top, followlinks=False):
            found += [os.path.relpath(os.path.join(d, n), root) for n in dirs + files if os.path.islink(os.path.join(d, n))]
    return found


def audit_problem(root, date):
    """None when results/own-clients-<date>/AUDIT.md of `root` is a regular file whose first line is
    AUDIT_FIRST_LINE; else why not."""
    audit = os.path.join(root, "results", f"own-clients-{date}", "AUDIT.md")
    if os.path.islink(audit) or not os.path.isfile(audit):
        return f"the night own-clients-{date} has no AUDIT.md: nothing of it is published before its audit " \
               "(docs/own-clients-RUN.md, \"The morning\")"
    with open(audit, errors="replace") as f:
        first = f.readline().rstrip("\n")
    if first != AUDIT_FIRST_LINE:
        return f"results/own-clients-{date}/AUDIT.md does not begin with {AUDIT_FIRST_LINE!r}: the night's audit is " \
               "not passed"
    return None


def night_of(name, path):
    """The night (its date) a raw file belongs to, read both from the path the manifest gives and from the file it
    resolves to; None when neither is under results/own-clients-*. Refused when the two disagree."""
    lexical = os.path.normpath(path).replace(os.sep, "/")
    resolved = os.path.relpath(os.path.realpath(os.path.join(ROOT, path)), os.path.realpath(ROOT)).replace(os.sep, "/")
    nights = {m.group(1) for m in (NIGHT_FOLDER.match(lexical), NIGHT_FOLDER.match(resolved)) if m}
    if len(nights) > 1 or (nights and lexical != resolved):
        raise SystemExit(f"{name}: {path} resolves to {resolved}: a raw file of an own-client night is published only "
                         "from where it lies")
    return nights.pop() if nights else None


def check_audit(name, date):
    why = audit_problem(ROOT, date)
    if why:
        raise SystemExit(f"{name}: {why}")


def audit_gate(root):
    """The commit hook's gate (and CI's), over a tree: no link under results/own-clients-*, and every night folder
    that holds any file has its AUDIT.md with AUDIT_FIRST_LINE. Returns the problems (empty: the tree may be
    committed)."""
    problems = [f"{link}: a symbolic link under results/own-clients-*: refused" for link in night_links(root)]
    results = os.path.join(root, "results")
    for name in sorted(os.listdir(results)) if os.path.isdir(results) else []:
        m = NIGHT_FOLDER.match(f"results/{name}")
        top = os.path.join(results, name)
        if not m or os.path.islink(top) or not os.path.isdir(top):
            continue
        if any(files for _, _, files in os.walk(top)):
            why = audit_problem(root, m.group(1))
            if why:
                problems.append(f"results/{name}: {why}")
    return problems


def read_harness(path):
    """harness/probe.py event log: one JSON object per line."""
    with open(os.path.join(ROOT, path)) as f:
        rows = [json.loads(line) for line in f if line.strip()]
    start = next(r for r in rows if r["event"] == "start")
    control, checks, late = [], {}, 0
    # Every reply's usage: whether any reported a cached token, and which lifetime its cache writes had.
    usages = [r["usage"] for r in rows if isinstance(r.get("usage"), dict)]
    ttls = set()
    for u in usages:
        for key, ttl in (("write_1h", "1h"), ("write_5m", "5m")):
            if u.get(key):
                ttls.add(ttl)
    # check-invalid (a turn of more than one request) and check-failed rows are not checks.
    answered = set()
    for r in rows:
        if r["event"] != "check":
            continue
        u = r.get("usage") if isinstance(r.get("usage"), dict) else {}
        # A check is one model request, said so explicitly: a check whose usage gives another count (0: no call at
        # all) is never published; from the own-client design on the count must be there.
        if "calls" in u and u["calls"] != 1:
            raise SystemExit(f"{path}: a {r['event']} at {r.get('age')} records {u['calls']!r} model requests, not 1: "
                             "it is not a check (the run goes in excluded, or its file is repaired from the probe)")
        if "calls" not in u and start["at"][:10] >= OWN_CLIENTS_SINCE and start.get("isolation"):
            raise SystemExit(f"{path}: a check at {r.get('age')} records no count of model requests: not published")
        own = start["at"][:10] >= OWN_CLIENTS_SINCE and start.get("isolation")
        if own and "model" in u:
            # From the own-client design on, a public line holds no model text a client reported (harness/probe.py,
            # Public): only `model_matches`, whether it was the run's requested model.
            raise SystemExit(f"{path}: a check at {r.get('age')} carries a client-reported model text: not published "
                             "(the probe's public record holds only model_matches)")
        if own and u.get("model_matches") is not True:
            # M-1: a check whose own turn named no model, or another than the requested one, is not a measurement of
            # the manifest's model.
            raise SystemExit(f"{path}: a check at {r.get('age')} has no model evidence of its own turn naming the "
                             "requested model (model_matches): not published (the run goes in excluded)")
        if u.get("model_issue"):
            raise SystemExit(f"{path}: a check at {r.get('age')} records {u['model_issue']!r}: its answering model is not "
                             "certain; not published")
        if own and start.get("harness") == "codex" and u.get("model_evidence") != "own-turn":
            # Codex names no model in its output: only a model bound to the check's own single new turn, and equal to
            # the requested one (harness/clients.py, codex_answer), says which model answered.
            raise SystemExit(f"{path}: a Codex check at {r.get('age')} has no model evidence bound to its own turn "
                             "(model_evidence own-turn): not published (the run goes in excluded)")
        if own:
            answered.add(start["model"])  # model_matches: answered by the run's requested model
        elif u.get("model"):
            answered.add(u["model"])
        if r.get("late"):
            # A late control is no control: a 30-second re-send made minutes later shows nothing about the cache.
            late += 1
        elif r["age"] == "control":
            control.append(bool(r["warm"]))
        else:
            checks.setdefault(age_seconds(r["age"]), []).append(bool(r["warm"]))
    return {
        "client": HARNESS_CLIENT[start["harness"]],
        "date": start["at"][:10],
        "started": start["at"],
        "control": control,
        "checks": checks,
        "late": late,
        "effort": start.get("effort"),
        "client_env": start.get("client_env") or {},
        "isolation": start.get("isolation"),
        "any_cached": any((u.get("cached") or 0) > 0 or (u.get("raw") or {}).get("cached") for u in usages),
        "written_ttls": sorted(ttls),
        "stop": next((r.get("reason") for r in rows if r["event"] == "stop"), None),
        "answered_models": sorted(answered),
        "requested_model": start.get("model"),
        "exact_model": start.get("harness") == "codex",
        "model_scans": [r for r in rows if r["event"] == "model-scan"],
        "harness": start.get("harness"),
        "own_since": bool(start["at"][:10] >= OWN_CLIENTS_SINCE and start.get("isolation")),
    }


def read_plain(path):
    """Result file of the TypeScript probe."""
    j = json.load(open(os.path.join(ROOT, path)))
    checks, late = {}, 0
    for c in j.get("checks", []):
        if c.get("error"):
            continue
        target = c["targetAgeMs"]
        # The probe's own rule (src/run.ts lateAfterMs); 0.1.0 files carry no flag, so apply it here.
        if c.get("late") or c["actualAgeMs"] - target > max(30_000, round(target * 0.1)):
            late += 1
            continue
        checks.setdefault(round(target / 1000), []).append(bool(c["warm"]))
    control = [bool(j["control"]["warm"])] if j.get("control") else []
    return {
        "date": j["startedAt"][:10],
        "started": j["startedAt"],
        "control": control,
        "checks": checks,
        "late": late,
        "probe_version": j.get("probeVersion"),
        # From probe 0.3.0 the run file records what was sent; --body-extra as given, or None.
        "body_extra": (j.get("request") or {}).get("bodyExtra"),
    }


def summarize(checks):
    """all_warm_through_s: the largest age up to which every age tested was fully warm (the safe value).
    last_warm_s: the largest age with any warm check. first_all_cold_s: the smallest age with none."""
    ages = sorted(checks)
    through = None
    for age in ages:
        if all(checks[age]):
            through = age
        else:
            break
    warm_ages = [a for a in ages if any(checks[a])]
    cold_ages = [a for a in ages if not any(checks[a])]
    return {
        "all_warm_through_s": through,
        "last_warm_s": max(warm_ages) if warm_ages else None,
        "first_all_cold_s": min(cold_ages) if cold_ages else None,
    }


LADDER_SINCE = "2026-11-14"


def check_kinds():
    """Every client and every route has a kind, and nothing else has one."""
    if set(CLIENT_KINDS) != set(CLIENTS) or set(ROUTE_KINDS) != set(ROUTES):
        raise SystemExit("every client and every route needs a kind, and only they (CLIENT_KINDS, ROUTE_KINDS): "
                         f"clients {sorted(set(CLIENTS) ^ set(CLIENT_KINDS))}, routes {sorted(set(ROUTES) ^ set(ROUTE_KINDS))}")
    if set(CLIENT_KINDS.values()) - {"direct", "own_client", "proxy"} or set(ROUTE_KINDS.values()) - {"api_key", "login"}:
        raise SystemExit("a kind is not one of direct, own_client, proxy (clients) or api_key, login (routes)")
    for client, route in OWN_CLIENT_ROUTE.items():
        if CLIENT_KINDS.get(client) != "own_client" or ROUTE_KINDS.get(route) != "login":
            raise SystemExit(f"{client}: an own client of {route}, which is not a login")
    missing = [c for c, k in CLIENT_KINDS.items() if k == "own_client" and c not in OWN_CLIENT_ROUTE]
    if missing:
        raise SystemExit(f"own clients with no vendor's route: {missing}")


def check_own_route(name, client, route):
    """An own client measures only its vendor's login."""
    if CLIENT_KINDS.get(client) == "own_client" and OWN_CLIENT_ROUTE.get(client) != route:
        raise SystemExit(f"{name}: {client} is the own client of {OWN_CLIENT_ROUTE.get(client)}, not of {route}")


def check_answered_model(run, data):
    """M-1: a check answered by another model than the manifest's is never published under the manifest's model."""
    same = (lambda a, m: a == m) if data.get("exact_model") else same_model
    other = [m for m in data.get("answered_models") or [] if not same(m, run["model"])]
    asked = data.get("requested_model")
    if data.get("exact_model") and asked is not None and asked != run["model"]:
        raise SystemExit(f"{run['id']}: the run asked for {asked}, not the manifest's {run['model']}: not published "
                         "under that model")
    if other:
        raise SystemExit(f"{run['id']}: its checks were answered by {', '.join(other)}, not {run['model']} (a reroute): "
                         "not published under that model; the run goes in excluded")


def check_model_scan(run, data):
    """Codex, at the run's level: the probe read every session file of the run whole, at each check and at the end
    (model-scan events: final, other_models, a count, and unreadable). A run whose files name any model but the
    requested one anywhere, or could not all be read, or that ended on either, or whose end scan is missing, is not
    published."""
    if data.get("harness") != "codex":
        return
    if data.get("stop") in ("other-model", "unreadable-session"):
        raise SystemExit(f"{run['id']}: the run stopped on its session files ({data['stop']}): not published")
    scans = data.get("model_scans") or []
    if not any(s.get("final") is True for s in scans):
        raise SystemExit(f"{run['id']}: no end-of-run scan of its Codex session files (model-scan): not published")
    def clean(s):
        # The count of other models (an int, never a bool) is 0 and every session file could be read.
        return type(s.get("other_models")) is int and s["other_models"] == 0 and s.get("unreadable") is False
    if not all(clean(s) for s in scans):
        raise SystemExit(f"{run['id']}: its Codex session files name another model than {run['model']}, or could not "
                         "all be read (model-scan): the whole run is excluded")


def check_own_run(run, client, data, options):
    """The refusals of docs/own-clients.md, section 3, for a run file of harness/probe.py. Returns the written ttl."""
    ttls = data.get("written_ttls") or []
    if len(ttls) > 1:
        raise SystemExit(f"{run['id']}: its replies wrote the cache with more than one lifetime ({', '.join(ttls)})")
    written = ttls[0] if ttls else None
    asked = data.get("client_env", {}).get("CLAUDE_CODE_PROMPT_CACHE_TTL")
    if asked is not None and options.get("ttl") != asked:
        raise SystemExit(f"{run['id']}: the run set CLAUDE_CODE_PROMPT_CACHE_TTL={asked}; its options must say ttl {asked}")
    if options.get("ttl") and written and options["ttl"] != written:
        raise SystemExit(f"{run['id']}: options ask ttl {options['ttl']}, but the replies wrote {written}")
    if CLIENT_KINDS.get(client) != "own_client" or "any_cached" not in data:
        return written
    if not data["any_cached"]:
        raise SystemExit(f"{run['id']}: no reply of this own-client run reported a cached token: it measured nothing, "
                         f"and goes in excluded, not in runs")
    if data["date"] >= OWN_CLIENTS_SINCE and data.get("isolation") != ISOLATION:
        raise SystemExit(f"{run['id']}: an own-client run from {OWN_CLIENTS_SINCE} on must record its dedicated state "
                         f"folder, throwaway HOME and temporary working folder (isolation {json.dumps(ISOLATION)})")
    return written


def build_cache(manifest):
    links = night_links(ROOT)
    if links:
        raise SystemExit(f"{links[0]}: a symbolic link under results/own-clients-*: nothing is built while one is there")
    entries = []
    for run in manifest["runs"]:
        path = run["file"]
        night_of(run["id"], path)  # before the file is read: a link out of a night or into one is refused
        data = read_harness(path) if path.endswith(".jsonl") else read_plain(path)
        client = run.get("client") or data["client"]
        # The client is the raw file's: the manifest may name it again, never another one.
        if data.get("client") and run.get("client") and run["client"] != data["client"]:
            raise SystemExit(f"{run['id']}: the manifest says client {run['client']}, its raw file records "
                             f"{data['client']}")
        if CLIENT_KINDS.get(client) == "own_client" and not data.get("client"):
            raise SystemExit(f"{run['id']}: an own-client entry needs a raw file of harness/probe.py that records the "
                             f"client; {path} records none")
        if data.get("stop") == "tier-changed":
            raise SystemExit(f"{run['id']}: the run stopped because its replies changed the lifetime they wrote "
                             f"(tier-changed); its checks mix two lifetimes: it goes in excluded")
        if client not in CLIENTS or run["route"] not in ROUTES:
            raise SystemExit(f"{run['id']}: unknown client or route")
        check_own_route(run["id"], client, run["route"])
        options = dict(run.get("options") or {})
        written = check_own_run(run, client, data, options)
        check_answered_model(run, data)
        night = night_of(run["id"], path)
        if night:
            check_audit(run["id"], night)  # whatever the run's date or client: its night is audited first
        elif CLIENT_KINDS.get(client) == "own_client" and data.get("own_since"):
            raise SystemExit(f"{run['id']}: an own-client run is published only from results/own-clients-<date>/ (its "
                             f"audited night); {path} is not there")
        if CLIENT_KINDS.get(client) == "own_client" and data.get("own_since"):
            check_model_scan(run, data)
        # A run file that records its extra body fields: each must be in the manifest's options, as sent, or in
        # removed_by_proxy: a field the client sent that is shown not to reach the provider on this route and build
        # (options are what the provider received; the proof goes in the run's note).
        removed = run.get("removed_by_proxy") or {}
        sent = data.get("body_extra") or {}
        for field, value in sent.items():
            if options.get(field) != value and removed.get(field) != value:
                raise SystemExit(f"{run['id']}: the run file sent {field} = {json.dumps(value)}; its options in "
                                 f"{MANIFEST} must say so, or removed_by_proxy where the proxy removes it")
        for field, value in removed.items():
            if sent.get(field) != value or field in options:
                raise SystemExit(f"{run['id']}: removed_by_proxy names {field} = {json.dumps(value)}, which the run "
                                 f"file does not record as sent, or which is also in its options")
        if removed and not run.get("note"):
            raise SystemExit(f"{run['id']}: removed_by_proxy needs a note with the proof of the removal")
        if data.get("effort") and "reasoning" not in options:
            options["reasoning"] = data["effort"]
        entry = {
            "id": run["id"],
            "route": run["route"],
            "client": client,
            "model": run["model"],
            "models_dev": run.get("models_dev"),
            "base_model": run.get("base_model"),
            "options": options,
            "date": data["date"],
            "source": path,
            "control": {"warm": sum(data["control"]), "total": len(data["control"])},
            "checks": [
                {"age": age_label(age), "age_s": age, "warm": sum(v), "total": len(v)}
                for age, v in sorted(data["checks"].items())
            ],
            "late_excluded": data["late"],
            **summarize(data["checks"]),
        }
        if written:
            entry["written_ttl"] = written
        # From 14 November 2026 every evaluation starts the same way: a control (the prompt sent again at once), then
        # 2.5 minutes as its first age. A run that continues another one carries on from where that one stopped. A run
        # whose control missed has no ages by the method (it ends at the control), as cpa-8.0.53/D6 and O1 before that
        # date. The rule reads the run's own control, never a chain's: only a run whose every control missed may have no
        # ages. A mixed control (some hit) showed the cache, so the run must go on to its ages like one whose control hit.
        control_missed = bool(data["control"]) and not any(data["control"]) and not data["checks"]
        if entry["date"] >= LADDER_SINCE and not run.get("continues") and not control_missed:
            first = min(data["checks"]) if data["checks"] else None
            if not data["control"] or first != 150:
                raise SystemExit(f"{run['id']}: an evaluation must start with a control and a check at 2.5 minutes "
                                 f"(control checks: {len(data['control'])}, first age: {first} s)")
        for key in ("requires", "lacks", "note", "continues", "removed_by_proxy"):
            if run.get(key):
                entry[key] = run[key]
        entry["_started"] = data["started"]
        entry["_checks"] = data["checks"]
        entry["_control"] = list(data["control"])
        entries.append(entry)

    # "continues": a run that adds checks to an earlier one (older ages, or more samples of an age; same route,
    # client, model and options). Its `checks` and its three summary numbers then cover the earlier run too, and the
    # runs that one continues, so the entry stays consistent in itself for a reader that doesn't know the field (a
    # run with only cold, old ages would otherwise read as "never cached"). Its `control` is likewise every control of
    # the chain, each run's own counted once (warm and total summed; a missed one stays a miss beside one that hit).
    by_id = {e["id"]: e for e in entries}
    for e in sorted(entries, key=lambda e: e["_started"]):
        e["_merged"] = e["_checks"]
        e["_merged_control"] = e["_control"]
        if "continues" not in e:
            continue
        base = by_id.get(e["continues"])
        same = base and all(base[k] == e[k] for k in ("route", "client", "model", "options"))
        if not same or "_merged" not in base:
            raise SystemExit(f"{e['id']}: continues {e['continues']}, which is missing, differs, or started later")
        merged = {age: list(v) for age, v in base["_merged"].items()}
        for age, v in e["_checks"].items():
            merged.setdefault(age, []).extend(v)
        e["_merged"] = merged
        e["_merged_control"] = base["_merged_control"] + e["_control"]
        e["control"] = {"warm": sum(e["_merged_control"]), "total": len(e["_merged_control"])}
        e["checks"] = [{"age": age_label(age), "age_s": age, "warm": sum(v), "total": len(v)} for age, v in sorted(merged.items())]
        e.update(summarize(merged))

    # "latest": the newest run of the same route, client, model and options.
    newest = {}
    for e in entries:
        key = (e["route"], e["client"], e["model"], json.dumps(e["options"], sort_keys=True))
        if key not in newest or e["_started"] > newest[key]["_started"]:
            newest[key] = e
    for e in entries:
        key = (e["route"], e["client"], e["model"], json.dumps(e["options"], sort_keys=True))
        e["latest"] = newest[key] is e
        del e["_started"], e["_checks"], e["_merged"], e["_control"], e["_merged_control"]
    entries.sort(key=lambda e: (e["route"], e["model"], e["client"], e["date"], e["id"]))
    return entries


# The fields of a limits row that count tokens, as providers.dev reads them (site/src/core/schema.ts, ObservedLimit).
LIMIT_TOKEN_FIELDS = ("context", "output", "input_accepted", "input_refused", "input_read", "output_accepted")
LIMIT_KEYS = ("route", "client", "model", "models_dev", "base_model", *LIMIT_TOKEN_FIELDS, "note", "date")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def raw_n(row):
    """The size of a request in filler words. The 2026-11-08 Devin rows carry it only in their kind (devin-gpt-925000)."""
    if isinstance(row.get("n"), int):
        return row["n"]
    m = re.search(r"-(\d+)$", row.get("kind") or "")
    return int(m.group(1)) if m else None


def refused(row):
    return row.get("status") is not None and row.get("status") != 200


def check_evidence(rows, item, name):
    """Every number in a limits entry must be backed by a row of the raw limits file. Returns the rows that back it
    and the values each piece of evidence proves ({field: value})."""
    used, proves = [], {}

    def prove(field, value):
        proves.setdefault(field, set()).add(value)

    for ev in item["evidence"]:
        model = ev["row_model"]
        mine = [r for r in rows if r.get("model") == model]
        if "accepted" in ev:
            hits = [r for r in mine if r.get("status") == 200 and r.get("promptTokens") == ev["accepted"]]
            prove("input_accepted", ev["accepted"])
        elif "read" in ev:
            # A request with a code word before the filler and one after it, both returned: the input was read to the end.
            words = ev.get("words") or []
            hits = [r for r in mine if r.get("kind") == "recall" and r.get("status") == 200
                    and r.get("promptTokens") == ev["read"] and words and all(w in (r.get("reply") or "") for w in words)]
            prove("input_read", ev["read"])
        elif "refused_tokens" in ev:
            # A refusal that states no count: its size in filler words, converted with tokens = per_n × N + overhead,
            # which every accepted request of the same model in the file must fit exactly.
            per, over, size = ev["per_n"], ev["overhead"], ev["refused_n"]
            if per * size + over != ev["refused_tokens"]:
                raise SystemExit(f"{name}: {per} × {size} + {over} is not {ev['refused_tokens']}")
            hits = [r for r in mine if refused(r) and raw_n(r) == size]
            fits = [r for r in mine if r.get("status") == 200 and isinstance(r.get("promptTokens"), int) and r["promptTokens"] > 0
                    and raw_n(r) is not None and r.get("kind") not in ("output", "output-step")]
            if not fits or any(per * raw_n(r) + over != r["promptTokens"] for r in fits):
                raise SystemExit(f"{name}: the accepted requests of {model} do not fit tokens = {per} × N + {over}")
            prove("input_refused", ev["refused_tokens"])
        elif "refused_stated" in ev:
            # A refusal that states its own count ("The input (1050182 tokens) exceeds ...").
            hits = [r for r in mine if refused(r) and re.search(rf"\b{ev['refused_stated']} tokens", r.get("message") or "")]
            prove("input_refused", ev["refused_stated"])
        elif "refused_n" in ev:
            hits = [r for r in mine if refused(r) and r.get("n") == ev["refused_n"]]
        elif "refused_kind" in ev:
            hits = [r for r in mine if refused(r) and r.get("kind") == ev["refused_kind"]]
        elif "output_step" in ev:
            hits = [r for r in mine if r.get("status") == 200 and r.get("maxTokens") == ev["output_step"]]
            prove("output_accepted", ev["output_step"])
        elif "message_has" in ev:
            hits = [r for r in mine if ev["message_has"] in (r.get("message") or "")]
            for n in re.findall(r"\d+", ev["message_has"]):
                prove("named", int(n))
        elif "ctx_message_has" in ev:
            hits = [r for r in mine if ev["ctx_message_has"] in str((r.get("ctx") or ["", ""])[1])]
            for n in re.findall(r"\d+", ev["ctx_message_has"]):
                prove("named", int(n))
        else:
            hits = []
        if not hits:
            raise SystemExit(f"{name}: no raw row backs {ev}")
        used.extend(hits)
    return used, proves


def check_limit(entry, name):
    """What providers.dev refuses in a limits row (site/design/usable-input-window.md, sections 6 and 9)."""
    if entry["route"] not in ROUTES or entry["client"] not in CLIENTS:
        raise SystemExit(f"{name}: unknown route or client")
    check_own_route(name, entry["client"], entry["route"])
    # No own-client input limit is published for now: the first night measures none, and harness/client_limits.py is
    # not yet trusted (review of own-clients, finding 11). A login's input limits stay the proxy's.
    if CLIENT_KINDS.get(entry["client"]) == "own_client" and not OWN_CLIENT_LIMITS:
        raise SystemExit(f"{name}: own-client input limits are not published yet (harness/client_limits.py is not yet "
                         f"trusted); the login's limits stay the proxy's")
    # When they are: a row counts only where the provider refused. An input_accepted alone (a walk that ended at a cap
    # of the client's) would stand in front of the proxy's refusal and publish less than the login accepts.
    if CLIENT_KINDS.get(entry["client"]) == "own_client" and entry.get("context") is None and entry.get("input_refused") is None:
        raise SystemExit(f"{name}: an own client's limits row needs context or input_refused, from the provider's refusal")
    for field in LIMIT_TOKEN_FIELDS:
        value = entry.get(field)
        if value is not None and not (isinstance(value, int) and not isinstance(value, bool) and value >= 0):
            raise SystemExit(f"{name}: {field} {value!r} is not a token count (a whole number, 0 or more)")
    accepted, refused_, named, read = (entry.get(k) for k in ("input_accepted", "input_refused", "context", "input_read"))
    if refused_ is not None and accepted is None:
        raise SystemExit(f"{name}: input_refused {refused_} with no input_accepted from the same walk")
    if accepted is not None and refused_ is not None and not accepted < refused_:
        raise SystemExit(f"{name}: input_accepted {accepted} is not below input_refused {refused_}")
    if accepted is not None and named is not None and accepted > named:
        raise SystemExit(f"{name}: input_accepted {accepted} is above context {named}")
    if read is not None and accepted is None:
        raise SystemExit(f"{name}: input_read {read} with no input_accepted")
    if read is not None and read > accepted:
        raise SystemExit(f"{name}: input_read {read} is above input_accepted {accepted}")
    if not any(entry.get(f) is not None for f in LIMIT_TOKEN_FIELDS):
        raise SystemExit(f"{name}: no limit in the row")
    if entry.get("date") is not None and not (isinstance(entry["date"], str) and DATE.fullmatch(entry["date"])):
        raise SystemExit(f"{name}: date {entry.get('date')!r} is not YYYY-MM-DD")
    if entry.get("note") is not None and not isinstance(entry["note"], str):
        raise SystemExit(f"{name}: note is not text")


def check_limit_provenance(item, used, name):
    """An own client's row rests only on raw rows that its own walk wrote (harness/client_limits.py records the
    client in every row): a proxy's refusal never becomes an own client's limit."""
    if CLIENT_KINDS.get(item["client"]) != "own_client":
        return
    other = sorted({str(r.get("client")) for r in used if r.get("client") != item["client"]})
    if other:
        raise SystemExit(f"{name}: its evidence rows were written by {', '.join(other)}, not by {item['client']}")


def build_limits(manifest):
    files = {}
    out = []
    seen = set()
    for item in manifest["limits"]:
        name = f"limits row {item.get('route')} / {item.get('client')} / {item.get('model')}"
        unknown = set(item) - set(LIMIT_KEYS) - {"evidence", "file"}
        if unknown:
            raise SystemExit(f"{name}: unknown keys {sorted(unknown)}")
        key = (item["route"], item["client"], item["model"])
        if key in seen:
            raise SystemExit(f"{name}: two rows with the same route, client and model (one row each; a new walk replaces it)")
        seen.add(key)
        check_limit(item, name)
        path = item.get("file") or manifest["limits_file"]
        if path not in files:
            files[path] = [json.loads(line) for line in open(os.path.join(ROOT, path)) if line.strip()]
        used, proves = check_evidence(files[path], item, name)
        check_limit_provenance(item, used, name)
        # Every token count of the row is one that a piece of its evidence proves.
        for field in ("input_accepted", "input_refused", "input_read", "output_accepted"):
            if item.get(field) is not None and item[field] not in proves.get(field, ()):
                raise SystemExit(f"{name}: {field} {item[field]} is not backed by its evidence")
        for field in ("context", "output"):
            if item.get(field) is not None and item[field] not in proves.get("named", ()):
                raise SystemExit(f"{name}: {field} {item[field]} is not named in a raw row's message")
        # The date: the day the requests were sent, from the raw rows (the newest that backs the row). Only rows that
        # carry no time may take it from the manifest.
        days = sorted({r["at"][:10] for r in used if isinstance(r.get("at"), str)})
        if days:
            if item.get("date") not in (None, days[-1]):
                raise SystemExit(f"{name}: date {item['date']} differs from its raw rows ({days[-1]})")
            date = days[-1]
        elif item.get("date"):
            date = item["date"]
        else:
            raise SystemExit(f"{name}: its raw rows carry no time, so the manifest must give the date")
        entry = {"models_dev": None, **{k: v for k, v in item.items() if k not in ("evidence", "file")}, "date": date}
        entry = {k: entry[k] for k in LIMIT_KEYS if k in entry}
        entry["source"] = path
        out.append(entry)
    out.sort(key=lambda e: (e["route"], e["model"], e["client"]))
    return out


def build_known(manifest):
    """Lifetimes that follow from how requests are built (not measured): passed through after a shape check."""
    out = []
    for item in manifest.get("known", []):
        if item.get("route") not in ROUTES or item.get("client") not in CLIENTS:
            raise SystemExit(f"known: unknown route or client in {item}")
        check_own_route("known", item["client"], item["route"])
        if not isinstance(item.get("ttl_s"), int) or not item.get("basis") or not item.get("source") or not item.get("model"):
            raise SystemExit(f"known: ttl_s, model, basis and source are required in {item}")
        out.append(item)
    return out


def build():
    check_kinds()
    manifest = json.load(open(os.path.join(ROOT, MANIFEST)))
    return {
        "schema": 1,
        "repository": "https://github.com/ngvoicu/groundtruth",
        "about": "Prompt-cache lifetimes and limits as measured, not as documented. Built from results/ by "
                 "scripts/build_observed.py; see README.md, section 'observed.json'.",
        "routes": ROUTES,
        "clients": CLIENTS,
        "client_kinds": CLIENT_KINDS,
        "route_kinds": ROUTE_KINDS,
        "cache": build_cache(manifest),
        "limits": build_limits(manifest),
        "known": build_known(manifest),
        "excluded": build_excluded(manifest),
    }


def build_excluded(manifest):
    """The manifest's excluded runs; an entry of an own-client night (its id or file names own-clients-<date>) only
    once that night is audited: nothing of an unaudited night is published, not even why a run was left out."""
    for e in manifest["excluded"]:
        for value in (e.get("id"), e.get("file")):
            m = NIGHT_NAME.search(value) if isinstance(value, str) else None
            if m:
                check_audit(f"excluded {e.get('id')}", m.group(1))
    return manifest["excluded"]


def main():
    if "--audit-gate" in sys.argv:
        tree = sys.argv[sys.argv.index("--audit-gate") + 1]
        problems = audit_gate(tree)
        for p in problems:
            print(p, file=sys.stderr)
        if problems:
            raise SystemExit("audit gate: refused: nothing under results/own-clients-* is committed before its night's "
                             "audit (docs/own-clients-RUN.md, \"The morning\")")
        print("audit gate: every own-client night in the tree is audited (or there is none)")
        return
    text = json.dumps(build(), indent=1, ensure_ascii=False) + "\n"
    target = os.path.join(ROOT, OUT)
    if "--check" in sys.argv:
        current = open(target).read() if os.path.exists(target) else ""
        if current != text:
            raise SystemExit(f"{OUT} is out of date: run python3 scripts/build_observed.py")
        print(f"{OUT} is up to date")
        return
    open(target, "w").write(text)
    data = json.loads(text)
    print(f"wrote {OUT}: {len(data['cache'])} cache runs, {len(data['limits'])} limits")


if __name__ == "__main__":
    main()
