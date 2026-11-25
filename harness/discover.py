#!/usr/bin/env python3
"""Discovery (step G1, Provimux's model-lists.md 9.1, way A): what each login's vendor offers, into listed.json.

    python3 harness/discover.py                  # reads Provimux and GitHub's listed.json, writes $G/listed.json only
    python3 harness/discover.py --publish        # the same, then puts listed.json on GitHub's main when it changed
    python3 harness/discover.py --answer FILE    # a saved Provimux answer instead of Provimux (nothing is sent to it)
    python3 harness/discover.py --forget-absent  # forgets the logins remembered but absent today (one removed on purpose)

$G is GROUNDTRUTH_CLIENT_HOME, an existing folder (the nights' private folder); everything discovery keeps is there:
`listed.json` (the last version it built), `discovery-state.json` (private, never published), `discovery.log`,
`discovery.lock`. Discovery runs no git command and has no clone.

What it does, in order:

1. **One local request**: `GET /v8/management/provimux/model-lists?view=live` to the owner's Provimux on this Mac
   (CPA_BASE_URL, default http://127.0.0.1:8317). The URL must be loopback; the opener uses no proxy and refuses a
   redirect, so the key never leaves this Mac. The management key (CPA_MGMT_KEY, else the MGMT_KEY line of
   ~/.cli-proxy-api/keys.txt) is never printed or written. Nothing is sent to a vendor.
2. **Four listings only**: Claude login -> claude-subscription, Codex -> openai-codex, Devin -> devin (Devin's own ids,
   without Provimux's `devin/`), Meta -> meta-subscription. Per login only its `live_list` (the vendor's answer as it
   arrived), and of an entry only its id, name, window, output limit, modalities and reasoning levels.
   **Only a described model**: an entry that carries nothing but its id is left out (Provimux records every Codex
   slug but describes only the ones Codex's picker shows; Meta's list is ids only), and a provider left with no model
   is not in the file. **No Codex window**: Codex's figure is the most its client lets a user set, not what the
   service accepts. The log counts, per provider, the models left out as undescribed (docs/discovery.md).
3. **Privacy by allowlist**: modalities and reasoning levels only from fixed vocabularies (providers.dev's
   LISTED_MODALITIES with its kinds(), and LISTED_LEVELS, which are Provimux's liveModelListLevels); any other word is
   dropped. A model is dropped when its id or name holds an identity value as a whole token sequence, whatever its
   length: a login's label, e-mail and its local part, file name and its stem, auth_index (of every row of the
   answer), and the management key from the environment and from the key file (also as a plain substring). An
   identity value made only of SERVICE_WORDS (a login labelled "Devin") never counts. Logged without the value.
4. **Complete lists, never a removal**: a login's list is complete when Provimux holds it (held, not expired), it is
   not empty, and it has as many models as Provimux says it listed (`live.listed_models`), counted on the whole
   list as it arrived, before any model is left out (a hidden or undescribed one does not make a list incomplete). The logins of each type are
   remembered (hashed) in `$G/discovery-state.json`; a login remembered but absent from today's answer counts as
   incomplete. A provider's new part is the union of the published part's models and today's complete lists; a field
   stated today replaces the published value (two logins stating it differently: the published value stays). Its
   date advances (to the oldest of today's lists) only when every enabled login of the type, and every remembered one,
   gave a complete list. A provider not yet published appears on its first complete day. A model is removed only by
   hand. Any other provider of the published file is carried forward as it is, except Copilot and Antigravity, which
   discovery does not list (docs/discovery.md).
5. **The base is GitHub's file** (`gh api`, read only): `GET /repos/ngvoicu/groundtruth/contents/listed.json`, its
   bytes checked against its blob sha. The new file is checked before it is written: its schema
   (harness/listed_schema.py), 8 MiB, no more than 40 % lost against GitHub's file. It is always written to
   `$G/listed.json`, which the weekly night plans from.
6. **--publish**: when the new file differs from GitHub's, harness/scan_secrets.py and an identity check run on the
   exact bytes to be sent, then `PUT` the same path with those bytes, GitHub's sha, branch main, the message
   "discovery: listed.json", and author and committer "groundtruth discovery <office@providers.dev>". A 409 or 422
   (the file changed meanwhile): read again and rebuild once; a second one is exit 1. GitHub only: the NAS copy
   follows it by itself (.forgejo/workflows/follow-github.yml).
7. **Ages, from the last published file**: every provider's age is logged. A provider older than 3 days is an `ASK:`
   line, and one macOS notification per stale part (osascript). A failed --publish is an `ASK:` line too.
8. **One run at a time**: a lock in $G makes a second run exit at once. Files are written through a temporary file
   unique to the run, then one rename.

Exit 0: written, unchanged or published (asks in the last lines); 1: anything failed (nothing published).
"""
import argparse
import base64
import datetime as dt
import fcntl
import hashlib
import ipaddress
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import listed_schema as S  # noqa: E402

PATH = "/v8/management/provimux/model-lists?view=live"
CLIENT = "provimux"  # data/authored/measurement-labels.yaml on providers.dev: Provimux, kind proxy
# A Provimux login type -> its listing on providers.dev (model-lists.md 4.1). Only these four.
LISTINGS = {"claude": "claude-subscription", "codex": "openai-codex", "devin": "devin", "meta": "meta-subscription"}
# Never carried from an earlier file: Copilot (Provimux's list holds models the account does not offer) and
# Antigravity (one shared description per model id for all logins). docs/discovery.md has the Provimux lines.
NOT_LISTED = {"copilot", "github-copilot", "antigravity"}
# Provimux shows a Devin id with its own route prefix (devin/<id>); Devin's own id, the one providers.dev lists, has none.
ROUTE_PREFIX = {"devin": "devin/"}
# Names of providers and services: an identity value made only of these words (a login labelled "Devin") drops nothing.
SERVICE_WORDS = {
    "anthropic", "antigravity", "aistudio", "chatgpt", "claude", "codex", "copilot", "deepseek", "devin", "gemini",
    "github", "google", "grok", "kimi", "meta", "moonshot", "muse", "openai", "openrouter", "provimux", "vertex",
    "windsurf", "codeium", "cursor", "mistral", "qwen", "xai",
}
# providers.dev's fixed lists (src/core/listings.ts, LISTED_MODALITIES and LISTED_LEVELS); the levels are also
# Provimux's liveModelListLevels (sdk/cliproxy/live_model_lists.go), the only levels a live list can carry.
MODALITIES = ("text", "image", "audio", "video", "pdf")
LEVELS = ("none", "minimal", "low", "medium", "high", "xhigh", "max")
STALE_DAYS = 3
MIN_SHARE = 0.6  # providers.dev refuses a file that lost more than 40 % of its providers or models
TIMEOUT = 30
REPO = "ngvoicu/groundtruth"
CONTENTS = f"repos/{REPO}/contents/listed.json"
MESSAGE = "discovery: listed.json"
IDENTITY = {"name": "groundtruth discovery", "email": "office@providers.dev"}
STATE = "discovery-state.json"
MODEL_FIELDS = ("id", "name", "context_window", "max_output", "input_modalities", "output_modalities", "reasoning")
# Login types whose list's window is not carried. Codex's `max_context_window` (872,000 in 2026-11) is the most a user
# may set in the Codex client, not what the service accepts (measured: about 921,500 accepted, 922,300 refused).
NO_WINDOW = {"codex"}


class Failure(Exception):
    """A reason to stop with exit 1; its text is safe to print (no key, no answer text)."""


class Conflict(Exception):
    """GitHub's file changed between the read and the PUT (HTTP 409 or 422)."""


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
    """The base URL, if it is http(s) to this Mac; else Failure."""
    parts = urllib.parse.urlsplit(base)
    host = parts.hostname or ""
    if parts.scheme not in ("http", "https") or not host:
        raise Failure("--base-url must be http(s)://<host>:<port> on this Mac")
    if host != "localhost":
        try:
            if not ipaddress.ip_address(host).is_loopback:
                raise ValueError
        except ValueError:
            raise Failure("refused: discovery reads only a Provimux on this Mac (127.0.0.1, ::1 or localhost)")
    return base.rstrip("/")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """A redirect is an error: the request, and its key, never go anywhere but the URL asked."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, "redirect refused", headers, fp)


def local_opener():
    """An opener with no proxy (whatever the environment or the system says) and no redirect."""
    return urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect()).open


def fetch(base, key, opener=None):
    """The one request. Its errors name the status or the kind of failure, never the answer's text or the key."""
    req = urllib.request.Request(local_only(base) + PATH, headers={"Authorization": "Bearer " + key,
                                                                   "Accept": "application/json"})
    try:
        with (opener or local_opener())(req, timeout=TIMEOUT) as resp:
            raw = resp.read(S.MAX_BYTES + 1)
    except urllib.error.HTTPError as err:
        hint = {401: " (the management key was refused)", 404: " (this Provimux has no model-lists endpoint: "
                "8.1.1-pmx.2 or later)", 503: " (the model-list status is not available yet)"}.get(err.code, "")
        if 300 <= err.code < 400:
            hint = " (a redirect: refused, the key is never sent on)"
        raise Failure(f"Provimux answered HTTP {err.code}{hint}")
    except (urllib.error.URLError, OSError) as err:
        raise Failure(f"Provimux could not be reached ({type(getattr(err, 'reason', err)).__name__})")
    if len(raw) > S.MAX_BYTES:
        raise Failure("Provimux's answer is larger than 8 MiB")
    try:
        return json.loads(raw)
    except ValueError:
        raise Failure("Provimux's answer is not JSON")


def management_keys():
    """(the key a request sends, every management key this Mac has): CPA_MGMT_KEY and the key file's MGMT_KEY."""
    keys = []
    env = os.environ.get("CPA_MGMT_KEY", "").strip()
    if env:
        keys.append(env)
    path = os.path.join(os.path.expanduser("~"), ".cli-proxy-api", "keys.txt")
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                if line.startswith("MGMT_KEY") and "=" in line:
                    value = line.split("=", 1)[1].strip()
                    if value and value not in keys:
                        keys.append(value)
                    break
    except OSError:
        pass
    return (keys[0] if keys else None), keys


# --- identity --------------------------------------------------------------------------------------------------------

def tokens(text):
    return re.findall(r"[a-z0-9]+", str(text).lower())


class Identities:
    """The identity values of an answer and the management keys. `holds(text)` is True when the text holds one."""

    def __init__(self, answer=None, keys=()):
        self.keys = [k.lower() for k in keys if isinstance(k, str) and k]
        raw = set(self.keys)
        for row in (answer.get("logins") if isinstance(answer, dict) else None) or []:
            if not isinstance(row, dict):
                continue
            raw.add(row.get("auth_index"))
            login = row.get("login") if isinstance(row.get("login"), dict) else {}
            for value in login.values():
                if not isinstance(value, str):
                    continue
                raw.add(value)
                if "@" in value:
                    raw.add(value.split("@", 1)[0])
                if "." in value:
                    raw.add(value.rsplit(".", 1)[0])
        self.sequences = set()
        for value in raw:
            seq = tuple(tokens(value)) if isinstance(value, str) else ()
            if seq and not all(t in SERVICE_WORDS for t in seq):
                self.sequences.add(seq)

    def holds(self, text):
        if not isinstance(text, str) or not text:
            return False
        lower = text.lower()
        if any(k in lower for k in self.keys):
            return True
        have = tokens(lower)
        for seq in self.sequences:
            n = len(seq)
            if any(tuple(have[i:i + n]) == seq for i in range(len(have) - n + 1)):
                return True
        return False


# --- from the answer to today's lists --------------------------------------------------------------------------------

def day_of(stamp):
    try:
        return dt.datetime.fromisoformat(str(stamp).replace("Z", "+00:00")).astimezone(dt.timezone.utc).date()
    except ValueError:
        return None


def modalities(values):
    """The fixed vocabulary only, in order, once each: a media type read as its kind (providers.dev's kinds())."""
    out = []
    for v in values if isinstance(values, list) else []:
        if not isinstance(v, str):
            continue
        lower = v.strip().lower()
        kind = "pdf" if lower == "application/pdf" else lower.split("/", 1)[0]
        if kind in MODALITIES and kind not in out:
            out.append(kind)
    return out


def levels(values):
    out = []
    for v in values if isinstance(values, list) else []:
        w = v.strip().lower() if isinstance(v, str) else ""
        if w in LEVELS and w not in out:
            out.append(w)
    return out


def clean(model, identities, dropped):
    """A model in the file's shape, with only discovery's fields, the vocabularies applied; None when it is dropped."""
    mid = model.get("id") if isinstance(model, dict) else None
    if not isinstance(mid, str):
        dropped.append("an entry without an id")
        return None
    name = model.get("name") if isinstance(model.get("name"), str) else ""
    if identities.holds(mid) or identities.holds(name):
        dropped.append("a model whose id or name holds an identity value (not shown)")
        return None
    problem = S.model_id_problem(mid)
    if problem:
        dropped.append(f"{mid if not S.unsafe(mid) and len(mid) <= 80 else '(an id not shown)'}: {problem}")
        return None
    out = {"id": mid}
    if name and not S.name_problem(name):
        out["name"] = name
    for key in ("context_window", "max_output"):
        if S.is_count(model.get(key)):
            out[key] = model[key]
    for key in ("input_modalities", "output_modalities"):
        words = modalities(model.get(key))
        if words:
            out[key] = words
    reasoning = model.get("reasoning") if isinstance(model.get("reasoning"), dict) else {}
    words = levels(reasoning.get("levels"))
    if words:
        out["reasoning"] = {"levels": words}
    return out


def vendor_model(login_type, entry, identities, dropped):
    """One entry of a vendor's list in the file's shape, or None. Only these fields of the entry are read."""
    if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
        dropped.append("an entry without an id")
        return None
    mid = entry["id"].strip()
    prefix = ROUTE_PREFIX.get(login_type)
    if prefix and mid.lower().startswith(prefix):
        mid = mid[len(prefix):]
    name = entry.get("display_name")
    window = None if login_type in NO_WINDOW else entry.get("context")
    return clean({"id": mid, "name": name.strip() if isinstance(name, str) else None,
                  "context_window": window, "max_output": entry.get("output"),
                  "input_modalities": entry.get("input_modalities"),
                  "output_modalities": entry.get("output_modalities"),
                  "reasoning": {"levels": entry.get("reasoning_levels")}}, identities, dropped)


def login_id(login_type, row):
    """A private, hashed identifier of a login (its auth_index, else its file name, e-mail or label); None without."""
    login = row.get("login") if isinstance(row.get("login"), dict) else {}
    for value in (row.get("auth_index"), login.get("name"), login.get("email"), login.get("label")):
        if isinstance(value, str) and value.strip():
            return hashlib.sha256(f"{login_type}\0{value.strip()}".encode()).hexdigest()[:24]
    return None


def complete_list(row):
    """(day, entries) when the row's list is complete; else (None, why)."""
    live = row.get("live") if isinstance(row.get("live"), dict) else {}
    entries = row.get("live_list")
    if live.get("held") is not True or live.get("expired") is True or not isinstance(entries, list) or not entries:
        return None, "no held list"
    day = day_of(live.get("fetched_at"))
    if day is None:
        return None, "no read time"
    stated = live.get("listed_models")
    if not isinstance(stated, int) or isinstance(stated, bool) or stated != len(entries):
        return None, "a list with fewer or more models than it says it listed"
    return day, entries


def today_lists(answer, known, identities, log, forget=False):
    """Per provider: {"lists": [(day, models)], "complete": bool}; and the logins to remember, by type."""
    if not isinstance(answer, dict) or not isinstance(answer.get("logins"), list):
        raise Failure("Provimux's answer has no list of logins: not a /provimux/model-lists answer")
    if (answer.get("options") or {}).get("live_lists") is False:
        log("Provimux's live lists are switched off (models.live-lists: false): no login has a list to read")
    seen = {t: set() for t in LISTINGS}
    enabled = {t: 0 for t in LISTINGS}
    lists = {t: [] for t in LISTINGS}
    why = {t: [] for t in LISTINGS}
    described_ids = {t: set() for t in LISTINGS}
    undescribed_ids = {t: set() for t in LISTINGS}
    skipped = 0
    for row in answer["logins"]:
        if not isinstance(row, dict):
            continue
        login_type = str(row.get("provider") or "").lower()
        if login_type not in LISTINGS:
            skipped += 1
            continue
        if "live_list" not in row:
            raise Failure("Provimux's answer has no live_list: it was not asked with view=live")
        ident = login_id(login_type, row)
        if ident:
            seen[login_type].add(ident)
        if row.get("disabled") is True:
            continue
        enabled[login_type] += 1
        day, entries = complete_list(row)
        if day is None:
            why[login_type].append(entries)
            continue
        dropped = []
        models = [m for m in (vendor_model(login_type, e, identities, dropped) for e in entries) if m]
        for d in sorted(set(dropped)):
            n = dropped.count(d)
            log(f"{LISTINGS[login_type]}: left out {d}" + (f" ({n} times)" if n > 1 else ""))
        # Only what the gateway describes is published; the list still counts as complete (checked above, on all).
        kept = [m for m in models if S.described(m)]
        described_ids[login_type].update(m["id"] for m in kept)
        undescribed_ids[login_type].update(m["id"] for m in models if not S.described(m))
        lists[login_type].append((day, kept))
    if skipped:
        log(f"skipped {skipped} row{'s' if skipped > 1 else ''} of login types discovery does not list")
    out, remember = {}, {}
    for login_type, provider in LISTINGS.items():
        undescribed = undescribed_ids[login_type] - described_ids[login_type]
        if undescribed:
            log(f"{provider}: left out {len(undescribed)} model{'' if len(undescribed) == 1 else 's'} the gateway "
                "lists without describing (an id only)")
        before = set(known.get(login_type) or [])
        absent = before - seen[login_type]
        if absent and forget:
            log(f"{provider}: forgot {len(absent)} login(s) absent today (--forget-absent)")
            before -= absent
            absent = set()
        remember[login_type] = sorted(before | seen[login_type])
        missing = enabled[login_type] - len(lists[login_type]) + len(absent)
        complete = enabled[login_type] > 0 and missing == 0
        if enabled[login_type] or absent:
            out[provider] = {"lists": lists[login_type], "complete": complete}
        if absent:
            log(f"{provider}: {len(absent)} login(s) seen before, absent from Provimux's answer: not a complete day "
                "(a login removed on purpose: --forget-absent)")
        for reason in sorted(set(why[login_type])):
            n = why[login_type].count(reason)
            log(f"{provider}: {n} enabled login(s): {reason}: not a complete day")
    return out, remember


# --- the file --------------------------------------------------------------------------------------------------------

def join(lists):
    """Today's lists of one type as one: by id, a field all who state it agree on (else not stated today)."""
    by_id, differing = {}, []
    for models in lists:
        for m in models:
            by_id.setdefault(m["id"], []).append(m)
    out = {}
    for mid, stated in by_id.items():
        model = {"id": mid}
        for k in MODEL_FIELDS[1:]:
            values = [m[k] for m in stated if k in m]
            if values and all(v == values[0] for v in values):
                model[k] = values[0]
            elif values:
                differing.append(f"{mid} {k}")
        out[mid] = model
    return out, differing


def ordered(model):
    return {k: model[k] for k in MODEL_FIELDS if k in model}


def merged(previous, today, identities, log):
    """The published file, with today's lists added; nothing removed but what may not be published."""
    old = dict((previous or {}).get("providers") or {})
    providers = {}
    for provider, part in sorted(old.items()):
        if provider in NOT_LISTED:
            log(f"{provider}: in GitHub's file, not listed by discovery: left out")
        elif provider not in LISTINGS.values():
            models = part.get("models") or []
            kept = [m for m in models if not (identities.holds(m.get("id")) or identities.holds(m.get("name")))]
            if len(kept) < len(models):
                log(f"{provider}: left out {len(models) - len(kept)} model(s) holding an identity value")
            if kept:
                providers[provider] = dict(part, models=kept)
    for provider in sorted(LISTINGS.values()):
        part = old.get(provider)
        dropped, models = [], {}
        for m in (part or {}).get("models") or []:
            c = clean(m, identities, dropped)
            if c:
                models[c["id"]] = c
        for d in sorted(set(dropped)):
            log(f"{provider}: GitHub's part: left out {d}")
        t = today.get(provider)
        if t is None:
            if part and models:
                providers[provider] = {"date": part["date"], "client": part.get("client", CLIENT),
                                       "models": [ordered(models[k]) for k in sorted(models)]}
                log(f"{provider}: no login today: kept the part of {part['date']}")
            continue
        if not part and not t["complete"]:
            log(f"{provider}: not published yet, and not a complete day: it waits for one")
            continue
        joined, differing = join([m for _, m in t["lists"]])
        if differing:
            log(f"{provider}: the logins' lists disagree on: {', '.join(sorted(differing))}: the published value stays")
        added = 0
        for mid, model in joined.items():
            if mid not in models:
                added += 1
                models[mid] = {}
            models[mid].update(model)
        date = part["date"] if part else None
        if t["complete"] and t["lists"]:
            read = min(d for d, _ in t["lists"]).isoformat()
            date = max(date or read, read)
        if not models:
            log(f"{provider}: no model the gateway describes: not in the file")
            continue
        providers[provider] = {"date": date, "client": CLIENT, "models": [ordered(models[k]) for k in sorted(models)]}
        log(f"{provider}: {len(models)} models ({added} new today), date {date}"
            f"{'' if t['complete'] else ' (kept: not a complete day)'}")
    return {"schema": S.SCHEMA, "repository": S.REPOSITORY, "providers": dict(sorted(providers.items()))}


def text_of(doc):
    """One model per line, so a day's change reads as a diff of models. ASCII only: bytes and characters agree."""
    dump = lambda v: json.dumps(v, ensure_ascii=True, separators=(", ", ": "))  # noqa: E731
    parts = []
    for provider, part in doc["providers"].items():
        models = ",\n".join("        " + dump(m) for m in part["models"])
        parts.append(f'    {dump(provider)}: {{"date": {dump(part["date"])}, "client": {dump(part["client"])}, '
                     f'"models": [\n{models}\n    ]}}')
    body = ",\n".join(parts)
    return (f'{{\n  "schema": {dump(doc["schema"])},\n  "repository": {dump(doc.get("repository", S.REPOSITORY))},\n'
            f'  "providers": {{\n{body}\n  }}\n}}\n')


def shrank(previous, doc):
    count = lambda d: (len(d["providers"]), sum(len(p["models"]) for p in d["providers"].values()))  # noqa: E731
    if not previous or not previous.get("providers"):
        return False
    (pp, pm), (np_, nm) = count(previous), count(doc)
    return np_ < pp * MIN_SHARE or nm < pm * MIN_SHARE


def build(previous, today, identities, log):
    """(doc, text): the new file, checked as providers.dev would check it."""
    doc = merged(previous, today, identities, log)
    if not doc["providers"]:
        raise Failure("no provider has a complete day yet, and GitHub has no listed.json: nothing written")
    errors = S.validate(doc)
    if errors:
        raise Failure("the file would not pass its schema: " + "; ".join(errors[:5]))
    text = text_of(doc)
    size = S.size_problem(text)
    if size:
        raise Failure(f"the file would be {size}: providers.dev would refuse it; not written")
    if shrank(previous, doc):
        raise Failure("the new file lost more than 40 % of the providers or models of GitHub's; providers.dev would "
                      "refuse it: not written")
    return doc, text


def exact_check(data, identities, home, scan=None):
    """The bytes about to be sent: the identity check, then harness/scan_secrets.py on a file of exactly those bytes."""
    try:
        text = data.decode("ascii")
        doc = json.loads(text)
    except (UnicodeDecodeError, ValueError):
        raise Failure("the bytes to publish are not ASCII JSON: not published")
    if any(k in text.lower() for k in identities.keys):
        raise Failure("the bytes to publish hold a management key: not published")
    for provider, part in doc["providers"].items():
        if identities.holds(provider) or any(identities.holds(m.get("id")) or identities.holds(m.get("name"))
                                             for m in part["models"]):
            raise Failure("the bytes to publish hold an identity value: not published")
    fd, path = tempfile.mkstemp(prefix=".listed-upload-", suffix=".json", dir=home)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        r = subprocess.run((scan or [sys.executable, "-B", os.path.join(HERE, "scan_secrets.py")]) + [path],
                           capture_output=True, text=True)
        with open(path, "rb") as f:
            same = f.read() == data
    finally:
        os.unlink(path)
    if r.returncode != 0 or not same:
        raise Failure("harness/scan_secrets.py found something in the bytes to publish: not published "
                      f"({(r.stdout.strip().splitlines() or ['no output'])[-1][:200]})")
    return (r.stdout.strip().splitlines() or ["clean"])[-1][:200]


# --- GitHub, through gh ------------------------------------------------------------------------------------------------

def gh(args, body=None):
    """`gh api --include ...`: (status, body bytes). gh is logged in on this Mac; nothing else is used to reach GitHub."""
    env = {k: v for k, v in os.environ.items() if k not in ("GH_REPO", "GH_DEBUG", "DEBUG", "GH_ENTERPRISE_TOKEN")}
    env.update(GH_HOST="github.com", GH_PROMPT_DISABLED="1", GH_NO_UPDATE_NOTIFIER="1", NO_COLOR="1")
    try:
        r = subprocess.run(["gh", "api", "--include", *args], input=body, capture_output=True, env=env, timeout=120)
    except FileNotFoundError:
        raise Failure("gh (GitHub's command line) is not on PATH")
    except subprocess.TimeoutExpired:
        raise Failure("gh did not answer within 2 minutes")
    out = r.stdout
    m = re.match(rb"HTTP/[0-9.]+ (\d{3})", out)
    if not m:
        line = (r.stderr.decode("utf-8", "replace").strip().splitlines() or ["no output"])[-1]
        raise Failure(f"gh gave no HTTP answer ({line[:160]})")
    ends = [i for i in (out.find(b"\r\n\r\n"), out.find(b"\n\n")) if i >= 0]
    return int(m.group(1)), out[min(ends):].lstrip(b"\r\n") if ends else b""


def blob_sha(data):
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def read_github():
    """(doc, sha, bytes) of listed.json on GitHub's main; (None, None, None) when there is none."""
    status, body = gh(["--method", "GET", "-H", "Accept: application/vnd.github+json", CONTENTS + "?ref=main"])
    if status == 404:
        return None, None, None
    if status != 200:
        raise Failure(f"GitHub answered HTTP {status} reading listed.json")
    try:
        meta = json.loads(body)
        sha = meta["sha"]
        if meta.get("encoding") == "base64" and meta.get("content"):
            data = base64.b64decode(meta["content"])
        else:  # a file over 1 MB: its blob, by the same sha
            status, body = gh(["--method", "GET", "-H", "Accept: application/vnd.github+json",
                               f"repos/{REPO}/git/blobs/{sha}"])
            if status != 200:
                raise Failure(f"GitHub answered HTTP {status} reading listed.json's blob")
            data = base64.b64decode(json.loads(body)["content"])
    except (ValueError, KeyError, TypeError):
        raise Failure("GitHub's answer for listed.json is not what the contents API gives")
    if blob_sha(data) != sha:
        raise Failure("GitHub's listed.json does not match its sha: not used")
    if len(data) > S.MAX_BYTES:
        raise Failure("GitHub's listed.json is larger than 8 MiB")
    try:
        doc = json.loads(data)
    except ValueError:
        raise Failure("GitHub's listed.json is not JSON: look at it first")
    errors = S.validate(doc)
    if errors:
        raise Failure(f"GitHub's listed.json does not pass its schema ({errors[0]}): look at it first")
    return doc, sha, data


def put_github(data, sha):
    """The new file on GitHub's main; the commit's short sha. Conflict on 409 or 422."""
    body = {"message": MESSAGE, "content": base64.b64encode(data).decode("ascii"), "branch": "main",
            "committer": dict(IDENTITY), "author": dict(IDENTITY)}
    if sha:
        body["sha"] = sha
    status, answer = gh(["--method", "PUT", CONTENTS, "--input", "-"], body=json.dumps(body).encode())
    if status in (409, 422):
        raise Conflict()
    if status not in (200, 201):
        raise Failure(f"GitHub refused the publication: HTTP {status}")
    try:
        return str(json.loads(answer)["commit"]["sha"])[:12]
    except (ValueError, KeyError, TypeError):
        return "?"


# --- $G's files ------------------------------------------------------------------------------------------------------

def write(path, text):
    """Through a temporary file unique to this run, then one rename (a symlink at `path` is replaced, never followed)."""
    folder = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(prefix=".discovery-", suffix=".tmp", dir=folder)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def read_state(home):
    path = os.path.join(home, STATE)
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except FileNotFoundError:
        return {}
    except OSError:
        raise Failure(f"$GROUNDTRUTH_CLIENT_HOME/{STATE} cannot be read (a link?): look at it first")
    try:
        with os.fdopen(fd, encoding="utf-8") as f:
            state = json.load(f)
    except ValueError:
        raise Failure(f"$GROUNDTRUTH_CLIENT_HOME/{STATE} is not JSON: look at it first")
    return state if isinstance(state, dict) else {}


def save_state(home, state, log):
    try:
        write(os.path.join(home, STATE), json.dumps(state, indent=1, sort_keys=True) + "\n")
    except OSError as err:
        log(f"could not save {STATE} ({type(err).__name__})")


def take_lock(home):
    try:
        fd = os.open(os.path.join(home, "discovery.lock"), os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
    except OSError:
        raise Failure("$GROUNDTRUTH_CLIENT_HOME/discovery.lock cannot be opened (a link?)")
    f = os.fdopen(fd, "r+")
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        f.close()
        raise Failure("another discovery run holds $GROUNDTRUTH_CLIENT_HOME/discovery.lock: this one stops")
    return f


def notify(text):
    """One macOS notification; never a stop when it cannot be shown."""
    try:
        subprocess.run(["osascript", "-e", "on run argv", "-e",
                        'display notification (item 1 of argv) with title "groundtruth discovery"', "-e", "end run",
                        text[:220]], capture_output=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        pass


def ages(published, today, state, log):
    """Logs every published provider's age; the asks (older than STALE_DAYS). One notification per stale part."""
    asks, new = [], []
    notified = state.setdefault("notified", {})
    for provider, date in sorted(published.items()):
        try:
            days = (today - dt.date.fromisoformat(date)).days
        except (TypeError, ValueError):
            days = None
        log(f"age: {provider} {days if days is not None else '?'} day{'' if days == 1 else 's'} (published {date})")
        if days is None or days > STALE_DAYS:
            asks.append(f"ASK: discovery has no fresh list for {provider}: "
                        f"{days if days is not None else 'unknown number of'} days old on GitHub (more than "
                        f"{STALE_DAYS}). Look at its logins on Provimux's model-lists status; then "
                        "`python3 $GROUNDTRUTH_CLIENT_HOME/bin/discover.py --publish`")
            if notified.get(provider) != date:
                new.append(provider)
                notified[provider] = date
        else:
            notified.pop(provider, None)
    for line in asks:
        log(line)
    if new:
        notify(f"listed.json: {', '.join(new)} older than {STALE_DAYS} days on GitHub (discovery.log has the asks)")
    return asks


# --- the command -----------------------------------------------------------------------------------------------------

def published_dates(doc):
    """The published parts' dates; a part discovery does not list (left out at the next publication) has no age."""
    return {p: part.get("date") for p, part in ((doc or {}).get("providers") or {}).items() if p not in NOT_LISTED}


def run(args, opener=None, key_finder=None, scan=None):
    """The whole command; returns (exit code, last words)."""
    home = os.environ.get("GROUNDTRUTH_CLIENT_HOME")
    if not home or not os.path.isdir(home):
        words = "discovery failed: GROUNDTRUTH_CLIENT_HOME must be an existing folder (discovery's files are there)"
        print(words, file=sys.stderr)
        return 1, words
    log = Log(args.log or os.path.join(home, "discovery.log"))
    today = dt.date.fromisoformat(args.date) if args.date else dt.date.today()
    state, lock, changed = {}, None, False
    try:
        lock = take_lock(home)
        state = read_state(home)
        log(f"discovery of {today.isoformat()}: {'saved answer' if args.answer else 'Provimux'}, "
            f"{'publish' if args.publish else 'no publication'}")
        request_key, keys = management_keys()
        if args.answer:
            with open(args.answer, encoding="utf-8") as f:
                answer = json.load(f)
        else:
            base = local_only(args.base_url)
            request_key = key_finder() if key_finder else request_key
            if not request_key:
                raise Failure("no management key: set CPA_MGMT_KEY, or a MGMT_KEY line in ~/.cli-proxy-api/keys.txt")
            keys = keys if request_key in keys else keys + [request_key]
            answer = fetch(base, request_key, opener)
        identities = Identities(answer, keys)
        today_parts, state["logins"] = today_lists(answer, state.get("logins") or {}, identities, log,
                                                   args.forget_absent)
        save_state(home, state, log)
        for attempt in (1, 2):
            previous, sha, raw = read_github()
            state["published"] = published_dates(previous)
            doc, text = build(previous, today_parts, identities, log)
            write(os.path.join(home, "listed.json"), text)
            data = text.encode("ascii")
            if raw == data or previous == doc:
                log("listed.json equals GitHub's: nothing to publish")
                break
            changed = True
            if not args.publish:
                log("wrote $GROUNDTRUTH_CLIENT_HOME/listed.json; not published (no --publish)")
                break
            log("checks of the exact bytes: " + exact_check(data, identities, home, scan))
            try:
                commit = put_github(data, sha)
            except Conflict:
                if attempt == 2:
                    raise Failure("GitHub's listed.json changed twice while publishing (HTTP 409/422): nothing "
                                  "published; the next run starts again from GitHub's")
                log("GitHub's listed.json changed meanwhile (HTTP 409/422): reading it again and rebuilding once")
                continue
            state["published"] = published_dates(doc)
            log(f"published listed.json on GitHub's main: commit {commit}")
            break
    except (Failure, OSError, ValueError) as err:
        text = str(err) if isinstance(err, Failure) else f"{type(err).__name__} reading the answer or a file"
        log(f"failed: {text}; nothing was published")
        lines = [f"discovery failed: {text}"]
        if args.publish:
            ask = (f"ASK: discovery could not publish listed.json ({text}). Look at "
                   "$GROUNDTRUTH_CLIENT_HOME/discovery.log; then "
                   "`python3 $GROUNDTRUTH_CLIENT_HOME/bin/discover.py --publish`")
            log(ask)
            lines.append(ask)
        lines += ages(state.get("published") or {}, today, state, log)
        save_state(home, state, log)
        return 1, "\n".join(lines)
    finally:
        if lock:
            lock.close()
    models = sum(len(p["models"]) for p in doc["providers"].values())
    published = args.publish and changed
    log(f"{'published' if published else 'wrote' if changed else 'unchanged:'} listed.json: "
        f"{len(doc['providers'])} providers, {models} models")
    asks = ages(state.get("published") or {}, today, state, log)
    save_state(home, state, log)
    words = (f"discovery: {len(doc['providers'])} providers, {models} models"
             f"{' (published)' if published else '' if changed else ' (unchanged)'}; "
             f"{len(asks)} ask{'' if len(asks) == 1 else 's'}")
    return 0, "\n".join([words] + asks)


def parser():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--base-url", default=os.environ.get("CPA_BASE_URL", "http://127.0.0.1:8317"),
                    help="the owner's Provimux on this Mac")
    ap.add_argument("--answer", help="a saved /provimux/model-lists?view=live answer: read instead of Provimux")
    ap.add_argument("--date", help="today, as YYYY-MM-DD (for the ages)")
    ap.add_argument("--log", help="the log file (default: $GROUNDTRUTH_CLIENT_HOME/discovery.log)")
    ap.add_argument("--publish", action="store_true", help="put listed.json on GitHub's main when it changed")
    ap.add_argument("--forget-absent", action="store_true",
                    help="forget the logins remembered but absent from today's answer (removed on purpose)")
    return ap


def main(argv=None):
    code, words = run(parser().parse_args(argv))
    print(words)
    return code


if __name__ == "__main__":
    sys.exit(main())
