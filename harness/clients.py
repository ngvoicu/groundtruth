#!/usr/bin/env python3
"""The clients that harness/probe.py and harness/client_limits.py drive: one class per client, with the same parts,
so the loops know no client by name (docs/own-clients.md, sections 1 and 5).

    harness       the --harness value
    client_id     the client's id in observed.json
    cumulative    the client reports a session's running total, so a check is the difference to its priming
    environment() the allow-list and the state folder's variables: nothing else of the caller's shell
    version()     `<client> --version`
    command()     the argument list of one invocation (a new session, or one resumed)
    parse()       a pure function of what the client printed: a Usage, or Refused / ClientError

Usage: total (input tokens of the request, cached or not), cached (read from the cache), write (written to it, where
the client reports it), calls (model requests the turn made; a check counts only when it is 1), model, and
write_5m / write_1h where the client says which lifetime it wrote (Claude Code).

Nothing here sends a request by itself: Session runs a command, and only harness/probe.py and harness/client_limits.py
make Sessions.
"""
import glob
import json
import os
import re
import subprocess
import uuid
from dataclasses import dataclass

# What a client's process gets of the caller's environment; everything else (API keys, base URLs, proxy settings,
# cache switches) never reaches it. A client adds the variables of its state folder and what the run sets.
ALLOW = ("PATH", "HOME", "USER", "LANG", "TERM", "TMPDIR")

OK_PROMPT = "Reply with OK only. Do not use any tools."


@dataclass
class Usage:
    total: int
    cached: int
    write: int | None = 0
    calls: int | None = None
    model: str | None = None
    write_5m: int | None = None
    write_1h: int | None = None
    handle: str | None = None  # the session id the client reported (Codex thread, Devin session); not logged here

    def record(self):
        """The dict harness/probe.py logs (None fields left out, the handle logged apart)."""
        return {k: v for k, v in self.__dict__.items() if v is not None and k != "handle"}


class Refused(Exception):
    """A refusal: kind `quota` (a plan's or a rate limit), `input` (the input is too long, from the provider), or
    `client-cap` (the client refused before sending anything: Codex's message size)."""

    def __init__(self, kind, text):
        super().__init__(f"{kind}: {text}")
        self.kind, self.text = kind, text


class ClientError(Exception):
    """Anything else: no reading, a crash, an output this module does not know."""


# The wording of a refusal, as far as the documentation and the source show it; the smoke runs correct this.
INPUT_TOO_LONG = re.compile(r"prompt is too long|input is too long|too many (?:input )?tokens|context[ _]?(?:length|window)"
                            r"(?:[ _]exceeded| is exceeded)?|maximum context|contextoverflow|context overflow"
                            r"|exceeds? (?:the )?(?:model'?s? )?(?:maximum|context|limit)", re.I)
QUOTA = re.compile(r"usage limit|rate[ _]limit|quota|too many requests|\b429\b|out of (?:credits|usage)|limit reached"
                   r"|hit your|insufficient[ _](?:credits|balance|quota)", re.I)


def classify(text):
    """The exception for a client's failure text: an input refusal, a quota refusal, or another error."""
    text = (text or "").strip()
    if INPUT_TOO_LONG.search(text):
        return Refused("input", text[-2000:])
    if QUOTA.search(text):
        return Refused("quota", text[-2000:])
    return ClientError(text[-600:] or "no output")


def json_lines(text):
    for line in (text or "").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            yield json.loads(line)
        except ValueError:
            continue


class Client:
    harness = client_id = binary = None
    own = True                # a client its route's vendor ships (driven apart from everyday use)
    isolated = True           # driven with a state folder of its own and the short environment
    cumulative = False
    prompt_mode = "file"      # stdin: the prompt file on stdin; file: its path on the command line; arg: its text
    settable = ()             # variables a run may set for the client (recorded in the run's start event)
    passthrough = ()          # variables passed from the caller's environment as they are (a key, never logged)
    defaults = ()             # the client's everyday folders under the home folder: never a state folder
    retries_note = None       # what is known of the client's own retries (recorded in the run's start event)

    def __init__(self, model, effort="low", settings=None):
        self.model, self.effort = model, effort
        self.settings = dict(settings or {})
        bad = sorted(set(self.settings) - set(self.settable))
        if bad:
            raise SystemExit(f"{self.client_id}: a run may not set {', '.join(bad)} (allowed: {', '.join(self.settable) or 'none'})")

    def effective_effort(self):
        """The reasoning level the client is actually asked for (recorded in the run's start event)."""
        return self.effort

    def run_info(self):
        """What the run records about how the client was driven, beyond its settings (None: nothing)."""
        return None

    # --- the state folder and the environment -------------------------------------------------------------------
    def home_vars(self, home):
        return {}

    def run_vars(self):
        return {}

    def environment(self, home, base=None):
        base = os.environ if base is None else base
        env = {k: base[k] for k in ALLOW if k in base}
        env.update(self.home_vars(home))
        env.update(self.run_vars())
        env.update(self.settings)
        for k in self.passthrough:
            if base.get(k):
                env[k] = base[k]
        return env

    def login_command(self):
        """A command that exits 0 when the state folder is logged in (None: checked otherwise)."""
        return None

    def version_command(self):
        return [self.binary, "--version"]

    def version(self, env, run=None):
        run = run or _run
        code, out, err = run(self.version_command(), env=env, cwd=None, stdin=None, timeout=60)
        line = (out or err).strip().splitlines()
        if code or not line:
            raise ClientError(f"{self.binary} --version failed: {(err or out)[-300:]}")
        return line[-1].strip()

    # --- one invocation -----------------------------------------------------------------------------------------
    def new_session(self):
        """The session id a new session is given on its command line, or None where the client names it."""
        return None

    def files(self, io, tag, session):
        """Files the invocation writes that parse() reads: name -> (path or glob, keep afterwards)."""
        return {}

    def command(self, prompt_file, resume=None, session=None, files=None):
        raise NotImplementedError

    def parse(self, stdout, stderr, code, files, expect=None):
        """`expect`: {"prompt": the text sent, "session": the session resumed or None}, where the output can be tied
        to them."""
        raise NotImplementedError

    def shown(self, argv, prompt_file, files=None):
        """The command as recorded in a run's start event: the prompt, the files and the session ids by name."""
        names = {prompt_file: "<prompt>"}
        for name, (path, _) in (files or {}).items():
            names[path] = f"<{name}>"
        return [names.get(a, a) for a in argv]


class Claude(Client):
    """Claude Code, on a Claude login (claude-subscription)."""
    harness, client_id, binary = "claude", "claude-code", "claude"
    prompt_mode = "stdin"
    settable = ("CLAUDE_CODE_PROMPT_CACHE_TTL",)
    defaults = ("~/.claude", "~/.claude.json")

    def home_vars(self, home):
        return {"CLAUDE_CONFIG_DIR": home}

    def run_vars(self):
        # Claude Code retries a failed request up to ten times by itself (design, 1.1), unseen by the harness: a check
        # could then be a re-send. CLAUDE_CODE_MAX_RETRIES=0 switches that off (the variable is in the 2.1.330 binary;
        # whether it is honoured is shown only by a failure, so every run records it and the retries note).
        return {"DISABLE_AUTOUPDATER": "1", "CLAUDE_CODE_MAX_RETRIES": "0"}

    retries_note = ("internal retries switched off with CLAUDE_CODE_MAX_RETRIES=0 (found in the client's binary, not "
                    "verified by a failure): a check may hide a retry if the client does not honour it")

    def login_command(self):
        return ["claude", "auth", "status", "--json"]

    def new_session(self):
        return str(uuid.uuid4())

    def command(self, prompt_file, resume=None, session=None, files=None):
        # Never --bare (it reads no login), never --no-session-persistence (the session could not be resumed). No MCP
        # server at all (--strict-mcp-config without --mcp-config); nobody answers a permission prompt.
        return ["claude", "-p", "--output-format", "json", "--model", self.model, "--effort", self.effort,
                *(["--resume", resume] if resume else ["--session-id", session]),
                "--strict-mcp-config", "--disable-slash-commands", "--permission-prompts", "none"]

    def parse(self, stdout, stderr, code, files, expect=None):
        result = None
        for d in json_lines(stdout):
            if d.get("type") == "result" or "usage" in d:
                result = d
        if result is None:
            try:
                result = json.loads(stdout)
            except ValueError:
                raise classify((stdout or "") + "\n" + (stderr or ""))
        if result.get("is_error") or code:
            raise classify(f"{result.get('subtype') or ''}: {result.get('result') or ''}\n{stderr or ''}")
        u = result.get("usage") or {}
        if not u:
            raise ClientError("no usage in the result")
        read, created = u.get("cache_read_input_tokens") or 0, u.get("cache_creation_input_tokens") or 0
        made = u.get("cache_creation") or {}
        models = list((result.get("modelUsage") or {}).keys())
        turns = result.get("num_turns")
        calls = 1 if turns == 1 and len(models) == 1 else max(turns or 0, len(models), 2)
        return Usage(total=(u.get("input_tokens") or 0) + read + created, cached=read, write=created, calls=calls,
                     model=models[0] if len(models) == 1 else None,
                     write_5m=made.get("ephemeral_5m_input_tokens"), write_1h=made.get("ephemeral_1h_input_tokens"),
                     handle=result.get("session_id"))


# The item types of a Codex turn that are not a tool call: a turn with any other item made more than one request.
CODEX_TEXT_ITEMS = {"agent_message", "reasoning"}
# Codex refuses a message above MAX_USER_INPUT_TEXT_CHARS (1,048,576 characters) before it sends anything.
CODEX_CAP = re.compile(r"1,?048,?576|(?:maximum|max) (?:input |message )?(?:length|size).{0,40}characters", re.I)


class Codex(Client):
    """OpenAI's Codex CLI, on a ChatGPT plan (codex-subscription)."""
    harness, client_id, binary = "codex", "codex-cli", "codex"
    cumulative = True  # `codex exec resume --json` reports the thread's running total, not the last turn
    prompt_mode = "stdin"
    defaults = ("~/.codex",)

    def home_vars(self, home):
        return {"CODEX_HOME": home}

    def _config(self):
        # The login is a file in the state folder; never the Keychain, where the everyday login may be.
        return ["-c", 'cli_auth_credentials_store="file"', "-c", f'model_reasoning_effort="{self.effort}"']

    def login_command(self):
        return ["codex", "login", "status", "-c", 'cli_auth_credentials_store="file"']

    def command(self, prompt_file, resume=None, session=None, files=None):
        base = ["--json", "--skip-git-repo-check", "-m", self.model, *self._config()]
        if resume:
            return ["codex", "exec", "resume", resume, *base, "-"]
        return ["codex", "exec", *base, "-s", "read-only", "-"]

    def parse(self, stdout, stderr, code, files, expect=None):
        tid, usage, tools, failure, turns = None, None, set(), None, 0
        for d in json_lines(stdout):
            t = d.get("type")
            if t == "thread.started":
                tid = d.get("thread_id")
            elif t == "turn.completed":
                usage = d.get("usage")
                turns += 1
            elif t in ("error", "turn.failed"):
                e = d.get("error")
                failure = (failure or "") + " " + str((e or {}).get("message") if isinstance(e, dict) else d.get("message") or e)
            elif t and t.startswith("item.") and isinstance(d.get("item"), dict):
                item = d["item"]
                if item.get("type") not in CODEX_TEXT_ITEMS:
                    tools.add(item.get("id") or len(tools))
        text = (failure or "") + "\n" + (stderr or "")
        # A failure is a failure, whatever usage came with it: a non-zero exit, an error or a failed turn.
        if usage is None or code or failure:
            if CODEX_CAP.search(text):
                raise Refused("client-cap", text.strip()[-2000:])
            raise classify(text if text.strip() else (stdout or f"exit {code}"))
        if expect and expect.get("session") and tid and tid != expect["session"]:
            raise ClientError(f"the output is of thread {tid}, not of the resumed one")
        # One model request: one completed turn and no tool item in it.
        return Usage(total=usage.get("input_tokens", 0), cached=usage.get("cached_input_tokens", 0),
                     write=usage.get("cache_write_input_tokens", 0), calls=turns + len(tools), handle=tid)


class Devin(Client):
    """The Devin CLI, on a Devin subscription (devin). The export (ATIF) is the record: -p has no JSON output."""
    harness, client_id, binary = "devin", "devin-cli", "devin"
    LEVELS = ("none", "minimal", "low", "medium", "high", "xhigh", "max")

    def effective_effort(self):
        # The model id carries the level (nemotron-3-5-super-none, swe-2-medium); --effort is not passed to Devin.
        tail = self.model.rsplit("-", 1)[-1]
        return tail if tail in self.LEVELS else None
    defaults = ("~/.devin", "~/.config", "~/.local/share", "~/.local/state", "~/.cache")

    # M-2 of the parity design: in-process (no shared daemon) and the client's cache keepalive off; the run records
    # both. `daemon=True` (pair DV-5 only) leaves both as the client has them, and says so.
    daemon = False

    def home_vars(self, home):
        return {"XDG_CONFIG_HOME": os.path.join(home, "config"), "XDG_DATA_HOME": os.path.join(home, "data"),
                "XDG_STATE_HOME": os.path.join(home, "state"), "XDG_CACHE_HOME": os.path.join(home, "cache"),
                "DEVIN_SESSIONS_DIR": os.path.join(home, "sessions")}

    def run_vars(self):
        return {} if self.daemon else {"DEVIN_CACHE_KEEPALIVE_MAX_PINGS": "0"}

    def run_info(self):
        return {"process_model": "client default (daemon)" if self.daemon else "in-process",
                "keepalive_max_pings": "client default" if self.daemon else 0}

    def _process(self):
        return [] if self.daemon else ["--process-model", "in-process"]

    def login_command(self):
        return ["devin", "auth", "--process-model", "in-process", "status"]

    def files(self, io, tag, session):
        return {"export": (os.path.join(io, f"export-{tag}.json"), False)}

    def command(self, prompt_file, resume=None, session=None, files=None):
        # in-process: a sample is a process that ends, never a shared background daemon that could touch its cache.
        # The model id carries the reasoning level (claude-opus-5-5-low); a resumed session keeps its model.
        return ["devin", *self._process(), *(["-r", resume] if resume else ["--model", self.model]),
                "--prompt-file", prompt_file, "-p", "--respect-workspace-trust", "false",
                "--export", (files or {})["export"][0]]

    def parse(self, stdout, stderr, code, files, expect=None):
        raw = files.get("export")
        if code or not raw:
            # A failed invocation is a failure even when an export is there: it may be the priming's, unchanged.
            raise classify(f"exit {code}{'' if raw else ', no export'}: {stderr or ''}\n{stdout or ''}")
        d = json.loads(raw)
        steps = d.get("steps") or []
        last_user = max((i for i, s in enumerate(steps) if s.get("source") == "user"), default=-1)
        if expect:
            # The turn must be this invocation's: the session resumed, and the last user step the prompt just sent.
            if expect.get("session") and d.get("session_id") != expect["session"]:
                raise ClientError(f"the export is of session {d.get('session_id')}, not of the resumed one")
            said = steps[last_user].get("message") if last_user >= 0 else None
            said = said if isinstance(said, str) else json.dumps(said)
            if (expect.get("prompt") or "").strip()[:200] not in (said or ""):
                raise ClientError("the export's last user step is not the prompt just sent: no new turn")
        turn = [s for s in steps[last_user + 1:] if s.get("metrics")]
        if not turn:
            raise classify(f"no step with metrics in the export (exit {code}): {stderr or ''}\n{stdout or ''}")
        m = turn[-1]["metrics"]
        return Usage(total=m.get("prompt_tokens", 0), cached=m.get("cached_tokens", 0),
                     write=(m.get("extra") or {}).get("cache_creation_input_tokens", 0), calls=len(turn),
                     model=turn[-1].get("model_name"), handle=d.get("session_id"))


class Muse(Client):
    """Meta's Muse Code, on the Muse Code subscription key (meta-subscription). The key comes in META_API_KEY."""
    harness, client_id, binary = "muse", "muse-code", "muse"
    passthrough = ("META_API_KEY",)
    defaults = ("~/.muse", "~/.config", "~/.local/share", "~/.local/state", "~/.cache")

    def home_vars(self, home):
        return {"XDG_CONFIG_HOME": os.path.join(home, "config"), "XDG_DATA_HOME": os.path.join(home, "data"),
                "XDG_STATE_HOME": os.path.join(home, "state"), "XDG_CACHE_HOME": os.path.join(home, "cache")}

    def run_vars(self):
        return {"MUSE_NO_AUTO_UPDATE": "1"}

    def new_session(self):
        return str(uuid.uuid4())

    def command(self, prompt_file, resume=None, session=None, files=None):
        # A session id that exists is continued: the check names its priming's id.
        return ["muse", "exec", "--json", "--model", self.model, "--reasoning-effort", self.effort,
                "--session-id", resume or session, "--prompt-file", prompt_file]

    def parse(self, stdout, stderr, code, files, expect=None):
        u, failure, other = None, [], []
        for d in json_lines(stdout):
            kind = str(d.get("payload_type") or d.get("type") or "")
            if kind == "run.usage":
                u = d.get("payload") or {}
            elif "error" in kind or "fail" in kind:
                failure.append(json.dumps(d.get("payload") or d))
            elif "usage" in kind:
                other.append(json.dumps(d)[:400])
        if failure or code:
            # A failure is a failure, whatever usage came with it.
            raise classify("\n".join(failure) + "\n" + (stderr or "") + (f"\nexit {code}" if code else ""))
        if u is None:
            # No run.usage line is no reading, never zero (Muse leaves it out when it cannot count a run). An event
            # that looks like usage is kept (redacted by the Session) so that the fixture can be corrected.
            raise ClientError("no run.usage line" + (f"; usage-like events: {' | '.join(other[:2])}" if other else ""))
        ms = u.get("models") or []
        return Usage(total=sum(m.get("input_tokens", 0) for m in ms), cached=sum(m.get("cached_tokens", 0) for m in ms),
                     write=None, calls=u.get("calls"), model=ms[0].get("model") if len(ms) == 1 else None)


PI_THINKING = {"none": "off", "minimal": "minimal", "low": "low", "medium": "medium", "high": "high", "xhigh": "xhigh"}


class Pi(Client):
    """pi through Provimux (a proxy client, client pi+cliproxyapi): the pi side of a parity pair (Provimux's design
    client-parity.md, section 6). pi runs from a state folder of its own (PI_CODING_AGENT_DIR = <client-home>/pi-provimux,
    set up once by the owner with pi-provimux and the proxy's key), never ~/.pi. The model is given as Provimux names
    it, a Devin id with its effort suffix as given (M-1). Each run records what pi and Provimux were (M-4)."""
    harness, client_id, binary = "pi", "pi+cliproxyapi", "pi"
    own = False
    state_name = "pi-provimux"
    prompt_mode = "arg"
    defaults = ("~/.pi",)
    provider = "cliproxyapi"  # the pi provider pi-provimux registers for the proxy

    def home_vars(self, home):
        return {"PI_CODING_AGENT_DIR": home}

    def run_vars(self):
        return {"PI_SKIP_VERSION_CHECK": "1"}

    def thinking(self):
        # A Devin id names its level; pi is asked the same one, so that both sides ask one variant (M-1).
        tail = self.model.rsplit("-", 1)[-1]
        return PI_THINKING.get(tail, self.effort) if self.model.startswith("devin/") else self.effort

    def effective_effort(self):
        return self.thinking()

    def new_session(self):
        return "hp-" + uuid.uuid4().hex[:12]

    def files(self, io, tag, session):
        return {"session": (os.path.join(io, "pi-sessions", f"*_{session}.jsonl"), True)}

    def command(self, prompt_file, resume=None, session=None, files=None):
        sd = os.path.dirname((files or {})["session"][0])
        return ["pi", "-p", "--session-dir", sd, "--session-id", resume or session,
                "--model", f"{self.provider}/{self.model}", "--thinking", self.thinking(), prompt_file]

    def parse(self, stdout, stderr, code, files, expect=None):
        raw = files.get("session")
        if code or not raw:
            raise classify(f"exit {code}{'' if raw else ', no session'}: {stderr or stdout}")
        msgs = [(json.loads(x).get("message") or {}) for x in raw.splitlines() if x.strip()]
        last_user = max((i for i, m in enumerate(msgs) if m.get("role") == "user"), default=-1)
        turn = [m for m in msgs[last_user + 1:] if m.get("role") == "assistant"]
        if not turn or turn[-1].get("stopReason") == "error":
            raise classify("pi error: " + str((turn[-1] if turn else {}).get("errorMessage")))
        u = turn[-1].get("usage") or {}
        return Usage(total=u.get("input", 0) + u.get("cacheRead", 0) + u.get("cacheWrite", 0), cached=u.get("cacheRead", 0),
                     write=u.get("cacheWrite", 0), calls=len(turn), model=turn[-1].get("model"))

    def describe(self, home, env, run=None):
        """M-4: the Provimux build, pi's version, pi-provimux's commit, the transport and the payload rules. Read from
        `provimux --version` (the installed binary), `pi --version`, the checkout named by PI_PROVIMUX_DIR, pi's
        settings in the state folder, and payload-rules.json in it (the rules of the owner's Provimux configuration
        that touch this login's requests, written there by the owner; the configuration itself is never read)."""
        run = run or _run
        info = {}

        def first(argv):
            code, out, err = run(argv, env=env, cwd=None, stdin=None, timeout=60)
            lines = (out or err or "").strip().splitlines()
            if code or not lines:
                raise SystemExit(f"pi run: {' '.join(argv)} failed: it is needed for the run's record (M-4)")
            return lines[-1].strip()
        info["provimux_build"] = first([os.environ.get("GROUNDTRUTH_PROVIMUX_BIN", "provimux"), "--version"])
        info["pi_version"] = first(["pi", "--version"])
        checkout = os.environ.get("PI_PROVIMUX_DIR")
        if not checkout:
            raise SystemExit("pi run: PI_PROVIMUX_DIR (the pi-provimux checkout pi loads) is not set (M-4)")
        info["pi_provimux_commit"] = first(["git", "-C", checkout, "rev-parse", "--short=12", "HEAD"])
        settings = {}
        try:
            with open(os.path.join(home, "settings.json")) as f:
                settings = json.load(f)
        except (OSError, ValueError):
            pass
        info["transport"] = {"requested": settings.get("transport") or "auto (pi-provimux: WebSocket first, SSE fallback)",
                             "used": "not recorded by pi"}
        try:
            with open(os.path.join(home, "payload-rules.json")) as f:
                info["payload_rules"] = json.load(f)
        except (OSError, ValueError):
            raise SystemExit("pi run: <client-home>/pi-provimux/payload-rules.json is missing or not JSON: the owner "
                             "writes there the payload rules of Provimux's configuration in force ([] for none) (M-4)")
        return info


CLIENTS = {c.harness: c for c in (Claude, Codex, Devin, Muse, Pi)}


# Every client's everyday folders, and pi's: no state folder lies in any of them, whichever client it is for.
EVERYDAY = ("~/.claude", "~/.claude.json", "~/.codex", "~/.devin", "~/.muse", "~/.pi", "~/.config", "~/.local/share",
            "~/.local/state", "~/.cache", "~/Library/Application Support", "~/Library/Keychains")


def inside(path, folder):
    return path == folder or path.startswith(folder.rstrip(os.sep) + os.sep)


def in_git_checkout(path):
    """The work tree that holds `path` (a folder with .git above it), or None."""
    p = os.path.realpath(path)
    while True:
        if os.path.exists(os.path.join(p, ".git")):
            return p
        parent = os.path.dirname(p)
        if parent == p:
            return None
        p = parent


def links_out(folder):
    """Symbolic links under `folder`, at any depth, whose target leaves it (or does not resolve)."""
    real, out = os.path.realpath(folder), []
    for d, dirs, files in os.walk(folder, followlinks=False):
        for name in dirs + files:
            p = os.path.join(d, name)
            if os.path.islink(p) and not inside(os.path.realpath(p), real):
                out.append(os.path.relpath(p, folder))
    return sorted(out)


def check_folder(what, path, root, user_home):
    """A folder the run writes to: outside the repository, any Git checkout and every everyday folder."""
    real = os.path.realpath(path)
    if real == user_home or any(inside(real, os.path.realpath(user_home + d[1:])) for d in EVERYDAY):
        raise SystemExit(f"{what} is an everyday folder of a client or of pi (or inside one)")
    if inside(real, os.path.realpath(root)):
        raise SystemExit(f"{what} is inside the repository")
    checkout = in_git_checkout(real)
    if checkout:
        raise SystemExit(f"{what} is inside a Git checkout")


def login_ok(client, code, out, err):
    """None when the status output shows the login the route needs (a subscription, never an API key), else why not."""
    text = f"{out or ''}\n{err or ''}"
    if code:
        return f"the status command exited {code}"
    if client.harness == "claude":
        try:
            st = json.loads(out)
        except ValueError:
            return "the status output is not JSON"
        method = str(st.get("authMethod") or "")
        if not st.get("loggedIn"):
            return "not logged in"
        if method not in ("claude.ai", "claudeai", "claude_ai", "oauth"):
            return f"logged in with {method or 'an unknown method'}, not a Claude subscription"
        if st.get("apiProvider") not in (None, "firstParty", "anthropic"):
            return f"routed through {st.get('apiProvider')}, not Anthropic"
        return None
    if client.harness == "codex":
        if re.search(r"api[ _-]?key", text, re.I):
            return "logged in with an API key, not a ChatGPT plan"
        if not re.search(r"logged in using chatgpt", text, re.I):
            return "the status does not say 'Logged in using ChatGPT'"
        return None
    if re.search(r"api[ _-]?key", text, re.I):
        return "the status names an API key"
    return None


def state_folder(client, base, root, user_home=None, env=None, run=None, check_login=True):
    """The client's state folder, `<base>/<client id>` made absolute, or SystemExit. It must exist, lie outside the
    repository, every Git checkout and every everyday folder (any client's, and pi's), hold no symbolic link that
    leaves it, and be logged in with the login the route needs (its status output read, not only its exit code)."""
    if not base:
        raise SystemExit(f"{client.client_id}: --client-home (or GROUNDTRUTH_CLIENT_HOME) is required for an own client")
    user_home = os.path.realpath(user_home or os.path.expanduser("~"))
    name = getattr(client, "state_name", None) or client.client_id
    home = os.path.realpath(os.path.abspath(os.path.join(base, name)))
    if not os.path.isdir(home):
        raise SystemExit(f"{client.client_id}: its state folder <client-home>/{name} does not exist: "
                         "create it and log the client in there first (docs/own-clients-RUN.md)")
    check_folder(f"{client.client_id}: the state folder", home, root, user_home)
    out = links_out(home)
    if out:
        raise SystemExit(f"{client.client_id}: the state folder holds links that leave it: {', '.join(out[:5])}")
    if check_login:
        cmd = client.login_command()
        e = env if env is not None else client.environment(home)
        if cmd:
            code, o, er = (run or _run)(cmd, env=e, cwd=None, stdin=None, timeout=120)
            why = login_ok(client, code, o, er)
            if why:
                raise SystemExit(f"{client.client_id}: refused: {why} ({' '.join(cmd[:4])})")
        for k in client.passthrough:
            if not (env if env is not None else os.environ).get(k):
                raise SystemExit(f"{client.client_id}: {k} is not set (read it from the Keychain into the environment)")
    return home


# What never reaches a public file from a client's output: a value of a secret variable of the client's environment,
# a folder of the run (home, state folder, temporary folders), a token shape, an e-mail address.
SECRET_NAME = re.compile(r"KEY|TOKEN|SECRET|PASSWORD|AUTH|COOKIE|CREDENTIAL", re.I)
TOKEN_SHAPE = re.compile(r"(?<![A-Za-z0-9_+/=-])(sk-[A-Za-z0-9_-]{16,}|Bearer [A-Za-z0-9._-]{16,}|eyJ[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_.-]{16,})")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
HOME_PATH = re.compile(r"/(?:Users|home)/[^/\s\"']+")
OPAQUE = re.compile(r"(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{32,}(?![A-Za-z0-9_-])")


class Redactor:
    def __init__(self, env=None, paths=()):
        env = env or {}
        self.secrets = sorted({v for k, v in env.items() if SECRET_NAME.search(k) and v and len(v) >= 8}, key=len, reverse=True)
        self.paths = sorted({os.path.realpath(p) for p in paths if p} | {p for p in paths if p}, key=len, reverse=True)

    def __call__(self, text):
        text = text or ""
        for v in self.secrets:
            text = text.replace(v, "<secret>")
        for i, p in enumerate(self.paths):
            text = text.replace(p, "<folder>")
        text = TOKEN_SHAPE.sub("<token>", text)
        text = EMAIL.sub("<e-mail>", text)
        text = HOME_PATH.sub("<home>", text)
        return OPAQUE.sub("<opaque>", text)


def _run(argv, env, cwd, stdin, timeout):
    p = subprocess.run(argv, cwd=cwd, env=env, stdin=stdin if stdin is not None else subprocess.DEVNULL,
                       capture_output=True, text=True, timeout=timeout)
    return p.returncode, p.stdout, p.stderr


class Session:
    """start() and resume() for the loops, from a client's command() and parse(). `io` holds the prompt and export
    files (deleted after each invocation); `work` is the client's working folder and stays empty."""

    def __init__(self, client, env, io, work, run=None, timeout=900, create=True, home=None, keep=None):
        self.client, self.env, self.io, self.work = client, env, io, work
        self.run, self.timeout = run or _run, timeout
        # Every text of the client's that leaves this object (an error, a refusal, a kept output) is redacted.
        self.redact = Redactor(env, [home, io, work, os.path.dirname(io), (env or {}).get("HOME"),
                                     os.path.expanduser("~")])
        self.keep, self.count = keep, 0  # a private folder for the redacted raw output (smoke runs), or None
        if keep:
            os.makedirs(keep, exist_ok=True)
        if create:
            os.makedirs(io, exist_ok=True)
            os.makedirs(work, exist_ok=True)

    def plan(self, resume=None):
        """The command of one invocation as a start event records it (nothing is run)."""
        tag, session = "x", (None if resume else self.client.new_session())
        files = self.client.files(self.io, tag, session or resume)
        pf = os.path.join(self.io, f"prompt-{tag}.txt")
        argv = self.client.command(pf, resume=resume and "<session>", session=session and "<session>", files=files)
        shown = self.client.shown(argv, pf, files)
        return shown + (["<", "<prompt>"] if self.client.prompt_mode == "stdin" else [])

    def _go(self, prompt, resume=None):
        tag = uuid.uuid4().hex[:10]
        session = None if resume else self.client.new_session()
        files = self.client.files(self.io, tag, session or resume)
        for path, keep in files.values():
            os.makedirs(os.path.dirname(path), exist_ok=True)
        pf = os.path.join(self.io, f"prompt-{tag}.txt")
        with open(pf, "w") as f:
            f.write(prompt)
        argv = self.client.command(pf, resume=resume, session=session, files=files)
        if self.client.prompt_mode == "arg":
            argv = [prompt if a == pf else a for a in argv]
        try:
            with open(pf) as stdin:
                code, out, err = self.run(argv, env=self.env, cwd=self.work,
                                          stdin=stdin if self.client.prompt_mode == "stdin" else None, timeout=self.timeout)
            contents = {}
            for name, (path, keep) in files.items():
                found = sorted(glob.glob(path)) if any(c in path for c in "*?[") else [path]
                for p in found:
                    if os.path.exists(p):
                        with open(p) as f:
                            contents[name] = f.read()
                        if not keep:
                            os.remove(p)
        finally:
            if os.path.exists(pf):
                os.remove(pf)
        self.count += 1
        if self.keep:
            # The minimum to correct a fixture from: what the client printed and wrote, redacted, kept privately.
            for name, text in (("stdout", out), ("stderr", err), *contents.items()):
                with open(os.path.join(self.keep, f"{self.count:03d}-{'check' if resume else 'start'}-{name}.txt"), "w") as f:
                    f.write(self.redact(text))
        expect = {"prompt": prompt, "session": resume}
        try:
            u = self.client.parse(out, err, code, contents, expect=expect)
        except Refused as e:
            r = Refused(e.kind, self.redact(e.text))
            r.code = code  # the client's exit code, kept with a refusal row
            raise r from None
        except ClientError as e:
            r = ClientError(self.redact(str(e)))
            r.code = code
            raise r from None
        except (ValueError, KeyError, TypeError) as e:
            r = ClientError(self.redact(f"unreadable output ({type(e).__name__}): {e}"))
            r.code = code
            raise r from None
        if u.handle is None:
            u.handle = resume or session
        return u

    def start(self, prompt):
        u = self._go(prompt)
        return u.handle, u

    def resume(self, handle, prompt):
        return self._go(prompt, resume=handle)
