"""What discovery's tests share: a private $G, HOME and PATH per test, a fake `gh` (GitHub's contents API on a folder,
fixtures/discovery/fake_gh.py) and a fake `osascript` first on PATH, fake Provimux servers on free loopback ports.
No test reaches GitHub, a vendor, port 8317 or 8787, or the Mac's own key files."""
import base64
import contextlib
import http.server
import io
import json
import os
import socket
import sys
import tempfile
import threading
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "harness"))
import discover as D  # noqa: E402

FIX = os.path.join(HERE, "fixtures", "discovery")
ANSWER = os.path.join(FIX, "provimux-model-lists-live.json")
YESTERDAY = os.path.join(FIX, "listed-yesterday.json")
FAKE_GH = os.path.join(FIX, "fake_gh.py")
TODAY = "2026-11-24"


def load(path):
    with open(path) as f:
        return json.load(f)


def read(path):
    with open(path) as f:
        return f.read()


def dump(doc, path):
    with open(path, "w") as f:
        json.dump(doc, f)


def row(provider, entries, label=None, email=None, name=None, held=True, disabled=False, auth_index=None,
        listed=None):
    """A login row as Provimux 8.1.1-pmx.2 writes it with view=live."""
    return {"auth_index": auth_index, "provider": provider, "login": {"name": name, "email": email, "label": label},
            "disabled": disabled, "source": "live" if held else "built-in",
            "live": {"supported": True, "held": held, "expired": False,
                     "fetched_at": "2026-11-24T12:00:00Z" if held else None, "from_cache": False, "fetching": False,
                     "listed_models": (len(entries) if listed is None else listed) if held else None,
                     "last_failure": None},
            "registered_models": len(entries), "learned_models": 0, "models": None,
            "live_list": entries if held else None}


def answer_of(*rows):
    return {"options": {"live_lists": True}, "logins": list(rows)}


class Server:
    """A local HTTP server that answers every GET with `respond(handler)` and records the requests."""

    def __init__(self, respond):
        self.requests = []
        outer = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                outer.requests.append({"path": self.path, "auth": self.headers.get("Authorization")})
                status, headers, body = respond(self)
                self.send_response(status)
                for k, v in headers.items():
                    self.send_header(k, v)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


def provimux(answer, status=200):
    return Server(lambda h: (status, {"Content-Type": "application/json"}, json.dumps(answer).encode()))


class Connections:
    """Records every outgoing connection of this process; refuses any but the allowed loopback port."""

    def __init__(self, allowed_port=None):
        self.allowed, self.seen = allowed_port, []

    @contextlib.contextmanager
    def watching(self):
        real = socket.socket.connect

        def connect(sock, address):
            self.seen.append(address)
            if self.allowed is None or address[1] != self.allowed or address[0] not in ("127.0.0.1", "::1"):
                raise ConnectionRefusedError("the test allows no such connection")
            return real(sock, address)
        socket.socket.connect = connect
        try:
            yield self
        finally:
            socket.socket.connect = real


class Base(unittest.TestCase):
    def setUp(self):
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        for name in ("GROUNDTRUTH_CLIENT_HOME", "CPA_BASE_URL", "CPA_MGMT_KEY", "http_proxy", "HTTP_PROXY",
                     "https_proxy", "HTTPS_PROXY", "all_proxy", "ALL_PROXY", "no_proxy", "NO_PROXY", "GH_TOKEN",
                     "GITHUB_TOKEN"):
            os.environ.pop(name, None)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = self.tmp.name
        self.home = os.path.join(self.dir, "G")
        os.mkdir(self.home, 0o700)
        self.fake = os.path.join(self.dir, "github")
        os.mkdir(self.fake)
        bin_ = os.path.join(self.dir, "bin")
        os.mkdir(bin_)
        for name in ("gh", "osascript"):
            path = os.path.join(bin_, name)
            with open(path, "w") as f:
                f.write(f"#!/bin/sh\nFAKE_AS={name} exec '{sys.executable}' '{FAKE_GH}' \"$@\"\n")
            os.chmod(path, 0o755)
        os.makedirs(os.path.join(self.dir, "home"))
        none = os.path.join(self.dir, "none")
        os.environ.update(GROUNDTRUTH_CLIENT_HOME=self.home, FAKE_GH=self.fake, HOME=os.path.join(self.dir, "home"),
                          PATH=bin_ + os.pathsep + os.environ.get("PATH", ""), SCAN_CLIENT_KEYS=none,
                          SCAN_KEYS_FILE=none, SCAN_CONFIG=none, SCAN_LOGINS=os.path.join(none, "*.json"),
                          SCAN_FINGERPRINTS=none)
        self.log = os.path.join(self.home, "discovery.log")
        self.out = os.path.join(self.home, "listed.json")

    # -- the fake GitHub
    def github(self, doc):
        os.makedirs(os.path.join(self.fake, "main"), exist_ok=True)
        with open(os.path.join(self.fake, "main", "listed.json"), "w") as f:
            f.write(doc if isinstance(doc, str) else D.text_of(doc))

    def github_file(self):
        path = os.path.join(self.fake, "main", "listed.json")
        return load(path) if os.path.exists(path) else None

    def lines(self, name):
        path = os.path.join(self.fake, name)
        return [json.loads(x) for x in read(path).splitlines()] if os.path.exists(path) else []

    def calls(self):
        return self.lines("calls.jsonl")

    def commits(self):
        return self.lines("commits.jsonl")

    def puts(self):
        return [json.loads(c["stdin"]) for c in self.calls() if "PUT" in c["argv"]]

    def put_bytes(self):
        return [base64.b64decode(p["content"]) for p in self.puts()]

    def notifications(self):
        return self.lines("osascript.jsonl")

    # -- running
    def run_with(self, argv, **kw):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code, words = D.run(D.parser().parse_args(argv), **kw)
        self.err = err.getvalue()
        return code, words

    def from_answer(self, answer, *extra, date=TODAY, **kw):
        path = os.path.join(self.dir, "answer.json")
        if isinstance(answer, str):
            path = answer
        else:
            dump(answer, path)
        return self.run_with(["--answer", path, "--date", date, *extra], **kw)

    def written(self):
        return load(self.out)

    def logged(self):
        return read(self.log) if os.path.exists(self.log) else ""
