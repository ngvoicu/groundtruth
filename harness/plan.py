#!/usr/bin/env python3
"""What a weekly Monday night measures, and in what order (docs/weekly-night.md; Provimux's design
`.github/provimux/design/model-lists.md`, section 9.2, with the owner's decisions of 2026-11-22 over it).

    python3 harness/plan.py --date 2026-11-30 --site-data <providers.dev data folder>      # the plan, printed
    python3 harness/plan.py --date 2026-11-30 --site-data <folder> --json                  # as JSON
    python3 harness/plan.py --date 2026-11-30 --site-data <folder> --write-values          # plan/values.json

Nothing is sent: the plan reads files (observed.json, plan/values.json, listed.json, the nights' result folders and
a copy of providers.dev's public dataset). harness/weekly.py reads providers.dev's dataset itself, from the site.

A **value** is one quantity of one model on one route: its cache lifetime (`cache`), its input window (`window`), its
output limit (`output`). The owner's rules of 2026-11-26: only models released in the **31 days before the night**,
and of those only the values **no source gives yet**. Every value offered on a route the night drives is in exactly
one state:

  new             planned: inside the window, a method for it, and no source gives it (providers.dev states no
                  documented value for it, from models.dev or the provider's own documentation; Pi's catalog states
                  none; we have not measured it)
  -  given        a source gives it: providers.dev's documented value (models.dev, or the provider's documentation as
                  providers.dev records it) or Pi's catalog (as providers.dev publishes it): never measured
  -  measured     we measured it already (our own source): never measured again
  -  unsteady     three measurements or more, no two agree: never measured again, and an ask (a decision)
  -  waiting      a measurement of it is in a night still waiting for its audit or its publication
  -  no method    the harness has no method for it on this route (named, never left out without a word)
  -  too old      released more than 31 days before the night: never measured
  -  no release date  no release date is known for the model: never measured, and PLAN.md and the morning report
                  name the model, so that nobody takes it for measured

The release date: providers.dev's entry on the route (`release_date`); else, for a login's own id, the `released` of
its row in the login's listing on providers.dev; else the release date of the lab's own model it names, when exactly
one is known (the lab's own entry, else the lab's listing row, else any entry naming that canonical model). The day
a model was first listed or discovered is not a release date: it orders the new ones (first seen since the last
night first), it never puts a model in the window. Cost is never a reason to leave a value out (the owner,
2026-11-26): an API-key value's worst case is worked out for the record (the night's estimate), never compared with
any cap.

The order of the new values: the models first seen since the last night first; then the newest release first; then
logins in the vendor's own list order and API keys cheapest first; then the id. The same inputs give the same plan.
"""
import argparse
import datetime as dt
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

# The routes a weekly night drives: two logins through their vendors' own clients, three API keys straight.
ROUTES = {
    "codex-subscription": {"kind": "login", "part": "codex", "client": "codex-cli", "provider": "openai-codex",
                           "label": "ChatGPT plan through Codex CLI"},
    "devin": {"kind": "login", "part": "devin", "client": "devin-cli", "provider": "devin",
              "label": "Devin subscription through the Devin CLI"},
    "openrouter": {"kind": "api_key", "part": "keys", "client": "direct", "provider": "openrouter",
                   "label": "OpenRouter key, straight"},
    "openai-api": {"kind": "api_key", "part": "keys", "client": "direct", "provider": "openai",
                   "label": "OpenAI key, straight"},
    "anthropic-api": {"kind": "api_key", "part": "keys", "client": "direct", "provider": "anthropic",
                      "label": "Anthropic key, straight"},
}
LOGIN_ROUTES = tuple(r for r, d in ROUTES.items() if d["kind"] == "login")
KEY_ROUTES = tuple(r for r, d in ROUTES.items() if d["kind"] == "api_key")
LOGIN_PROVIDERS = tuple(ROUTES[r]["provider"] for r in LOGIN_ROUTES)
PROVIDER_ROUTE = {d["provider"]: r for r, d in ROUTES.items()}
QUANTITIES = ("cache", "window", "output")
# Where the harness has a method (design 9.2): cache lifetimes on every route the night drives; windows on API-key
# routes (one request that should be refused); no window through the own clients yet; no output limit anywhere.
NO_METHOD = {("window", "login"): "no method yet: no window through the own clients (docs/own-clients.md 4.4)",
             ("output", "login"): "no method yet: the output limit is not measured",
             ("output", "api_key"): "no method yet: the output limit is not measured"}
# The clients whose runs count for a route (observed.json's client kinds): on an API key, only direct requests; on a
# login, direct requests and the vendor's own client. A proxy's runs (Provimux) are parity checks, never routine:
# they do not make a value measured.
COUNTING = {"api_key": ("direct",), "login": ("direct", "own_client")}
HARNESS_ROUTE = {"codex": "codex-subscription", "devin": "devin"}
EFFORT_SUFFIX = re.compile(r"-(?:none|minimal|low|medium|high|xhigh|max)$")

NEW, GIVEN, MEASURED, UNSTEADY = "new", "given by a source", "measured already", "unsteady"
WAITING, NO_METHOD_STATE, TOO_OLD, UNDATED = "waiting for its audit", "no method yet", "too old", "no release date"
PLANNED = (NEW,)
STATES = PLANNED + (GIVEN, MEASURED, UNSTEADY, WAITING, NO_METHOD_STATE, TOO_OLD, UNDATED)
WINDOW_DAYS = 31  # the owner, 2026-11-26: models released in the 31 days before the night
# Two window measurements agree within this share (a bracket's two ends, a count's rounding).
WINDOW_TOLERANCE = 0.01


def window_start(day):
    """The first day of the window of the night of `day` (a date): WINDOW_DAYS before it. A model released on that
    day or later is inside; the night's own date is the only clock (never today's)."""
    return day - dt.timedelta(days=WINDOW_DAYS)


def parse_day(s):
    try:
        return dt.date.fromisoformat(s[:10]) if isinstance(s, str) and len(s) >= 10 else None
    except ValueError:
        return None


def base_id(model):
    """A login's model id without the client's effort suffix (Devin's `-low`, `-none`)."""
    return EFFORT_SUFFIX.sub("", model)


def norm(model):
    """A model id compared across a login and a lab: lower case, dots as dashes, no effort suffix."""
    return base_id(model.lower()).replace(".", "-").replace("_", "-")


# --- providers.dev's dataset ----------------------------------------------------------------------------------------

def _num(x):
    return x if isinstance(x, (int, float)) and not isinstance(x, bool) else None


def _pi(entry, field):
    """pi.dev's value and standing for one field of an entry (providers.dev's verdict: agrees, differs, silent)."""
    for v in ((entry.get("providers_dev") or {}).get("pi") or {}).get("values") or []:
        if v.get("field") == field:
            return v.get("pi"), v.get("standing")
    return None, None


def summarize_entry(row, full=None):
    """What the plan needs of one providers.dev entry: its index row (`row`) and, for the night's own providers, its
    full record (`full`: pi.dev's values, the cache-write price)."""
    full = full or {}
    short = (row.get("cache_lifetime") or {}).get("short") or {}
    win = row.get("input_window") or {}
    cache_pi, cache_standing = _pi(full, "prompt_cache.short")
    win_pi, win_standing = _pi(full, "context_window")
    text = ((full.get("cost") or {}).get("text") or {})
    write = _num(((text.get("input") or {}).get("cache") or {}).get("write"))
    return {
        "provider": row["provider"], "model": row["model"], "type": row.get("type"),
        "release_date": row.get("release_date"), "canonical_id": row.get("canonical_id"),
        "price_in": _num(row.get("price_in")), "price_out": _num(row.get("price_out")), "price_write": write,
        "context": _num(row.get("context")), "input": _num(row.get("input")),
        "cache": {"documented": _num(short.get("documented_s")), "status": short.get("documented_status"),
                  "pi": _num(cache_pi), "pi_standing": cache_standing},
        "window": {"documented": _num(win.get("documented_tokens")), "status": win.get("documented_status"),
                   "pi": _num(win_pi), "pi_standing": win_standing},
        # providers.dev publishes no verdict on the output limit before its 1.4.0.
        "output": {"documented": _num(row.get("max_output")), "status": None, "pi": None, "pi_standing": None,
                   "unavailable": True},
    }


def load_site(folder):
    """providers.dev's dataset from a copy of its published `data` folder (index.json, entries/<provider>/<n>.json,
    and listings/<provider>.json where there is one)."""
    with open(os.path.join(folder, "index.json")) as f:
        index = json.load(f)

    def listing(provider):
        path = os.path.join(folder, "listings", f"{provider}.json")
        return _read_json(path) if os.path.isfile(path) else None
    return site_from(index, lambda provider, shard: _read_json(os.path.join(folder, "entries", provider,
                                                                            f"{shard}.json")), listing)


def _read_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def listing_rows(doc):
    """A provider's listing (`/data/listings/<provider>.json`, as `/api/v1/listings/<provider>`: {meta, data: {models:
    [...]}}) as the plan needs it: each row's id, its `released` day (None when it states none or not a whole day),
    its canonical id and owner."""
    data = doc.get("data") if isinstance(doc, dict) and isinstance(doc.get("data"), dict) else doc
    models = data.get("models") if isinstance(data, dict) else None
    rows = []
    for m in models if isinstance(models, list) else []:
        if not isinstance(m, dict) or not isinstance(m.get("id"), str):
            continue
        day = parse_day(m.get("released"))
        rows.append({"id": m["id"], "released": day.isoformat() if day else None,
                     "canonical": m.get("canonical") if isinstance(m.get("canonical"), str) else None,
                     "owner": m.get("owner") if isinstance(m.get("owner"), str) else None})
    return rows


def listing_providers(index, entries, login_rows=()):
    """The listings the plan reads: the logins' own (openai-codex, devin), every lab that is a provider of
    providers.dev and the lab of some entry's canonical id, and every owner a login's listing names."""
    known = {p.get("id") if isinstance(p, dict) else p for p in index.get("providers") or []}
    labs = {(e.get("canonical_id") or "").split("/", 1)[0] for e in entries.values() if "/" in (e.get("canonical_id")
                                                                                               or "")}
    owners = {r["owner"] for r in login_rows if r.get("owner")}
    return sorted((labs | owners) & known - set(LOGIN_PROVIDERS))


def site_from(index, shard_reader, listing_reader=None):
    """The plan's view of providers.dev: every entry's summary (by `provider/model`), with the full records of the
    night's own providers read through `shard_reader(provider, shard)`; and, with `listing_reader(provider)` (a
    listing's document, or None), the listings' rows of the logins and of the labs (listing_providers)."""
    shards = {}
    entries = {}
    for row in index.get("entries") or []:
        full = None
        if row.get("provider") in PROVIDER_ROUTE:
            key = (row["provider"], row.get("shard", 0))
            if key not in shards:
                shards[key] = shard_reader(*key) or {}
            full = shards[key].get(row["model"])
        entries[f"{row['provider']}/{row['model']}"] = summarize_entry(row, full)
    listings = {}
    if listing_reader:
        for p in LOGIN_PROVIDERS:
            rows = listing_rows(listing_reader(p))
            if rows:
                listings[p] = rows
        for p in listing_providers(index, entries, [r for p in listings for r in listings[p]]):
            rows = listing_rows(listing_reader(p))
            if rows:
                listings[p] = rows
    return {"dataset": index.get("dataset_version"), "generated_at": index.get("generated_at"), "entries": entries,
            "listings": listings}


def listed_release(site, provider, model):
    """The `released` day of a model's row in a provider's listing (its id exactly, else the one row whose normalized
    id is the model's), or None."""
    rows = (site.get("listings") or {}).get(provider) or []
    for r in rows:
        if r["id"] == model:
            return r["released"]
    days = {r["released"] for r in rows if norm(r["id"]) == norm(model)}
    if len(days) == 1:
        return next(iter(days))
    return None


def lab_dates(site):
    """normalized model id -> the set of release dates of the lab's own model: how a login's own id without a date
    of its own gets one. The lab's own entries (an entry whose provider is the lab of its canonical id) where there
    are any; else the lab's own listing rows (`released`, providers.dev's listings of the labs); else the entries of
    other providers that name the same canonical model (providers.dev holds many labs' models only through
    OpenRouter: `google/gemini-3.5-flash`), whose release date is the model's."""
    own, listed, named = {}, {}, {}
    for e in site["entries"].values():
        cid = e.get("canonical_id") or ""
        if "/" not in cid or not e.get("release_date"):
            continue
        lab, model = cid.split("/", 1)
        day = e["release_date"][:10]
        if e["provider"] == lab:
            own.setdefault(norm(model), set()).add(day)
            own.setdefault(norm(e["model"]), set()).add(day)
        else:
            named.setdefault(norm(model), set()).add(day)
    for lab, rows in (site.get("listings") or {}).items():
        if lab in LOGIN_PROVIDERS:
            continue
        for r in rows:
            cid = r.get("canonical") or ""
            # The lab's own model only: a row another owner's (a reseller listing a lab's model) or naming another
            # lab's canonical model is not this lab's date.
            if not r["released"] or (r.get("owner") or lab) != lab or ("/" in cid and not cid.startswith(lab + "/")):
                continue
            listed.setdefault(norm(r["id"]), set()).add(r["released"])
            if cid:
                listed.setdefault(norm(cid.split("/", 1)[1]), set()).add(r["released"])
    out = dict(named)
    out.update(listed)
    out.update(own)
    return out


# --- what is offered ------------------------------------------------------------------------------------------------

def listed_levels(m):
    """A listed.json model's reasoning levels (`reasoning.levels`, docs/discovery.md), in the vendor's order; [] when
    the list states no reasoning for it."""
    levels = (m.get("reasoning") or {}).get("levels") if isinstance(m.get("reasoning"), dict) else None
    return [x for x in levels if isinstance(x, str)] if isinstance(levels, list) else []


def offered(site, listed=None):
    """route -> the models offered there, in order, each {model, efforts, from}.
    Logins: listed.json (discovery, G1), in the vendor's own list order; without it, providers.dev's entries of the
    login (said in the plan). API keys: providers.dev's chat entries of openrouter, openai and anthropic.
    listed.json states no release date and no first-seen day (its schema allows neither, harness/listed_schema.py):
    a model's date comes from providers.dev and plan/values.json (release_of). Its reasoning levels are
    `reasoning.levels` (`efforts` here: [] when it states none, None when the list is not discovery's)."""
    out, notes = {}, []
    listed_providers = (listed or {}).get("providers") or {}
    for route, d in ROUTES.items():
        rows = []
        lp = listed_providers.get(d["provider"])
        if d["kind"] == "login" and lp and lp.get("models"):
            for m in lp["models"]:
                m = {"id": m} if isinstance(m, str) else m
                rows.append({"model": m["id"], "efforts": listed_levels(m), "from": "listed"})
        else:
            if d["kind"] == "login":
                notes.append(f"{route}: no list of {d['provider']} in listed.json (discovery, step G1, is not running "
                             "yet): the models offered are providers.dev's entries of the login")
            for ref in sorted(site["entries"]):
                e = site["entries"][ref]
                if e["provider"] != d["provider"] or (d["kind"] == "api_key" and e.get("type") != "chat"):
                    continue
                rows.append({"model": e["model"], "efforts": None, "from": "providers.dev"})
        out[route] = rows
    return out, notes


# --- what we measured -----------------------------------------------------------------------------------------------

def counting(observed, route, client):
    kind = (observed.get("client_kinds") or {}).get(client)
    return kind in COUNTING[ROUTES[route]["kind"]]


LIFETIME_SETTINGS = (("ttl",), ("prompt_cache_retention",), ("prompt_cache_options", "ttl"))
UNIT_S = {"s": 1, "m": 60, "h": 3600, "d": 86400}


def short_profile(options):
    """Whether a run measured the short retention profile, as providers.dev decides it (site/src/core/cache.ts,
    profileOf): no lifetime asked, or one of at most 5 minutes (the shortest any provider documents). The night asks
    for none, so only those runs count for its cache values; a run that asked for 1 hour or 24 hours measured another
    value (the long profile), which the night has no method for."""
    for path in LIFETIME_SETTINGS:
        v = options or {}
        for k in path:
            v = v.get(k) if isinstance(v, dict) else None
        if isinstance(v, str) and v:
            m = re.fullmatch(r"(\d+(?:\.\d+)?)([smhd])", v.strip())
            return bool(m) and float(m.group(1)) * UNIT_S[m.group(2)] <= 300
    return True


def measurements(observed):
    """(route, model, quantity) -> [{value, date, id}] of the published runs of the clients that count (for a cache
    lifetime, the runs of the short profile only)."""
    out = {}
    for c in observed.get("cache") or []:
        if c.get("route") in ROUTES and counting(observed, c["route"], c.get("client")) and \
                short_profile(c.get("options")):
            v = c.get("all_warm_through_s")
            out.setdefault((c["route"], c["model"], "cache"), []).append(
                {"value": v if v is not None else 0, "date": c.get("date"), "id": c.get("id")})
    for row in observed.get("limits") or []:
        if row.get("route") in ROUTES and counting(observed, row["route"], row.get("client")):
            v = row.get("context") or row.get("input_refused") or row.get("input_accepted")
            if v:
                out.setdefault((row["route"], row["model"], "window"), []).append(
                    {"value": v, "date": row.get("date"), "id": row.get("source")})
    for k in out:
        out[k].sort(key=lambda m: (m.get("date") or "", m.get("id") or ""))
    return out


def warm_at_two_hours(observed):
    """(route, model) whose last cache run of any client was still warm at 2 hours: its next run is `long`."""
    last = {}
    for c in observed.get("cache") or []:
        key = (c.get("route"), c.get("model"))
        if (c.get("date") or "") >= (last.get(key, {}).get("date") or ""):
            last[key] = c
    return {k for k, c in last.items() if (c.get("all_warm_through_s") or 0) >= 7200}


def pending_runs(root, observed):
    """(route, model, quantity) -> [night folder] of runs in a night's folder that observed.json does not hold yet
    and that no audit excluded: a night waiting for its audit or its publication."""
    published = {c.get("source") for c in observed.get("cache") or []}
    published |= {r.get("source") for r in observed.get("limits") or []}
    excluded = {e.get("id") for e in observed.get("excluded") or []}
    out = {}

    def add(key, folder):
        out.setdefault(key, []).append(folder)
    for top in sorted(glob.glob(os.path.join(root, "results", "own-clients-*")) +
                      sorted(glob.glob(os.path.join(root, "results", "night-*")))):
        folder = os.path.basename(top)
        listed = os.path.join(top, "runs.json")
        if os.path.isfile(listed):  # a weekly night: the runs it started, public
            for r in _read_json(listed).get("runs") or []:
                rel = r.get("file")
                if not rel or not os.path.exists(os.path.join(root, rel)) or rel in published:
                    continue
                if f"{folder}/{r.get('label')}" in excluded:
                    continue
                add((r["route"], r["model"], r.get("quantity", "cache")), folder)
            continue
        for path in sorted(glob.glob(os.path.join(top, "*.jsonl"))):  # the first night: the probe's files
            rel = os.path.relpath(path, root).replace(os.sep, "/")
            label = os.path.basename(path)[:-len(".jsonl")]
            if rel in published or f"{folder}/{label}" in excluded:
                continue
            try:
                with open(path) as f:
                    start = json.loads(f.readline() or "{}")
            except (OSError, ValueError):
                continue
            route = HARNESS_ROUTE.get(start.get("harness"))
            if route and start.get("model"):
                add((route, base_id(start["model"]), "cache"), folder)
    return out


# --- the sources -----------------------------------------------------------------------------------------------------

def verdict(e, quantity):
    """providers.dev's verdict on our value, worked out there and never again here: `disagree` (models.dev
    contradicted, or pi.dev differs), `agree` (a source states it and none disagrees), `none` (no source states it),
    or `unavailable` (no verdict published for this quantity yet). Kept in the plan for the record only: since
    2026-11-26 a measured value is never measured again, whatever the verdict."""
    if e is None:
        return "none"
    q = e[quantity]
    if q.get("unavailable"):
        return "unavailable"
    if q.get("status") == "contradicted" or q.get("pi_standing") == "differs":
        return "disagree"
    if q.get("status") == "not_contradicted" or q.get("pi_standing") == "agrees":
        return "agree"
    return "none"


def stated(e, quantity):
    """What models.dev and pi.dev state now for a value: {models_dev, pi}."""
    if e is None:
        return {"models_dev": None, "pi": None}
    return {"models_dev": e[quantity].get("documented"), "pi": e[quantity].get("pi")}


def given_by(e, quantity):
    """The sources that already give a value, read from providers.dev's entry on the route (`e`): its documented value
    (`documented`: models.dev's, or the provider's own documentation as providers.dev records it: for a cache lifetime
    `cache_lifetime.short.documented_s`, for a window `input_window.documented_tokens`, for an output limit
    `max_output`) and Pi's catalog (`pi`: the value providers.dev publishes from Pi, `prompt_cache.short` or
    `context_window`). A value of 0 is a value (a provider that documents no caching). [] when none gives it."""
    if e is None:
        return []
    q = e[quantity]
    out = []
    if q.get("documented") is not None:
        out.append(f"documented: {q['documented']}")
    if q.get("pi") is not None:
        out.append(f"Pi's catalog: {q['pi']}")
    return out


def same(quantity, a, b):
    if quantity == "window":
        return abs(a - b) <= WINDOW_TOLERANCE * max(a, b)
    return a == b


def agreeing_pair(quantity, values):
    """The value two of `values` share (the latest such), or None when no two agree."""
    for i in range(len(values) - 1, -1, -1):
        for j in range(i - 1, -1, -1):
            if same(quantity, values[i], values[j]):
                return values[i]
    return None


def state_of(quantity, ms, pending, given):
    """One value's state, inside the window and with a method (build decides those first): from its counting
    measurements (oldest first), the nights that hold it waiting, and the sources that give it (given_by)."""
    if pending:
        return WAITING
    if ms:
        values = [m["value"] for m in ms]
        if len(ms) >= 3 and agreeing_pair(quantity, values) is None:
            return UNSTEADY
        return MEASURED
    if given:
        return GIVEN
    return NEW


# --- the plan ---------------------------------------------------------------------------------------------------------

NO_DATE = "no release date known"


def release_of(route, row, site, labs):
    """(date, basis) of a model on a route: providers.dev's entry; else, for a login, the `released` of the model's
    row in the login's listing on providers.dev ("listed release"); else the lab's own model it names (lab_dates: the
    lab's own entry, else the lab's listing row, else an entry naming that model; exactly one date known); else
    (None, NO_DATE). The day a model was first listed is not its release date (the owner, 2026-11-26)."""
    e = site["entries"].get(f"{ROUTES[route]['provider']}/{row['model']}")
    if e and e.get("release_date"):
        return e["release_date"][:10], "release"
    if ROUTES[route]["kind"] == "login":
        day = listed_release(site, ROUTES[route]["provider"], row["model"])
        if day:
            return day, "listed release"
    dates = labs.get(norm(row["model"])) if ROUTES[route]["kind"] == "login" else None
    if dates and len(dates) == 1:
        return next(iter(dates)), "lab release"
    return None, NO_DATE


REQUESTS = {"std": 3 + 2 * 3 * 14, "long": 3 + 2 * 3 * 17}


def estimate_usd(e, schedule="std"):
    """The worst case of one API-key cache run, as on 18 November: every request (control 3, then priming and check
    3 per age) of 3,000 prompt tokens billed at the higher of the input and the cache-write price, plus 32 output
    tokens. None when providers.dev states no input price. For the record (the night's estimate), never a limit."""
    if not e or e.get("price_in") is None:
        return None
    requests = REQUESTS[schedule]
    pin = max(e["price_in"], e.get("price_write") or 0)
    return round((requests * 3000 * pin + requests * 32 * (e.get("price_out") or 0)) / 1e6, 4)


def window_words(e):
    """How large a window request is: 10 % above the larger documented figure, else 1.2 million words."""
    e = e or {}
    figures = [x for x in (e.get("context"), e.get("input"), (e.get("window") or {}).get("documented")) if x]
    return int(max(figures) * 1.1) + 1000 if figures else 1_200_000


def window_usd(e, words):
    """The worst case of a window request answered instead of refused: every word a token, at the input price."""
    if not e or e.get("price_in") is None:
        return None
    return round(words * e["price_in"] / 1e6, 4)


def value_key(text):
    """`<route>:<model>:<quantity>` (as --value takes it) -> `route|model|quantity`; None when it is not one."""
    route, _, rest = text.partition(":")
    model, _, q = rest.rpartition(":")
    if route not in ROUTES or not model or q not in QUANTITIES:
        return None
    return f"{route}|{model}|{q}"


def build(date, observed, site, values=None, listed=None, root=ROOT, last_night=None):
    """The plan of the night of `date` (YYYY-MM-DD, a Monday; the plan's only clock): every value offered on the
    night's routes with its state, the planned ones in order, the models with no release date (named, never
    measured), and the asks the plan raises (unsteady values)."""
    day = dt.date.fromisoformat(date)
    since = window_start(day)
    values = values or {}
    first_seen = values.get("first_seen") or {}
    last_night = last_night or values.get("last_night") or (day - dt.timedelta(days=7)).isoformat()
    offers, notes = offered(site, listed)
    ms_all = measurements(observed)
    pend = pending_runs(root, observed)
    long_warm = warm_at_two_hours(observed)
    labs = lab_dates(site)
    items, newly_seen = [], {}
    for route, rows in offers.items():
        kind = ROUTES[route]["kind"]
        for pos, row in enumerate(rows):
            model = row["model"]
            known = first_seen.get(route) or {}
            if model in known:
                seen = known[model]  # a day, or null: listed before discovery began
            else:
                newly_seen.setdefault(route, {})[model] = date
                seen = date
            released, basis = release_of(route, row, site, labs)
            e = site["entries"].get(f"{ROUTES[route]['provider']}/{model}")
            for q in QUANTITIES:
                key = f"{route}|{model}|{q}"
                ms = ms_all.get((route, model, q), [])
                given = given_by(e, q)
                item = {"key": key, "route": route, "model": model, "quantity": q, "position": pos,
                        "release": released, "release_basis": basis, "first_seen": seen,
                        "fresh": bool(seen) and seen > last_night, "count": len(ms),
                        "last_measured": ms[-1]["date"] if ms else None,
                        "oldest_measured": ms[0]["date"] if ms else None,
                        "values": [m["value"] for m in ms], "verdict": verdict(e, q), "given": given,
                        "pending": pend.get((route, model, q), []), "efforts": row.get("efforts")}
                rel = parse_day(released)
                if (q, kind) in NO_METHOD:
                    item["state"], item["why"] = NO_METHOD_STATE, NO_METHOD[(q, kind)]
                elif rel is None:
                    item["state"], item["why"] = UNDATED, "no release date known: not measured"
                elif rel < since:
                    item["state"], item["why"] = TOO_OLD, f"released {released} ({basis}), before {since.isoformat()}"
                else:
                    item["state"] = state_of(q, ms, item["pending"], given)
                    if item["state"] == GIVEN:
                        item["why"] = "; ".join(given)
                if kind == "api_key" and e:
                    item["prices"] = {"in": e.get("price_in"), "out": e.get("price_out"), "write": e.get("price_write")}
                if q == "cache":
                    item["schedule"] = "long" if (route, model) in long_warm else "std"
                    if kind == "api_key":
                        item["estimate_usd"] = estimate_usd(e, item["schedule"])
                elif q == "window" and kind == "api_key":
                    item["words"] = window_words(e)
                    item["estimate_usd"] = window_usd(e, item["words"])
                items.append(item)

    def sort_key(i):
        rel = parse_day(i["release"]) or dt.date.min
        cost = i.get("estimate_usd")
        return (0 if i["fresh"] else 1, -rel.toordinal(),
                i["position"] if ROUTES[i["route"]]["kind"] == "login" else (cost if cost is not None else 1e9),
                i["route"], i["model"], i["quantity"])
    planned = sorted((i for i in items if i["state"] in PLANNED), key=sort_key)
    asks = [{"kind": "unsteady-value", "route": i["route"], "model": i["model"], "quantity": i["quantity"],
             "values": i["values"]} for i in items if i["state"] == UNSTEADY]
    return {"date": date, "window_since": since.isoformat(), "window_days": WINDOW_DAYS, "last_night": last_night,
            "dataset": site.get("dataset"), "notes": notes, "items": items, "planned": planned, "asks": asks,
            "newly_seen": newly_seen, "undated": undated(items)}


def undated(items, routes=None):
    """The models offered with no release date known, once each: [(route, model)], in the plan's order of routes and
    the vendor's order. Never measured; named so that nobody takes them for measured."""
    out = []
    for i in items:
        if i["release"] is None and i["quantity"] == "cache" and (routes is None or i["route"] in routes):
            out.append((i["route"], i["model"]))
    return out


def estimate(planned):
    """The night's cost estimate from its planned API-key values (for the record: the log, PLAN.md and the morning
    report; never a limit): {cache: worst case of the cache runs, windows: the window checks' worst case if every one
    were answered (refused, as expected, they cost nothing), unpriced: values with no price known, runs: how many}."""
    cache = sum(i.get("estimate_usd") or 0.0 for i in planned
                if ROUTES[i["route"]]["kind"] == "api_key" and i["quantity"] == "cache")
    windows = sum(i.get("estimate_usd") or 0.0 for i in planned
                  if ROUTES[i["route"]]["kind"] == "api_key" and i["quantity"] == "window")
    unpriced = [i["key"] for i in planned if ROUTES[i["route"]]["kind"] == "api_key" and i.get("estimate_usd") is None]
    return {"cache": round(cache, 4), "windows": round(windows, 4), "unpriced": unpriced,
            "key_values": sum(1 for i in planned if ROUTES[i["route"]]["kind"] == "api_key"),
            "login_values": sum(1 for i in planned if ROUTES[i["route"]]["kind"] == "login")}


def estimate_line(est):
    """The estimate in words (the night's log, PLAN.md, the morning report)."""
    line = (f"Estimate: API keys ${est['cache']:.2f} at most for {est['key_values']} values (the cache runs' worst "
            f"case; the window checks are expected to be refused and cost nothing, ${est['windows']:.2f} if every one "
            f"were answered); logins: {est['login_values']} values on the subscriptions, no dollars.")
    if est["unpriced"]:
        line += f" No price known for {len(est['unpriced'])} of them: measured all the same, cost unknown."
    return line


def counts(plan):
    out = {}
    for i in plan["items"]:
        out.setdefault(i["route"], {}).setdefault(i["state"], 0)
        out[i["route"]][i["state"]] += 1
    return out


def undated_lines(pairs):
    """The models with no release date known, by route, each by name."""
    by = {}
    for route, model in pairs:
        by.setdefault(route, []).append(f"`{model}`")
    return [f"- {route} ({len(ms)}): {', '.join(ms)}" for route, ms in by.items()] or ["- none"]


def render(plan, limit=None):
    """The plan as Markdown (results/night-<date>/PLAN.md): public, model ids and states only."""
    lines = [f"# Plan of the night of {plan['date']}", "",
             f"providers.dev dataset `{plan['dataset']}`. Window: models released on or after {plan['window_since']} "
             f"(the {plan['window_days']} days before the night), and of those only the values no source gives. "
             f"Last night: {plan['last_night']}.", "", estimate_line(estimate(plan["planned"])), ""]
    for n in plan["notes"]:
        lines.append(f"- {n}")
    if plan["notes"]:
        lines.append("")
    lines += ["## Planned, in order", "", "| # | Route | Model | Value | State | Released | Run |",
              "|---|---|---|---|---|---|---|"]
    for n, i in enumerate(plan["planned"][:limit] if limit else plan["planned"], 1):
        run = i.get("schedule", "window request" if i["quantity"] == "window" else "")
        if i.get("estimate_usd") is not None:
            run += f", worst case ${i['estimate_usd']:.2f}"
        elif ROUTES[i["route"]]["kind"] == "api_key":
            run += ", no price known"
        lines.append(f"| {n} | {i['route']} | `{i['model']}` | {i['quantity']} | {i['state']}"
                     f"{' (first seen since the last night)' if i['fresh'] else ''} | "
                     f"{i['release']} ({i['release_basis']}) | {run} |")
    if not plan["planned"]:
        lines.append("| | | nothing to measure | | | | |")
    lines += ["", "## No release date known: not measured", "",
              "These models are offered, but no release date is known for them (providers.dev's entry, the login's "
              "listing, the lab's own model): the night does not measure them.", ""]
    lines += undated_lines(plan["undated"])
    lines += ["", "## Every value, by state", "", "| Route | " + " | ".join(STATES) + " |",
              "|---|" + "---|" * len(STATES)]
    for route, c in counts(plan).items():
        lines.append(f"| {route} | " + " | ".join(str(c.get(s, 0)) for s in STATES) + " |")
    since = plan["window_since"]
    lines += ["", "## Inside the window, given by a source", ""]
    lines += [f"- {i['route']} `{i['model']}` {i['quantity']}: {i['why']}" for i in plan["items"]
              if i["state"] == GIVEN] or ["- none"]
    lines += ["", "## No method yet, inside the window", ""]
    named = [i for i in plan["items"] if i["state"] == NO_METHOD_STATE and (i["release"] or "") >= since]
    lines += [f"- {i['route']} `{i['model']}` {i['quantity']}: {i['why']}" for i in named] or ["- none"]
    for title, state in (("Unsteady (an ask each)", UNSTEADY), ("Waiting for an audit or a publication", WAITING)):
        rows = [i for i in plan["items"] if i["state"] == state]
        lines += ["", f"## {title}", ""]
        lines += [f"- {i['route']} `{i['model']}` {i['quantity']}" + (f" ({', '.join(i['pending'])})"
                                                                     if i["pending"] else "") for i in rows] or ["- none"]
    return "\n".join(lines) + "\n"


# --- plan/values.json -------------------------------------------------------------------------------------------------

def values_file(observed, site, previous=None, today=None, first_seen=None, last_night=None):
    """plan/values.json, written at each publication: per measured value how often it was measured, when, its last
    value, and what models.dev and pi.dev stated on the day we measured it. A value whose count and date have not
    changed keeps what was stated then; a newly measured one records what the sources state today. The first time,
    every existing measurement records today's sources (else every old value would look moved). `first_seen` keeps,
    per route, the day each model was first listed or discovered."""
    previous = previous or {}
    old = previous.get("values") or {}
    out = {}
    for (route, model, q), ms in sorted(measurements(observed).items()):
        key = f"{route}|{model}|{q}"
        e = site["entries"].get(f"{ROUTES[route]['provider']}/{model}")
        rec = {"count": len(ms), "date": ms[-1]["date"], "value": ms[-1]["value"]}
        prev = old.get(key)
        if prev and prev.get("count") == rec["count"] and prev.get("date") == rec["date"]:
            rec["stated"], rec["stated_date"] = prev.get("stated"), prev.get("stated_date")
        else:
            rec["stated"], rec["stated_date"] = stated(e, q), today
        out[key] = rec
    seen = {r: dict(m) for r, m in (previous.get("first_seen") or {}).items()}
    for r, models in (first_seen or {}).items():
        for m, d in models.items():
            seen.setdefault(r, {}).setdefault(m, d)
    return {"schema": 1, "about": "What the weekly night's plan knows of each measured value (harness/plan.py): how "
            "often it was measured, when, our last value, and what models.dev and pi.dev stated on the day we "
            "measured it; and the day each offered model was first seen (null: listed before discovery began, "
            "2026-11-25, the day unknown). Written at each publication.",
            "dataset": site.get("dataset"), "last_night": last_night or previous.get("last_night"),
            "values": out, "first_seen": {r: dict(sorted(m.items())) for r, m in sorted(seen.items())}}


def record_baseline(values, plan):
    """Records as `first_seen: null` every login model that this plan sees for the first time and has no release date
    (neither providers.dev's nor its lab's): models already listed when discovery began, whose first-listed day is not
    known. Run once, on the first listed.json (2026-11-25). Since 2026-11-26 a model with no release date is never
    measured whatever its first-seen day; the record keeps the order of the new ones (first seen since the last
    night) honest. Returns how many."""
    fs = values.setdefault("first_seen", {})
    added = 0
    for i in plan["items"]:
        if i["quantity"] != "cache" or ROUTES[i["route"]]["kind"] != "login" or i["release_basis"] != NO_DATE:
            continue
        if i["model"] in (plan["newly_seen"].get(i["route"]) or {}):
            fs.setdefault(i["route"], {})[i["model"]] = None
            added += 1
    values["first_seen"] = {r: dict(sorted(m.items())) for r, m in sorted(fs.items())}
    return added


def load(path, default=None):
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def main(argv=None):
    ap = argparse.ArgumentParser(description="The weekly night's plan")
    ap.add_argument("--date", required=True)
    ap.add_argument("--site-data", required=True, help="a copy of providers.dev's published data folder")
    ap.add_argument("--observed", default=os.path.join(ROOT, "observed.json"))
    ap.add_argument("--values", default=os.path.join(ROOT, "plan", "values.json"))
    ap.add_argument("--listed", default=os.path.join(ROOT, "listed.json"))
    ap.add_argument("--last-night", help="the date of the last night (default: plan/values.json's, else a week before)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--write-values", action="store_true", help="write plan/values.json (at a publication)")
    ap.add_argument("--record-baseline", action="store_true",
                    help="record the login models listed before discovery began (no date known) in plan/values.json's "
                         "first_seen as null; changes nothing else")
    a = ap.parse_args(argv)
    site = load_site(a.site_data)
    observed = load(a.observed, {})
    values = load(a.values, {})
    plan = build(a.date, observed, site, values, load(a.listed), last_night=a.last_night)
    if a.record_baseline:
        added = record_baseline(values, plan)
        with open(a.values, "w") as f:
            f.write(json.dumps(values, indent=1, sort_keys=True) + "\n")
        print(f"wrote {os.path.relpath(a.values, ROOT)}: {added} models listed before discovery began")
        return
    if a.write_values:
        data = values_file(observed, site, values, today=a.date, first_seen=plan["newly_seen"],
                           last_night=a.last_night)
        os.makedirs(os.path.dirname(a.values), exist_ok=True)
        with open(a.values, "w") as f:
            f.write(json.dumps(data, indent=1, sort_keys=True) + "\n")
        print(f"wrote {os.path.relpath(a.values, ROOT)}: {len(data['values'])} values")
        return
    if a.json:
        print(json.dumps(plan, indent=1, default=str))
    else:
        sys.stdout.write(render(plan))


if __name__ == "__main__":
    main()
