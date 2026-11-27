#!/usr/bin/env python3
"""Cache lifetimes a real coding agent (Pi) gets through Provimux, with the account that answered every request.

The method is the one of the published `agent+cliproxyapi` runs (harness/probe.py with its Pi client, before
2026-11-22): each sample is a new Pi session whose first message carries a block no other sample has; after its age
the session is resumed once with a short message; the check is warm when the cache covers the prompt except at most
half of the block. Added here: a loopback relay between Pi and Provimux, one per Pi process, that records for every
request the `X-Provimux-Account` of the answer, the model the provider's answer names and the usage as reported, so
that a sample counts only when the intended login answered both its priming and its check.

    PROVIMUX_API_KEY=... python3 harness/agent_gateway.py --model claude-fable-5-2 --login claude \
        --ages 4,6,30,55,65 --extend 120 --replicas 3 --out <scratch>/raw --scratch <scratch>

The key comes from the environment only; it is never printed or written. Pi runs with PI_CODING_AGENT_DIR, HOME and
TMPDIR inside --scratch, cache warming off, the SSE transport (the relay reads per-request headers), and only the
pi-provimux extension. Every line of the output file is one request (or one decision), nothing dropped.
"""
import argparse
import datetime as dt
import fcntl
import hashlib
import http.client
import http.server
import json
import os
import random
import re
import subprocess
import sys
import threading
import time
import urllib.request
import uuid

GATEWAY = ("127.0.0.1", 8317)
DRY = os.environ.get("GT_DRY_DIR")  # a folder: model requests are written there and never sent
MODEL_PATHS = ("/v1/messages", "/v1/responses", "/v1/chat/completions", "/v1beta/models", "/backend-api/codex/responses")
FIRST_LINE = "groundtruth cache measurement {salt} (an automated test, not a task)."
ASK = "Reply with OK only. Do not use any tools."
SYLL = ["ka", "lo", "mi", "ne", "su", "ta", "ri", "po", "de", "fu", "ga", "hi", "jo", "ku", "ma", "no", "pe", "ra",
        "si", "to", "vu", "we", "ya", "zo", "bi", "ce", "da", "fe", "gu", "ho"]
LIMIT_WORDS = re.compile(r"overage|extra[ _-]usage|usage[ _-]limit|quota|rate[ _-]?limit|limit reached|out of credits"
                         r"|insufficient|billing|exceeded", re.I)
SECRETISH = re.compile(r"(sk-[A-Za-z0-9_\-]{8,}|Bearer\s+\S+|[A-Za-z0-9_\-]{32,})")


def now_iso(t=None):
    return dt.datetime.fromtimestamp(t if t is not None else time.time(), dt.timezone.utc).isoformat(timespec="milliseconds")


def block(salt, words):
    rnd = random.Random(salt)
    out, line = [], []
    for i in range(words):
        line.append("".join(rnd.choice(SYLL) for _ in range(rnd.randint(2, 4))))
        if len(line) == 12:
            out.append(" ".join(line) + ".")
            line = []
    if line:
        out.append(" ".join(line) + ".")
    return "\n".join(out)


# --- the relay ----------------------------------------------------------------------------------------------------

def _num(x):
    return x if isinstance(x, int) else 0


def normalise(usage):
    """(input incl. cached, cache_read, cache_write, output) from one usage object of any of the three formats."""
    if not isinstance(usage, dict):
        return None
    if "input_tokens" in usage and ("cache_read_input_tokens" in usage or "cache_creation_input_tokens" in usage):
        read, write = _num(usage.get("cache_read_input_tokens")), _num(usage.get("cache_creation_input_tokens"))
        return {"input": _num(usage.get("input_tokens")) + read + write, "cache_read": read, "cache_write": write,
                "output": _num(usage.get("output_tokens"))}
    if "input_tokens" in usage:  # Responses
        det = usage.get("input_tokens_details") or {}
        return {"input": _num(usage.get("input_tokens")), "cache_read": _num(det.get("cached_tokens")),
                "cache_write": None, "output": _num(usage.get("output_tokens"))}
    if "prompt_tokens" in usage:  # Chat Completions
        det = usage.get("prompt_tokens_details") or {}
        return {"input": _num(usage.get("prompt_tokens")), "cache_read": _num(det.get("cached_tokens")),
                "cache_write": _num(det.get("cache_write_tokens")) if "cache_write_tokens" in det else None,
                "output": _num(usage.get("completion_tokens"))}
    if "promptTokenCount" in usage:  # Gemini
        return {"input": _num(usage.get("promptTokenCount")), "cache_read": _num(usage.get("cachedContentTokenCount")),
                "cache_write": None, "output": _num(usage.get("candidatesTokenCount"))}
    return None


def read_answer(raw):
    """The model the answer names, every usage object it carries (raw), the merged usage, and event types."""
    model, usages, types = None, [], []
    anth_start = anth_delta = None
    texts = []
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            line = line[5:].strip()
        if not line.startswith("{"):
            continue
        texts.append(line)
    if not texts and raw.strip().startswith("{"):
        texts = [raw.strip()]
    for t in texts:
        try:
            ev = json.loads(t)
        except ValueError:
            continue
        typ = ev.get("type")
        if typ:
            types.append(typ)
        if typ == "message_start":
            msg = ev.get("message") or {}
            model = msg.get("model") or model
            anth_start = msg.get("usage")
            usages.append({"event": typ, "usage": anth_start})
        elif typ == "message_delta" and ev.get("usage"):
            anth_delta = ev["usage"]
            usages.append({"event": typ, "usage": anth_delta})
        elif isinstance(ev.get("response"), dict):
            r = ev["response"]
            model = r.get("model") or model
            if r.get("usage"):
                usages.append({"event": typ, "usage": r["usage"]})
        else:
            if ev.get("model"):
                model = ev.get("model") or model
            if ev.get("modelVersion"):
                model = ev["modelVersion"]
            for k in ("usage", "usageMetadata"):
                if isinstance(ev.get(k), dict) and ev[k]:
                    usages.append({"event": typ or "chunk", "usage": ev[k]})
    merged = None
    if anth_start is not None or anth_delta is not None:
        u = dict(anth_start or {})
        for k, v in (anth_delta or {}).items():
            if v is not None:
                u[k] = v
        merged = normalise(u)
    elif usages:
        merged = normalise(usages[-1]["usage"])
    return model, usages, merged, sorted(set(types))


class Relay:
    """One loopback relay to the gateway for one Pi process: forwards every request as it is, streams the answer
    back, and records what the answer says about who answered and what it used."""

    def __init__(self):
        self.records = []
        relay = self

        class H(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *a):
                pass

            def handle_any(self):
                t0 = time.time()
                n = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(n) if n else b""
                rec = {"t_start": now_iso(t0), "method": self.command, "path": self.path.split("?")[0],
                       "query": ("?" + self.path.split("?", 1)[1]) if "?" in self.path else ""}
                if body:
                    rec["request_bytes"] = len(body)
                    rec["request_sha256"] = hashlib.sha256(body).hexdigest()[:16]
                    try:
                        plain = body
                        if (self.headers.get("Content-Encoding") or "").lower() == "zstd":
                            from compression import zstd
                            plain = zstd.decompress(body)
                            rec["request_encoding"] = "zstd"
                        jb = json.loads(plain)
                        rec["requested_model"] = jb.get("model")
                        rec["stream"] = jb.get("stream")
                        s = json.dumps(jb)
                        rec["cache_control_ttls"] = sorted(set(re.findall(r'"ttl": "([^"]+)"', s)))
                        rec["cache_control_marks"] = s.count('"cache_control"')
                        for k in ("prompt_cache_key", "prompt_cache_retention", "previous_response_id"):
                            if k in jb:
                                rec[k] = "<set>" if k != "prompt_cache_retention" else jb[k]
                    except Exception:  # noqa: BLE001
                        pass
                if DRY and self.command == "POST":
                    with open(os.path.join(DRY, "dry-%d.json" % int(t0 * 1000)), "wb") as f:
                        f.write(body)
                    rec.update(status=400, error="dry run", t_end=now_iso())
                    relay.records.append(rec)
                    data = b'{"error":{"type":"invalid_request_error","message":"dry run"}}'
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(data)))
                    self.send_header("Connection", "close")
                    self.end_headers()
                    self.wfile.write(data)
                    self.close_connection = True
                    return
                fwd = {k: v for k, v in self.headers.items() if k.lower() not in ("host", "connection", "content-length",
                                                                                 "accept-encoding", "keep-alive")}
                fwd["Host"] = "%s:%d" % GATEWAY
                fwd["Accept-Encoding"] = "identity"
                if body:
                    fwd["Content-Length"] = str(len(body))
                try:
                    c = http.client.HTTPConnection(*GATEWAY, timeout=600)
                    c.request(self.command, self.path, body=body or None, headers=fwd)
                    r = c.getresponse()
                except Exception as e:  # noqa: BLE001
                    rec.update(status=None, error="relay: " + type(e).__name__, t_end=now_iso())
                    relay.records.append(rec)
                    self.send_error(502)
                    return
                rec["status"] = r.status
                hdrs = r.getheaders()
                hl = {k.lower(): v for k, v in hdrs}
                rec["account"] = hl.get("x-provimux-account")
                rec["auth_kind"] = hl.get("x-cpa-auth-kind")
                rec["auth_provider"] = hl.get("x-cpa-auth-provider")
                rec["header_names"] = sorted(hl)
                rec["limit_headers"] = {k: v for k, v in hl.items()
                                        if re.search(r"ratelimit|overage|quota|limit|retry|usage", k)}
                self.send_response(r.status)
                for k, v in hdrs:
                    if k.lower() in ("transfer-encoding", "connection", "content-length", "keep-alive"):
                        continue
                    self.send_header(k, v)
                self.send_header("Connection", "close")
                self.end_headers()
                buf = bytearray()
                while True:
                    chunk = r.read1(65536) if hasattr(r, "read1") else r.read(65536)
                    if not chunk:
                        break
                    if len(buf) < 4_000_000:
                        buf += chunk
                    try:
                        self.wfile.write(chunk)
                        self.wfile.flush()
                    except OSError:
                        break
                self.close_connection = True
                rec["t_end"] = now_iso()
                text = buf.decode("utf-8", "replace")
                if rec["path"].startswith(MODEL_PATHS) or rec["method"] == "POST":
                    model, usages, merged, types = read_answer(text)
                    rec.update(answer_model=model, usage_raw=usages, usage=merged, event_types=types)
                    if r.status >= 400 or "error" in types:
                        rec["error_text"] = SECRETISH.sub("<redacted>", text[:600])
                    if LIMIT_WORDS.search(text) and (r.status >= 400 or "error" in types):
                        rec["limit_sign"] = True
                if any(LIMIT_WORDS.search(k + " " + str(v)) for k, v in rec["limit_headers"].items()):
                    rec["limit_header_sign"] = True
                relay.records.append(rec)

            do_GET = do_POST = do_PUT = do_DELETE = do_PATCH = handle_any

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *a):
        self.server.shutdown()
        self.server.server_close()


# --- Pi -----------------------------------------------------------------------------------------------------------

def sandbox_profile(scratch):
    home = os.path.realpath(os.path.expanduser("~"))
    return ('(version 1)(allow default)(deny file-write* (subpath "%s"))'
            '(allow file-write* (subpath "%s"))' % (home, os.path.realpath(scratch)))


class Pi:
    def __init__(self, a, key):
        self.a, self.key = a, key
        self.agent = os.path.join(a.scratch, "agent-" + re.sub(r"[^A-Za-z0-9.-]", "_", a.model))
        self.sessions = os.path.join(a.scratch, "sessions")
        self.work = os.path.join(a.scratch, "work")
        for d in (self.agent, self.sessions, self.work, os.path.join(a.scratch, "home"), os.path.join(a.scratch, "tmp")):
            os.makedirs(d, mode=0o700, exist_ok=True)
        settings = os.path.join(self.agent, "settings.json")
        want = {"cacheWarming": "off", "transport": "sse", "defaultThinkingLevel": a.thinking, "quietStartup": True}
        with open(settings, "w") as f:
            json.dump(want, f)

    def env(self, port):
        e = {k: os.environ[k] for k in ("PATH", "USER", "LANG", "TERM") if k in os.environ}
        e.update(HOME=os.path.join(self.a.scratch, "home"), TMPDIR=os.path.join(self.a.scratch, "tmp"),
                 PI_CODING_AGENT_DIR=self.agent, PI_SKIP_VERSION_CHECK="1", PROVIMUX_BASE_URL=f"http://127.0.0.1:{port}",
                 PROVIMUX_API_KEY=self.key, PROVIMUX_FAST="false")
        return e

    def run(self, session, text):
        with Relay() as relay:
            argv = ["pi", "-p", "--no-extensions", "-e", self.a.extension, "--no-skills", "--no-prompt-templates",
                    "--no-context-files", "--session-dir", self.sessions, "--session-id", session,
                    "--model", f"provimux/{self.a.model}", "--thinking", self.a.thinking, text]
            if sys.platform == "darwin":
                argv = ["sandbox-exec", "-p", sandbox_profile(self.a.scratch)] + argv
            t0 = time.time()
            try:
                p = subprocess.run(argv, env=self.env(relay.port), cwd=self.work, capture_output=True, text=True,
                                   timeout=600, stdin=subprocess.DEVNULL)
                code, out, err = p.returncode, p.stdout, p.stderr
            except subprocess.TimeoutExpired:
                code, out, err = "timeout", "", ""
            t1 = time.time()
        calls = [r for r in relay.records if r["method"] == "POST" and r["path"].startswith(MODEL_PATHS)]
        others = [{"method": r["method"], "path": r["path"], "status": r.get("status")} for r in relay.records
                  if r not in calls]
        redact = lambda s: SECRETISH.sub("<redacted>", (s or "")[-400:])  # noqa: E731
        return {"t_start": now_iso(t0), "t0": t0, "t_end": now_iso(t1), "exit": code, "stdout": redact(out).strip(),
                "stderr": redact(err).strip() if code else "", "requests": calls, "other_requests": others}


# --- the run ------------------------------------------------------------------------------------------------------

class Run:
    def __init__(self, a):
        self.a = a
        key = os.environ.get("PROVIMUX_API_KEY")
        if not key:
            raise SystemExit("PROVIMUX_API_KEY is not set")
        self.key = key
        self.pi = Pi(a, key)
        self.out = open(a.outfile, "a", buffering=1)
        self.lockfile = open(os.path.join(a.scratch, f"login-{a.login}.lock"), "a")
        self.stop_reason = None
        self.fails = 0
        self.cost = 0.0
        self.tokens = {"requests": 0, "input": 0, "cache_read": 0, "cache_write": 0, "output": 0}

    def log(self, rec):
        rec.setdefault("model", self.a.model)
        rec.setdefault("login", self.a.login)
        self.out.write(json.dumps(rec) + "\n")

    def accounts(self):
        req = urllib.request.Request("http://%s:%d/v1/models?include=accounts" % GATEWAY,
                                     headers={"Authorization": "Bearer " + self.key})
        data = json.load(urllib.request.urlopen(req, timeout=30))["data"]
        m = next((x for x in data if x["id"] == self.a.model), None)
        if not m:
            raise SystemExit(f"{self.a.model}: not listed by the gateway")
        accts = m.get("accounts") or []
        intended = sorted({x["account"] for x in accts if x.get("provider") == self.a.login and x.get("kind") == "oauth"})
        return accts, intended

    def invoke(self, role, sample, text):
        fcntl.flock(self.lockfile, fcntl.LOCK_EX)  # one request at a time on this login, across models
        try:
            res = self.pi.run(sample, text)
        finally:
            fcntl.flock(self.lockfile, fcntl.LOCK_UN)
        reqs = res["requests"]
        rec = {"kind": "request", "role": role, "sample": sample, **{k: v for k, v in res.items() if k != "t0"}}
        rec["calls"] = len(reqs)
        last = reqs[-1] if reqs else {}
        rec["account"] = last.get("account")
        rec["answer_model"] = last.get("answer_model")
        rec["usage"] = last.get("usage")
        rec["status"] = last.get("status")
        signs = [r for r in reqs if r.get("limit_sign") or r.get("limit_header_sign")]
        kinds = {r.get("auth_kind") for r in reqs if r.get("auth_kind")}
        if signs:
            self.stop_reason = "limit or overage sign in an answer"
        if "apikey" in kinds:
            self.stop_reason = "an API key (paid route) answered"
        self.spend(reqs)
        if self.cost > self.a.budget:
            self.stop_reason = f"list-price budget reached ({self.cost:.2f} of {self.a.budget:.2f} USD)"
        ok = res["exit"] == 0 and last.get("status") == 200 and rec["usage"]
        self.fails = 0 if ok else self.fails + 1
        if self.fails >= 4:
            self.stop_reason = "four failed requests in a row"
        return rec, res["t0"]

    def spend(self, reqs):
        a = self.a
        for r in reqs:
            u = r.get("usage") or {}
            if not u:
                continue
            self.tokens["requests"] += 1
            w = u.get("cache_write") or 0
            fresh = max(u["input"] - u["cache_read"] - w, 0)
            for k, v in (("input", u["input"]), ("cache_read", u["cache_read"]), ("cache_write", w), ("output", u["output"])):
                self.tokens[k] += v
            self.cost += (fresh * a.price_in + u["cache_read"] * a.price_cached + w * a.price_write
                          + u["output"] * a.price_out) / 1e6

    def warm(self, prime, check):
        u, pu = check.get("usage") or {}, prime.get("usage") or {}
        if not u or not pu or self.baseline is None:
            return None
        blk = max(pu["input"] - self.baseline, 0)  # the block, as the provider counts it
        return u["cache_read"] >= self.baseline + blk / 2

    def counted(self, prime, check):
        why = []
        for name, r in (("prime", prime), ("check", check)):
            if r["calls"] != 1:
                why.append(f"{name}: {r['calls']} model requests")
            if r.get("status") != 200 or not r.get("usage"):
                why.append(f"{name}: no answer (status {r.get('status')}, exit {r.get('exit')})")
            if r.get("account") not in self.intended:
                why.append(f"{name}: answered by {r.get('account')} (not the intended login)")
        for name, r in (("prime", prime), ("check", check)):
            m = (r.get("answer_model") or "").lower()
            if m and not (m == self.a.model.lower() or m.startswith(self.a.model.lower().rsplit("-low", 1)[0])):
                why.append(f"{name}: the answer names another model")
        if prime.get("account") and check.get("account") and prime["account"] != check["account"]:
            why.append("prime and check answered by different accounts")
        return (not why), why

    def main(self):
        a = self.a
        accts, self.intended = self.accounts()
        self.log({"kind": "start", "t": now_iso(), "accounts": accts, "intended": self.intended, "ages_min": a.ages,
                  "extend_min": a.extend, "replicas": a.replicas, "words": a.words, "thinking": a.thinking,
                  "pi": subprocess.run(["pi", "--version"], capture_output=True, text=True).stdout.strip(),
                  "provimux": subprocess.run(["provimux", "-v"], capture_output=True, text=True).stdout.strip()[:120],
                  "pi_provimux": json.load(open(os.path.join(a.extension, "package.json")))["version"],
                  "transport": "sse", "cache_warming": "off"})
        if not self.intended:
            raise SystemExit("no login of that kind serves the model")
        time.sleep(a.delay)
        tag = uuid.uuid4().hex[:8]
        # baseline: Pi's own prompt without a block
        b, _ = self.invoke("baseline", f"gt-{tag}-base", ASK)
        self.log(b)
        self.baseline = (b.get("usage") or {}).get("input")
        if self.stop_reason or not self.baseline:
            return self.end(self.stop_reason or "no baseline")

        def prime(sid):
            text = FIRST_LINE.format(salt=sid) + "\n\n" + block(sid, a.words) + "\n\n" + ASK
            r, t0 = self.invoke("prime", sid, text)
            self.log(r)
            return r, t0

        def check(sid, pr, t0, age_s, role="check"):
            r, t1 = self.invoke(role, sid, ASK)
            r["target_age_s"] = age_s
            r["age_s"] = round(t1 - t0, 1)
            ok, why = self.counted(pr, r)
            r["counted"], r["not_counted_because"] = ok, why
            r["warm"] = self.warm(pr, r)
            r["prime_usage"] = pr.get("usage")
            r["baseline_input"] = self.baseline
            self.log(r)
            return r

        # control: primed, checked at 30 s; a cold one gets one more, in a fresh session (as harness/probe.py)
        for k in range(2):
            cid = f"gt-{tag}-c{k}"
            cp, ct0 = prime(cid)
            if self.stop_reason:
                return self.end(self.stop_reason)
            time.sleep(max(0, ct0 + 30 - time.time()))
            c = check(cid, cp, ct0, 30, role="control")
            if self.stop_reason:
                return self.end(self.stop_reason)
            if c["warm"]:
                break
        else:
            return self.end("no observable cache: both controls cold")
        # every sample primed once, up front (the extension's too, so no 2-hour wait after 65 minutes)
        plan = [(age, r) for age in a.ages + ([a.extend] if a.extend and not a.lazy_extend else [])
                for r in range(a.replicas)]
        primed = []
        for age, rep in plan:
            sid = f"gt-{tag}-{age}m-{rep}"
            pr, t0 = prime(sid)
            primed.append({"sid": sid, "age": age, "prime": pr, "t0": t0})
            if self.stop_reason:
                return self.end(self.stop_reason)
            time.sleep(a.gap)
        primed.sort(key=lambda s: s["t0"] + s["age"] * 60)
        results = {}
        for s in primed:
            if s["age"] == a.extend:
                last = [r for (age, _), r in results.items() if age == max(a.ages) and r.get("counted")]
                if not any(r.get("warm") for r in last):
                    self.log({"kind": "not-checked", "sample": s["sid"], "target_age_s": s["age"] * 60,
                              "reason": f"no counted {max(a.ages)}-minute check read the cache"})
                    continue
            time.sleep(max(0, s["t0"] + s["age"] * 60 - time.time()))
            results[(s["age"], s["sid"])] = check(s["sid"], s["prime"], s["t0"], s["age"] * 60)
            if self.stop_reason:
                return self.end(self.stop_reason)
        if a.extend and a.lazy_extend:
            last = [r for (age, _), r in results.items() if age == max(a.ages) and r.get("counted")]
            if not any(r.get("warm") for r in last):
                self.log({"kind": "not-primed", "target_age_s": a.extend * 60,
                          "reason": f"no counted {max(a.ages)}-minute check read the cache"})
                return self.end("done")
            ext = []
            for rep in range(a.replicas):
                sid = f"gt-{tag}-{a.extend}m-{rep}"
                pr, t0 = prime(sid)
                ext.append((sid, pr, t0))
                if self.stop_reason:
                    return self.end(self.stop_reason)
                time.sleep(a.gap)
            for sid, pr, t0 in ext:
                time.sleep(max(0, t0 + a.extend * 60 - time.time()))
                check(sid, pr, t0, a.extend * 60)
                if self.stop_reason:
                    return self.end(self.stop_reason)
        return self.end("done")

    def end(self, why):
        self.log({"kind": "end", "t": now_iso(), "reason": why, "used": self.tokens,
                  "list_price_usd": round(self.cost, 4)})
        print(f"{self.a.model}: {why}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--login", required=True, help="the provider of the intended login in include=accounts")
    ap.add_argument("--ages", required=True, help="minutes, comma-separated")
    ap.add_argument("--extend", type=float, default=0, help="minutes; checked only if a counted last-age check was warm")
    ap.add_argument("--replicas", type=int, default=3)
    ap.add_argument("--words", type=int, default=700)
    ap.add_argument("--thinking", default="low")
    ap.add_argument("--delay", type=float, default=0)
    ap.add_argument("--gap", type=float, default=2)
    ap.add_argument("--scratch", required=True)
    ap.add_argument("--extension", required=True, help="the pi-provimux package Pi loads")
    ap.add_argument("--outfile", required=True)
    ap.add_argument("--budget", type=float, required=True, help="USD at list prices; the run stops when it is reached")
    ap.add_argument("--lazy-extend", action="store_true", help="prime the extension only after a warm last age")
    for k in ("in", "cached", "write", "out"):
        ap.add_argument(f"--price-{k}", type=float, required=True, help="USD per million tokens")
    a = ap.parse_args()
    a.ages = [float(x) if "." in x else int(x) for x in a.ages.split(",")]
    a.extend = int(a.extend) if a.extend == int(a.extend) else a.extend
    Run(a).main()


if __name__ == "__main__":
    main()
