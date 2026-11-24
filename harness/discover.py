#!/usr/bin/env python3
"""Discovery (step G1, Provimux's model-lists.md 9.1, way A): what each login's vendor offers today, into listed.json.

    python3 harness/discover.py                      # reads the owner's Provimux, writes ./listed.json; no commit
    python3 harness/discover.py --out FILE           # the same, into FILE
    python3 harness/discover.py --publish            # into discovery's own clone, committed and pushed to GitHub
    python3 harness/discover.py --answer FILE        # reads a saved answer instead of Provimux (nothing is sent)

What it does, in order:

1. **One local request**: `GET /v8/management/provimux/model-lists?view=live` to the owner's Provimux on this Mac
   (CPA_BASE_URL, default http://127.0.0.1:8317). The URL must be loopback, and the request goes through an opener
   with no proxy and no redirect (a redirect is an error), so the key never leaves this Mac. The management key is
   found as harness/pool.py finds it (CPA_MGMT_KEY, else the MGMT_KEY line of ~/.cli-proxy-api/keys.txt) and never
   printed or written. Nothing is sent to a vendor: Provimux has asked them already; groundtruth reads no token.
2. **Only what the vendor's list said**: per login, its `live_list` (the vendor's answer as it arrived, unmerged),
   only while Provimux holds it (`live.held`). From an entry only its id, name, window, output limit, modalities and
   reasoning levels are read; nothing of the row.
3. **No identity**: a model whose id or name contains an identity value of the answer (a login's label, e-mail or
   its local part, file name or its stem, `auth_index`) or the management key, compared without case, is dropped and
   the drop is logged without the value. Values of 3 characters or fewer and the names of providers and services
   (SERVICE_WORDS: a label "Devin" on a Devin login) do not count.
4. **A provider changes only on a complete day**: its part is rebuilt when every enabled login of its type has a
   held live list today; else yesterday's part stays as it was, date included (logged). The logins' lists are joined:
   the union of their models; a field two logins state differently is left out. The date is the oldest list's.
5. **Checked before it is written**: the schema (harness/listed_schema.py: providers.dev's `ListedFile`, its integer
   bounds included), the 8 MiB limit of providers.dev's sync, the key nowhere in the text, and providers.dev's shrink
   rule (no more than 40 % of the providers or models lost) against the file it compares with: with --publish the
   file on GitHub's main, else the file at --out.
6. **Ages**: every provider's age is logged (`$GROUNDTRUTH_CLIENT_HOME/discovery.log`, else --log, else stderr only).
   A provider older than 3 days is an ask: an `ASK:` line in the log and in the command's last words.
7. **--publish** (off by default) never touches the checkout it runs from. Discovery keeps its own clone of
   groundtruth at `$GROUNDTRUTH_CLIENT_HOME/discovery-repo` (made from GitHub on first use). Each run fetches GitHub,
   resets the clone to `upstream/main` and cleans it, writes listed.json there, and stops if it equals GitHub's.
   Otherwise harness/scan_secrets.py must pass on the file, listed.json alone is committed (as "groundtruth discovery
   <office@providers.dev>", never the Mac's own identity) and pushed to GitHub's main, without force. A refused push
   is redone once from a fresh fetch; a second refusal is exit 1, and the next day starts again from GitHub. Only
   GitHub is pushed: the NAS copy follows it by itself (.forgejo/workflows/follow-github.yml).
8. **One run at a time**: with $GROUNDTRUTH_CLIENT_HOME set, a lock (`discovery.lock`) makes a second run exit at
   once. Files are written through a temporary file unique to the run.

Exit: 0 written, unchanged or published (asks, if any, are in the last lines); 1 when Provimux could not be read, the
answer or a file is not usable, the new file would be refused by providers.dev, another run holds the lock, or the scan
or the publication failed.
"""
import argparse
import datetime as dt
import fcntl
import ipaddress
import json
import os
import subprocess
import sys
import tempfile
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
# discovery. Not here: Copilot (Provimux's list holds models the account does not offer; docs/discovery.md), Kimi
# (not asked by Provimux yet, 13.4), xAI, Gemini keys, Vertex and AI Studio (models.dev).
LISTINGS = {
    "antigravity": "antigravity",
    "claude": "claude-subscription",
    "codex": "openai-codex",
    "devin": "devin",
    "meta": "meta-subscription",
}
# Provimux shows a Devin id with its own route prefix (devin/<id>); Devin's own id, the one providers.dev lists, has none.
ROUTE_PREFIX = {"devin": "devin/"}
# Names of providers and services: an identity value equal to one of them (a login labelled "Devin") drops nothing.
SERVICE_WORDS = {
    "anthropic", "antigravity", "aistudio", "chatgpt", "claude", "codex", "copilot", "deepseek", "devin", "gemini",
    "github", "google", "grok", "kimi", "meta", "moonshot", "muse", "openai", "openrouter", "provimux", "vertex",
    "windsurf", "codeium", "cursor", "mistral", "qwen", "xai",
}
STALE_DAYS = 3
MAX_BYTES = S.MAX_BYTES  # providers.dev's sync refuses a larger file; also the most of an answer read
MIN_SHARE = 0.6  # providers.dev refuses a file that lost more than 40 % of its providers or models
TIMEOUT = 30
UPSTREAM_URL = "https://github.com/ngvoicu/groundtruth.git"
COMMITTER = ("groundtruth discovery", "office@providers.dev")


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
    """The base URL, if it is http(s) to this Mac; else Failure. Discovery reads the owner's Provimux and nothing else."""
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
            raw = resp.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as err:
        hint = {401: " (the management key was refused)", 404: " (this Provimux has no model-lists endpoint: "
                "8.1.1-pmx.2 or later)", 503: " (the model-list status is not available yet)"}.get(err.code, "")
        if 300 <= err.code < 400:
            hint = " (a redirect: refused, the key is never sent on)"
        raise Failure(f"Provimux answered HTTP {err.code}{hint}")
    except (urllib.error.URLError, OSError) as err:
        raise Failure(f"Provimux could not be reached ({type(getattr(err, 'reason', err)).__name__})")
    if len(raw) > MAX_BYTES:
        raise Failure("Provimux's answer is larger than 8 MiB")
    try:
        return json.loads(raw)
    except ValueError:
        raise Failure("Provimux's answer is not JSON")


# --- from the answer to the parts ------------------------------------------------------------------------------------

def day_of(stamp):
    try:
        return dt.datetime.fromisoformat(str(stamp).replace("Z", "+00:00")).astimezone(dt.timezone.utc).date()
    except ValueError:
        return None


def identity_values(answer, key=None):
    """Every identity value of the answer, and the key, lower case: login labels, e-mails and their local parts, file
    names and their stems, auth_index. Values of 3 characters or fewer and SERVICE_WORDS are not kept."""
    raw = {key} if isinstance(key, str) else set()
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
    out = set()
    for value in raw:
        if isinstance(value, str):
            value = value.strip().lower()
            if len(value) > 3 and value not in SERVICE_WORDS:
                out.add(value)
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
    return out[:S.MAX_WORDS]


def vendor_model(login_type, entry, dropped, identities):
    """One entry of a vendor's list as the file writes it, or None. Only the fields below are read."""
    if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
        dropped.append("an entry without an id")
        return None
    mid = entry["id"].strip()
    prefix = ROUTE_PREFIX.get(login_type)
    if prefix and mid.lower().startswith(prefix):
        mid = mid[len(prefix):]
    name = entry.get("display_name")
    name = name.strip() if isinstance(name, str) else ""
    if any(v in mid.lower() or v in name.lower() for v in identities):
        dropped.append("a model whose id or name holds an identity value (not shown)")
        return None
    problem = S.model_id_problem(mid)
    if problem:
        dropped.append(f"{mid if not S.unsafe(mid) and len(mid) <= 80 else '(an id not shown)'}: {problem}")
        return None
    out = {"id": mid}
    if name and not S.name_problem(name):
        out["name"] = name
    for src, dst in (("context", "context_window"), ("output", "max_output")):
        if S.is_count(entry.get(src)):
            out[dst] = entry[src]
    for key in ("input_modalities", "output_modalities"):
        words = words_of(entry.get(key))
        if words:
            out[key] = words
    levels = words_of(entry.get("reasoning_levels"))
    if levels:
        out["reasoning"] = {"levels": levels[:S.MAX_LEVELS]}
    return out


def join(lists):
    """The union of several logins' lists of one type. A field stays when all who state it agree."""
    by_id, differing = {}, []
    for models in lists:
        for m in models:
            by_id.setdefault(m["id"], []).append(m)
    out = []
    for mid in sorted(by_id):
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


def discovered(answer, log, identities=frozenset()):
    """provider -> {date, client, models} from the answer: the providers whose every enabled login has a held list."""
    if not isinstance(answer, dict) or not isinstance(answer.get("logins"), list):
        raise Failure("Provimux's answer has no list of logins: not a /provimux/model-lists answer")
    if (answer.get("options") or {}).get("live_lists") is False:
        log("Provimux's live lists are switched off (models.live-lists: false): no login has a list to read")
    enabled, complete, unmapped = {}, {}, 0
    for row in answer["logins"]:
        if not isinstance(row, dict):
            continue
        provider = LISTINGS.get(str(row.get("provider") or "").lower())
        if provider is None:
            unmapped += 1
            continue
        if "live_list" not in row:
            raise Failure("Provimux's answer has no live_list: it was not asked with view=live")
        if row.get("disabled") is True:
            continue
        enabled[provider] = enabled.get(provider, 0) + 1
        live = row.get("live") if isinstance(row.get("live"), dict) else {}
        if not isinstance(row.get("live_list"), list) or not row["live_list"] or live.get("held") is not True \
                or day_of(live.get("fetched_at")) is None:
            continue
        dropped = []
        models = [m for m in (vendor_model(str(row["provider"]).lower(), e, dropped, identities)
                              for e in row["live_list"]) if m]
        for d in sorted(set(dropped)):
            n = dropped.count(d)
            log(f"{provider}: left out {d}" + (f" ({n} times)" if n > 1 else ""))
        if models:
            complete.setdefault(provider, []).append((day_of(live["fetched_at"]), models))
    if unmapped:
        log(f"skipped {unmapped} row{'s' if unmapped > 1 else ''} of login types without a listed listing")
    out = {}
    for provider, n in sorted(enabled.items()):
        lists = complete.get(provider, [])
        if len(lists) < n:
            log(f"{provider}: {n - len(lists)} of {n} enabled logins have no live list today: the provider's part "
                "is kept as it was")
            continue
        models, differing = join([m for _, m in lists])
        if differing:
            log(f"{provider}: the logins' lists disagree, so these fields are left out: {', '.join(differing)}")
        out[provider] = {"date": min(d for d, _ in lists).isoformat(), "client": CLIENT, "models": models}
        log(f"{provider}: live lists of {len(lists)} login{'s' if len(lists) > 1 else ''}, {len(models)} models, "
            f"read {out[provider]['date']}")
    return out


# --- the file --------------------------------------------------------------------------------------------------------

def merged(previous, today, log):
    """The earlier file with today's parts in it. A provider without a part today keeps its part and date."""
    providers = dict((previous or {}).get("providers") or {})
    for provider, part in today.items():
        old = providers.get(provider)
        if old and old.get("date", "") > part["date"]:
            log(f"{provider}: today's lists were read {part['date']}, before the part already written "
                f"({old['date']}): kept")
            continue
        providers[provider] = part
    for provider in sorted(set(providers) - set(today)):
        log(f"{provider}: no new part today: kept the part of {providers[provider].get('date')}")
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


def check(doc, previous, key=None):
    """What providers.dev would refuse, and the key anywhere: all before anything is written. Returns the text."""
    errors = S.validate(doc)
    if errors:
        raise Failure("the file would not pass its schema: " + "; ".join(errors[:5]))
    text = text_of(doc)
    size = S.size_problem(text)
    if size:
        raise Failure(f"the file would be {size}: providers.dev would refuse it; not written")
    if key and key.lower() in text.lower():
        raise Failure("the file would hold the management key: not written")
    if shrank(previous, doc):
        raise Failure("the new file lost more than 40 % of the providers or models of the one it replaces; "
                      "providers.dev would refuse it: not written")
    return text


def shrank(previous, doc):
    count = lambda d: (len(d["providers"]), sum(len(p["models"]) for p in d["providers"].values()))  # noqa: E731
    if not previous or not previous.get("providers"):
        return False
    (pp, pm), (np_, nm) = count(previous), count(doc)
    return np_ < pp * MIN_SHARE or nm < pm * MIN_SHARE


def write(path, text):
    """Through a temporary file unique to this run, then one rename."""
    folder = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(prefix=".listed-", suffix=".tmp", dir=folder)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


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


def build(previous, parts, log, key=None):
    """The new document from the file it replaces; (doc, text)."""
    doc = merged(previous, parts, log)
    if not doc["providers"]:
        raise Failure("no provider has a complete set of live lists, and there is no earlier file: nothing written")
    return doc, check(doc, previous, key)


# --- publishing: discovery's own clone -------------------------------------------------------------------------------

def git(repo, *args):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["GIT_TERMINAL_PROMPT"] = "0"
    return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, env=env)


def last_line(r):
    return ((r.stderr or "").strip().splitlines() or (r.stdout or "").strip().splitlines() or ["?"])[-1][:200]


def fresh_clone(home, url, log):
    """$G/discovery-repo at GitHub's main, nothing else in it: made on first use, else fetched, reset and cleaned."""
    repo = os.path.join(home, "discovery-repo")
    if not os.path.isdir(os.path.join(repo, ".git")):
        if os.path.exists(repo):
            raise Failure(f"{repo} exists and is not a clone: move it away")
        r = git(home, "clone", "-q", "--origin", "upstream", url, repo)
        if r.returncode:
            raise Failure("the clone of groundtruth failed: " + last_line(r))
        log("made discovery's clone of groundtruth")
    for args in (("remote", "set-url", "upstream", url), ("fetch", "-q", "upstream"),
                 ("checkout", "-q", "-B", "main", "upstream/main"), ("reset", "-q", "--hard", "upstream/main"),
                 ("clean", "-q", "-fdx")):
        r = git(repo, *args)
        if r.returncode:
            raise Failure(f"git {args[0]} in discovery's clone failed: " + last_line(r))
    return repo


def commit_and_push(repo, path, date, log, scan=None):
    """True when pushed; False when the push was refused (Failure for anything else)."""
    scan = scan or [sys.executable, "-B", os.path.join(HERE, "scan_secrets.py"), path]
    r = subprocess.run(scan, capture_output=True, text=True)
    if r.returncode != 0:
        raise Failure("harness/scan_secrets.py found something in listed.json: not committed "
                      f"({(r.stdout.strip().splitlines() or ['no output'])[-1]})")
    log("scan: " + (r.stdout.strip().splitlines() or ["clean"])[-1])
    name, email = COMMITTER
    rel = os.path.relpath(path, repo)
    r = git(repo, "add", "--", rel)
    if r.returncode == 0:
        # The clone's own commit hook (scripts/pre-commit) runs too; the identity is fixed, never the Mac's.
        r = git(repo, "-c", f"user.name={name}", "-c", f"user.email={email}", "-c", "commit.gpgsign=false",
                "-c", "core.hooksPath=scripts", "commit", "-q", "-m", f"discovery: listed.json of {date}", "--", rel)
    if r.returncode != 0:
        raise Failure("the commit of listed.json failed: " + last_line(r))
    log("committed: " + git(repo, "log", "-1", "--format=%h %s").stdout.strip())
    r = git(repo, "push", "-q", "upstream", "HEAD:main")
    if r.returncode != 0:
        log("the push to GitHub was refused: " + last_line(r))
        return False
    log("pushed to GitHub's main")
    return True


def publish(home, url, parts, today, log, key=None, scan=None):
    """Writes listed.json in discovery's clone from GitHub's main and pushes it when it changed; one retry. The final
    document."""
    for attempt in (1, 2):
        repo = fresh_clone(home, url, log)
        path = os.path.join(repo, "listed.json")
        previous = read_previous(path)
        doc, text = build(previous, parts, log, key)
        if previous == doc:
            log("listed.json equals GitHub's: nothing to publish")
            return doc, False
        write(path, text)
        if commit_and_push(repo, path, today.isoformat(), log, scan):
            return doc, True
        if attempt == 1:
            log("starting again from a fresh fetch of GitHub")
    raise Failure("the push to GitHub was refused twice; nothing is left over: the next run starts from GitHub")


# --- the command -----------------------------------------------------------------------------------------------------

def take_lock(home):
    """An exclusive lock on $G/discovery.lock for the life of the process; Failure when another run holds it."""
    f = open(os.path.join(home, "discovery.lock"), "a+")
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        f.close()
        raise Failure("another discovery run holds $GROUNDTRUTH_CLIENT_HOME/discovery.lock: this one stops")
    return f


def run(args, opener=None, key_finder=None, scan=None):
    """The whole command; returns (exit code, last words)."""
    home = os.environ.get("GROUNDTRUTH_CLIENT_HOME")
    home = home if home and os.path.isdir(home) else None
    log = Log(args.log or (os.path.join(home, "discovery.log") if home else None))
    today = dt.date.fromisoformat(args.date) if args.date else dt.date.today()
    previous, lock, key = None, None, None
    try:
        if args.publish and args.out:
            raise Failure("--publish writes only in discovery's own clone: --out is refused with it")
        if args.publish and not home:
            raise Failure("--publish needs $GROUNDTRUTH_CLIENT_HOME, an existing folder (its discovery-repo is the "
                          "clone it publishes from)")
        out = None if args.publish else (args.out or os.path.join(os.getcwd(), "listed.json"))
        lock = take_lock(home) if home else None
        log(f"discovery of {today.isoformat()}: {'saved answer' if args.answer else 'Provimux'}, "
            f"{'publish from discovery-repo' if args.publish else 'file ' + os.path.basename(out)}")
        if out:
            previous = read_previous(out)
        if args.answer:
            with open(args.answer, encoding="utf-8") as f:
                answer = json.load(f)
        else:
            base = local_only(args.base_url)
            key = (key_finder or management_key)()
            answer = fetch(base, key, opener)
        parts = discovered(answer, log, identity_values(answer, key))
        if args.publish:
            doc, pushed = publish(home, args.upstream_url, parts, today, log, key, scan)
            changed = pushed
        else:
            doc, text = build(previous, parts, log, key)
            changed = previous != doc
            if changed:
                write(out, text)
    except (Failure, OSError, ValueError) as err:
        text = str(err) if isinstance(err, Failure) else f"{type(err).__name__} reading the answer or a file"
        log(f"failed: {text}; nothing was changed")
        if previous is None and args.publish and home:  # the ages of what GitHub has, as discovery's clone last saw it
            try:
                previous = read_previous(os.path.join(home, "discovery-repo", "listed.json"))
            except Failure:
                previous = None
        asks = ages(previous, today, log) if previous else []
        return 1, "\n".join([f"discovery failed: {text}"] + asks)
    finally:
        key = None
        if lock:
            lock.close()
    models = sum(len(p["models"]) for p in doc["providers"].values())
    verb = ("published" if changed else "unchanged") if args.publish else ("wrote" if changed else "unchanged:")
    log(f"{verb} listed.json: {len(doc['providers'])} providers, {models} models, {len(parts)} rebuilt today")
    asks = ages(doc, today, log)
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
    ap.add_argument("--out", help="the file to write without --publish (default: ./listed.json); refused with it")
    ap.add_argument("--date", help="today, as YYYY-MM-DD (for the ages)")
    ap.add_argument("--log", help="the log file (default: $GROUNDTRUTH_CLIENT_HOME/discovery.log)")
    ap.add_argument("--publish", action="store_true",
                    help="write in $GROUNDTRUTH_CLIENT_HOME/discovery-repo, commit and push to GitHub when it changed")
    ap.add_argument("--upstream-url", default=UPSTREAM_URL, help=argparse.SUPPRESS)  # the tests' local remote
    return ap


def main(argv=None):
    code, words = run(parser().parse_args(argv))
    print(words)
    return code


if __name__ == "__main__":
    sys.exit(main())
