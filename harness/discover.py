#!/usr/bin/env python3
"""Discovery (step G1, Provimux's model-lists.md 9.1, way A): what each login's vendor offers today, into listed.json.

    python3 harness/discover.py                      # reads the owner's Provimux, writes listed.json; no commit
    python3 harness/discover.py --publish            # the same, then commits and pushes listed.json when it changed
    python3 harness/discover.py --answer FILE        # reads a saved answer instead of Provimux (nothing is sent)

What it does, in order:

1. **One local request**: `GET /v8/management/provimux/model-lists?view=live` to the owner's Provimux on this Mac
   (CPA_BASE_URL, default http://127.0.0.1:8317; a host that is not this Mac is refused). The management key is found
   as harness/pool.py finds it (CPA_MGMT_KEY, else the MGMT_KEY line of ~/.cli-proxy-api/keys.txt) and never printed
   or written. Nothing is sent to a vendor: Provimux has asked them already, and groundtruth reads no token.
2. **Only what the vendor's list said**: per login, its `live_list` (the vendor's answer as it arrived, unmerged), and
   only while Provimux holds it (`live.held`: fetched, not past Provimux's 7 days). A login without one, a disabled
   login, and a login type with no listing on providers.dev (LISTINGS) give nothing.
3. **No identity**: the file is built field by field from a model's id, name, window, output limit, modalities and
   reasoning levels. Nothing of a row (`auth_index`, `login` with its name, e-mail and label, counts, failures) is
   read into it, and the result is checked against the schema (harness/listed_schema.py) and against every identity
   string of the answer before it is written.
4. **The logins of one type are joined**: the union of their models. A field is written when every login that states
   it states the same value; where two disagree it is left out (logged). The part's date is the oldest of the joined
   lists' fetch dates, so a part is never newer than what it holds.
5. **A provider with no live list today keeps yesterday's part and date**, unchanged. So does a provider whose new
   list would be older than the part already written.
6. **Ages**: every provider's age is logged (`$GROUNDTRUTH_CLIENT_HOME/discovery.log`, else --log, else stderr only).
   A provider older than 3 days is an ask: an `ASK:` line in the log and in the command's last words. When Provimux
   cannot be read, the file keeps its last content, and the ages and asks are still logged.
7. **--publish** (off by default): when listed.json changed, harness/scan_secrets.py must pass on it, then it alone is
   committed on `main` and pushed (--remote, default upstream then origin). Without --publish nothing is committed.

The file (schema 1, providers.dev's `ListedFile`):

    {"schema": 1, "repository": "https://github.com/ngvoicu/groundtruth",
     "providers": {"devin": {"date": "2026-11-24", "client": "provimux",
                             "models": [{"id": "gemini-4-argon", "context_window": 1048576, ...}]}}}

Exit: 0 written or unchanged (asks, if any, are in the last lines); 1 when Provimux could not be read, the answer or
the existing file is not usable, the file would lose too much for providers.dev to take it, or the scan or the
publication failed.
"""
import argparse
import datetime as dt
import ipaddress
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import listed_schema as S  # noqa: E402

PATH = "/v8/management/provimux/model-lists?view=live"
CLIENT = "provimux"  # data/authored/measurement-labels.yaml on providers.dev: Provimux, kind proxy
# A Provimux login type -> its listing on providers.dev (model-lists.md 4.1), for the types whose listing comes from
# discovery. Not here: Kimi (Provimux does not ask it yet, 13.4, and which host is "global" is not settled), xAI
# (models.dev unless the login's list differs), Gemini keys, Vertex and AI Studio (models.dev).
LISTINGS = {
    "antigravity": "antigravity",
    "claude": "claude-subscription",
    "codex": "openai-codex",
    "copilot": "github-copilot",
    "devin": "devin",
    "meta": "meta-subscription",
}
# Provimux shows a Devin id with its own route prefix (devin/<id>); Devin's own id, the one providers.dev lists, has none.
ROUTE_PREFIX = {"devin": "devin/"}
STALE_DAYS = 3
MAX_BYTES = 8 * 1024 * 1024  # providers.dev's limit for the file, and Provimux's for a list
MIN_SHARE = 0.6  # providers.dev refuses a file that lost more than 40 % of its providers or models
TIMEOUT = 30
REMOTES = ("upstream", "origin")


class Failure(Exception):
    """A reason to stop with exit 1; its text is safe to print (no key, no answer text)."""


class Log:
    def __init__(self, path):
        self.path, self.lines = path, []

    def __call__(self, line):
        self.lines.append(line)
        print(line, file=sys.stderr)
        if self.path:
            stamp = dt.datetime.now().astimezone().isoformat(timespec="seconds")
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(f"{stamp} {line}\n")


# --- reading Provimux ------------------------------------------------------------------------------------------------

def local_only(base):
    """The base URL, if its host is this Mac; else Failure. Discovery reads the owner's Provimux and nothing else."""
    parts = urllib.parse.urlsplit(base)
    host = parts.hostname or ""
    if parts.scheme not in ("http", "https") or not host:
        raise Failure(f"--base-url must be http(s)://<host>:<port>, got a value without a host")
    if host != "localhost":
        try:
            if not ipaddress.ip_address(host).is_loopback:
                raise ValueError
        except ValueError:
            raise Failure("refused: discovery reads only a Provimux on this Mac (127.0.0.1, ::1 or localhost)")
    return base.rstrip("/")


def fetch(base, key, opener=urllib.request.urlopen):
    """The one request. Its errors name the status or the kind of failure, never the answer's text or the key."""
    req = urllib.request.Request(local_only(base) + PATH, headers={"Authorization": "Bearer " + key,
                                                                   "Accept": "application/json"})
    try:
        with opener(req, timeout=TIMEOUT) as resp:
            raw = resp.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as err:
        hint = {401: " (the management key was refused)", 404: " (this Provimux has no model-lists endpoint: "
                "8.1.1-pmx.2 or later)", 503: " (the model-list status is not available yet)"}.get(err.code, "")
        raise Failure(f"Provimux answered HTTP {err.code}{hint}")
    except (urllib.error.URLError, OSError) as err:
        raise Failure(f"Provimux could not be reached ({type(getattr(err, 'reason', err)).__name__})")
    if len(raw) > MAX_BYTES:
        raise Failure("Provimux's answer is larger than 8 MB")
    try:
        return json.loads(raw)
    except ValueError:
        raise Failure("Provimux's answer is not JSON")


# --- from the answer to the file -------------------------------------------------------------------------------------

def day_of(stamp):
    try:
        return dt.datetime.fromisoformat(str(stamp).replace("Z", "+00:00")).astimezone(dt.timezone.utc).date()
    except ValueError:
        return None


def identity_strings(answer):
    """Every identity value of the answer (auth_index, the login's name, e-mail and label): none may reach the file."""
    out = set()
    for row in answer.get("logins") or []:
        if not isinstance(row, dict):
            continue
        values = [row.get("auth_index")] + list((row.get("login") or {}).values() if isinstance(row.get("login"), dict)
                                                 else [])
        out.update(v for v in values if isinstance(v, str) and len(v) >= 4)
    return out


def vendor_model(login_type, entry, dropped):
    """One entry of a vendor's list as the file writes it, or None. Only the fields below are read."""
    if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
        dropped.append("an entry without an id")
        return None
    mid = entry["id"].strip()
    prefix = ROUTE_PREFIX.get(login_type)
    if prefix and mid.lower().startswith(prefix):
        mid = mid[len(prefix):]
    problem = S.model_id_problem(mid)
    if problem:
        dropped.append(f"{mid if not S.unsafe(mid) and len(mid) <= 80 else '(an id not shown)'}: {problem}")
        return None
    out = {"id": mid}
    name = entry.get("display_name")
    if isinstance(name, str) and name.strip() and not S.name_problem(name.strip()):
        out["name"] = name.strip()
    for src, dst in (("context", "context_window"), ("output", "max_output")):
        if S.is_count(entry.get(src)):
            out[dst] = entry[src]
    for src, dst in (("input_modalities", "input_modalities"), ("output_modalities", "output_modalities")):
        words = words_of(entry.get(src))
        if words:
            out[dst] = words
    levels = words_of(entry.get("reasoning_levels"))
    if levels:
        out["reasoning"] = {"levels": levels[:16]}
    return out


def words_of(values):
    """A list's lower-case words, in order, once each; an empty or missing list states nothing."""
    if not isinstance(values, list):
        return []
    out = []
    for v in values:
        w = v.strip().lower() if isinstance(v, str) else ""
        if w and not S.word_problem(w) and w not in out:
            out.append(w)
    return out[:64]


def join(lists):
    """The union of several logins' lists of one type. A field stays when all who state it agree."""
    by_id, order, differing = {}, [], []
    for models in lists:
        for m in models:
            if m["id"] not in by_id:
                by_id[m["id"]] = [m]
                order.append(m["id"])
            else:
                by_id[m["id"]].append(m)
    out = []
    for mid in sorted(order):
        stated = by_id[mid]
        model = {"id": mid}
        keys = []
        for m in stated:
            keys += [k for k in m if k not in keys and k != "id"]
        for k in keys:
            values = [m[k] for m in stated if k in m]
            if all(v == values[0] for v in values):
                model[k] = values[0]
            else:
                differing.append(f"{mid} {k}")
        out.append(model)
    return out, differing


def discovered(answer, log):
    """provider -> {date, client, models} from today's answer: the providers with a held live list."""
    if not isinstance(answer, dict) or not isinstance(answer.get("logins"), list):
        raise Failure("Provimux's answer has no list of logins: not a /provimux/model-lists answer")
    if (answer.get("options") or {}).get("live_lists") is False:
        log("Provimux's live lists are switched off (models.live-lists: false): no login has a list to read")
    groups, skipped = {}, {}
    for row in answer["logins"]:
        if not isinstance(row, dict):
            continue
        login_type = str(row.get("provider") or "").lower()
        provider = LISTINGS.get(login_type)
        live = row.get("live") if isinstance(row.get("live"), dict) else {}
        reason = None
        if provider is None:
            reason = f"{login_type or '?'}: no listing of providers.dev comes from discovery"
        elif "live_list" not in row:
            raise Failure("Provimux's answer has no live_list: it was not asked with view=live")
        elif row.get("disabled") is True:
            reason = f"{provider}: a disabled login"
        elif not isinstance(row.get("live_list"), list) or not row["live_list"]:
            reason = f"{provider}: a login without a live list"
        elif live.get("held") is not True:
            reason = f"{provider}: a login whose list Provimux no longer holds (older than 7 days)"
        elif day_of(live.get("fetched_at")) is None:
            reason = f"{provider}: a login whose list has no fetch time"
        if reason:
            skipped[reason] = skipped.get(reason, 0) + 1
            continue
        dropped = []
        models = [m for m in (vendor_model(login_type, e, dropped) for e in row["live_list"]) if m]
        for d in sorted(set(dropped)):
            log(f"{provider}: left out {d}")
        if models:
            groups.setdefault(provider, []).append((day_of(live["fetched_at"]), models))
    for reason, n in sorted(skipped.items()):
        log(f"skipped {n} row{'s' if n > 1 else ''}: {reason}")
    out = {}
    for provider, lists in sorted(groups.items()):
        models, differing = join([m for _, m in lists])
        if differing:
            log(f"{provider}: the logins' lists disagree, so these fields are left out: {', '.join(differing)}")
        out[provider] = {"date": min(d for d, _ in lists).isoformat(), "client": CLIENT, "models": models}
        log(f"{provider}: live list of {len(lists)} login{'s' if len(lists) > 1 else ''}, {len(models)} models, "
            f"read {out[provider]['date']}")
    return out


def merged(previous, today, log):
    """Yesterday's file with today's parts in it. A provider without a list today keeps its part and date."""
    providers = dict((previous or {}).get("providers") or {})
    for provider, part in today.items():
        old = providers.get(provider)
        if old and old.get("date", "") > part["date"]:
            log(f"{provider}: today's list was read {part['date']}, before the part already written "
                f"({old['date']}): kept")
            continue
        providers[provider] = part
    for provider in sorted(set(providers) - set(today)):
        log(f"{provider}: no live list today: kept the part of {providers[provider].get('date')}")
    return {"schema": S.SCHEMA, "repository": S.REPOSITORY, "providers": dict(sorted(providers.items()))}


def ages(doc, today, log):
    """Logs every provider's age; returns the asks (providers older than STALE_DAYS)."""
    asks = []
    for provider, part in sorted(((doc or {}).get("providers") or {}).items()):
        try:
            days = (today - dt.date.fromisoformat(part["date"])).days
        except (KeyError, TypeError, ValueError):
            days = None
        log(f"age: {provider} {days if days is not None else '?'} day{'' if days == 1 else 's'} "
            f"({len(part.get('models') or [])} models)")
        if days is None or days > STALE_DAYS:
            asks.append(f"ASK: discovery has no fresh list for {provider}: "
                        f"{days if days is not None else 'unknown number of'} days old (more than {STALE_DAYS}). "
                        "Look at its logins on Provimux's model-lists status; then `python3 harness/discover.py`")
    for line in asks:
        log(line)
    return asks


def check(doc, answer):
    """The schema, and no identity value of the answer anywhere in the text: both before anything is written."""
    errors = S.validate(doc)
    if errors:
        raise Failure("the file would not pass its schema: " + "; ".join(errors[:5]))
    text = json.dumps(doc).lower()
    strings = set()

    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                strings.add(str(k).lower())
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
        elif isinstance(node, str):
            strings.add(node.lower())
    walk(doc)
    for value in identity_strings(answer):
        value = value.lower()
        # A long value anywhere in the text; a short one (a label like "work") as a whole value only.
        if (len(value) >= 8 and value in text) or value in strings:
            raise Failure("the file would hold an identity value of the answer: not written")


def shrank(previous, doc):
    count = lambda d: (len(d["providers"]), sum(len(p["models"]) for p in d["providers"].values()))  # noqa: E731
    if not previous or not previous.get("providers"):
        return False
    (pp, pm), (np_, nm) = count(previous), count(doc)
    return np_ < pp * MIN_SHARE or nm < pm * MIN_SHARE


def text_of(doc):
    """One model per line, so a day's change reads as a diff of models."""
    dump = lambda v: json.dumps(v, ensure_ascii=True, separators=(", ", ": "))  # noqa: E731
    parts = []
    for provider, part in doc["providers"].items():
        models = ",\n".join("        " + dump(m) for m in part["models"])
        parts.append(f'    {dump(provider)}: {{"date": {dump(part["date"])}, "client": {dump(part["client"])}, '
                     f'"models": [\n{models}\n    ]}}')
    body = ",\n".join(parts)
    return (f'{{\n  "schema": {dump(doc["schema"])},\n  "repository": {dump(doc.get("repository", S.REPOSITORY))},\n'
            f'  "providers": {{\n{body}\n  }}\n}}\n')


def write(path, doc):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text_of(doc))
    os.replace(tmp, path)


def read_previous(path):
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, ValueError):
        raise Failure(f"{os.path.basename(path)} is not JSON: look at it before discovery writes over it")
    errors = S.validate(doc)
    if errors:
        raise Failure(f"{os.path.basename(path)} does not pass its schema ({errors[0]}): look at it first")
    return doc


# --- publishing ------------------------------------------------------------------------------------------------------

def git(repo, *args):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, env=env)


def publish(repo, path, date, remotes, log, scan=None):
    """Commits listed.json alone on main and pushes it, after the credential scan passes on it."""
    rel = os.path.relpath(path, repo)
    if git(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip() != "main":
        raise Failure("--publish commits on main only: this checkout is on another branch")
    if not git(repo, "status", "--porcelain", "--", rel).stdout.strip():
        log("listed.json is as committed: nothing to publish")
        return False
    scan = scan or [sys.executable, os.path.join(HERE, "scan_secrets.py"), path]
    r = subprocess.run(scan, capture_output=True, text=True)
    if r.returncode != 0:
        raise Failure("harness/scan_secrets.py found something in listed.json: not committed "
                      f"({(r.stdout.strip().splitlines() or ['no output'])[-1]})")
    log("scan: " + (r.stdout.strip().splitlines() or ["clean"])[-1])
    r = git(repo, "add", "--", rel)
    if r.returncode == 0:
        r = git(repo, "commit", "-q", "-m", f"discovery: listed.json of {date}", "--", rel)
    if r.returncode != 0:
        raise Failure("the commit of listed.json failed (the pre-commit hook's words are in its output): "
                      + (r.stderr.strip().splitlines() or r.stdout.strip().splitlines() or ["?"])[-1][:200])
    log("committed: " + git(repo, "log", "-1", "--format=%h %s").stdout.strip())
    for remote in remotes:
        r = git(repo, "push", "-q", remote, "HEAD:main")
        if r.returncode != 0:
            raise Failure(f"the push to {remote} failed; the commit stays here: "
                          + (r.stderr.strip().splitlines() or ["?"])[-1][:200])
        log(f"pushed to {remote}")
    return True


# --- the command -----------------------------------------------------------------------------------------------------

def run(args, opener=urllib.request.urlopen, key_finder=None, scan=None):
    """The whole command; returns (exit code, last words)."""
    home = os.environ.get("GROUNDTRUTH_CLIENT_HOME")
    log = Log(args.log or (os.path.join(home, "discovery.log") if home and os.path.isdir(home) else None))
    today = dt.date.fromisoformat(args.date) if args.date else dt.date.today()
    out = args.out
    log(f"discovery of {today.isoformat()}: {'saved answer' if args.answer else 'Provimux'}, file {os.path.relpath(out, ROOT) if out.startswith(ROOT) else os.path.basename(out)}")
    try:
        previous = read_previous(out)
    except Failure as err:
        log(f"failed: {err}")
        return 1, f"discovery failed: {err}"
    try:
        if args.answer:
            with open(args.answer, encoding="utf-8") as f:
                answer = json.load(f)
        else:
            base = local_only(args.base_url)
            key = (key_finder or management_key)()
            answer = fetch(base, key, opener)
            del key
        today_parts = discovered(answer, log)
        doc = merged(previous, today_parts, log)
        if not doc["providers"]:
            raise Failure("no provider has a live list, and there is no earlier file: nothing written")
        check(doc, answer)
        if shrank(previous, doc):
            raise Failure("the new file lost more than 40 % of the providers or models of the last one; providers.dev "
                          "would refuse it: not written")
    except (Failure, OSError, ValueError) as err:
        text = str(err) if isinstance(err, Failure) else f"{type(err).__name__} reading the answer"
        log(f"failed: {text}; {os.path.basename(out)} keeps its last content")
        asks = ages(previous, today, log)
        return 1, "\n".join([f"discovery failed: {text}"] + asks)
    changed = previous is None or text_of(previous) != text_of(doc)
    if changed:
        write(out, doc)
    models = sum(len(p["models"]) for p in doc["providers"].values())
    log(f"{'wrote' if changed else 'unchanged:'} {os.path.basename(out)}: {len(doc['providers'])} providers, "
        f"{models} models, {len(today_parts)} read today")
    asks = ages(doc, today, log)
    if args.publish:
        try:
            publish(os.path.dirname(os.path.abspath(out)), out, today.isoformat(), args.remote or REMOTES, log, scan)
        except Failure as err:
            log(f"failed: {err}")
            return 1, "\n".join([f"discovery wrote {os.path.basename(out)} but did not publish it: {err}"] + asks)
    words = (f"discovery: {len(doc['providers'])} providers, {models} models"
             f"{'' if changed else ' (unchanged)'}; {len(asks)} ask{'' if len(asks) == 1 else 's'}")
    return 0, "\n".join([words] + asks)


def management_key():
    import pool  # harness/pool.py: CPA_MGMT_KEY, else ~/.cli-proxy-api/keys.txt; exits when there is none
    try:
        return pool.management_key()
    except SystemExit:
        raise Failure("no management key: set CPA_MGMT_KEY, or a MGMT_KEY line in ~/.cli-proxy-api/keys.txt")


def parser():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--base-url", default=os.environ.get("CPA_BASE_URL", "http://127.0.0.1:8317"),
                    help="the owner's Provimux on this Mac")
    ap.add_argument("--answer", help="a saved /provimux/model-lists?view=live answer: read instead of Provimux")
    ap.add_argument("--out", default=os.path.join(ROOT, "listed.json"))
    ap.add_argument("--date", help="today, as YYYY-MM-DD (for the ages)")
    ap.add_argument("--log", help="the log file (default: $GROUNDTRUTH_CLIENT_HOME/discovery.log)")
    ap.add_argument("--publish", action="store_true", help="commit and push listed.json when it changed")
    ap.add_argument("--remote", action="append", help="where --publish pushes (repeatable; default upstream, origin)")
    return ap


def main(argv=None):
    code, words = run(parser().parse_args(argv))
    print(words)
    return code


if __name__ == "__main__":
    sys.exit(main())
