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
    preflight()   the state folder's own settings checked against the route (Codex: the provider its config selects)
    allowed_link() the links a client itself makes in its state folder that may leave it (Codex's two helpers)
    answered_model() the model that answered, where the output leaves it out (Codex: its session file, bound to the
                  invocation's one new turn by its id, and only when it is the requested model)

Every client process runs under sandbox-exec on macOS (confine): no file write under the owner's home folder except
in its state folder, its throwaway HOME and its temporary folder.

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
import sys
import uuid
from dataclasses import dataclass

# What a client's process gets of the caller's environment; everything else (API keys, base URLs, proxy settings,
# cache switches) never reaches it. A client adds the variables of its state folder and what the run sets. HOME is
# never the caller's: every client process gets a throwaway one (throwaway_home), so a client that ignores its state
# folder's variable writes under it, never under the owner's home folder. TMPDIR is never the caller's either: every
# client gets its own under <client-home> (throwaway_tmp), so no setting of the shell widens what it may write.
ALLOW = ("PATH", "USER", "LANG", "TERM")


def throwaway_home(state):
    """The HOME of every process of a client: <client-home>/home/<the state folder's name>, beside the state folder,
    the same for the owner's login and for every run of the night. On macOS the Keychain is found through HOME too
    (`security list-keychains` is empty under it): a client cannot reach the owner's Keychain from there, and Claude
    Code keeps its login in <state folder>/.credentials.json instead."""
    return os.path.join(os.path.dirname(state.rstrip(os.sep)), "home", os.path.basename(state.rstrip(os.sep)))


def throwaway_tmp(state):
    """The TMPDIR of every process of a client: <client-home>/tmp/<the state folder's name> (mode 700)."""
    return os.path.join(os.path.dirname(state.rstrip(os.sep)), "tmp", os.path.basename(state.rstrip(os.sep)))

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
    # Codex: why the answering model is not known for certain (`no-model`, `ambiguous-model`, `other-model`), or None;
    # and, when it is, `own-turn` (bound to this invocation's one new turn, and the requested model).
    model_issue: str | None = None
    model_evidence: str | None = None
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
    """Anything else: no reading, a crash, an output this module does not know. `kind` is one of ERROR_KINDS (None:
    decided by the Session from the exit code)."""

    def __init__(self, text="", kind=None):
        super().__init__(text)
        self.kind = kind


# The only error text a public result carries: one of these kinds. The client's own words (which can hold a key, a
# path, anything) go only to the run's console log, redacted, never into a public file.
ERROR_KINDS = ("timeout", "spawn", "exit-nonzero", "quota", "input", "client-cap", "parse", "no-usage", "wrong-turn",
               "not-one-call", "no-model", "login", "other")
# Why a check's answering model is not taken (harness/probe.py logs the check `check-invalid` with this reason).
MODEL_ISSUES = ("no-model", "ambiguous-model", "other-model")


def error_kind(e):
    """The public kind of a client failure: always one of ERROR_KINDS."""
    kind = getattr(e, "kind", None) if isinstance(e, (Refused, ClientError)) else None
    return kind if kind in ERROR_KINDS else "other"


HANDLE_TEXT = re.compile(r"[A-Za-z0-9._:-]{1,100}")


def handle_text(handle):
    """A session id as a public record may hold it."""
    return handle if isinstance(handle, str) and HANDLE_TEXT.fullmatch(handle) else "<unrecognised>"


# The wording of a refusal, as far as the documentation and the source show it; the smoke runs correct this.
INPUT_TOO_LONG = re.compile(r"prompt is too long|input is too long|too many (?:input )?tokens|context[ _]?(?:length|window)"
                            r"(?:[ _]exceeded| is exceeded)?|maximum context|contextoverflow|context overflow"
                            r"|exceeds? (?:the )?(?:model'?s? )?(?:maximum|context|limit)", re.I)
QUOTA = re.compile(r"usage limit|rate[ _]limit|quota|too many requests|\b429\b|out of (?:credits|usage)|limit reached"
                   r"|hit your|insufficient[ _](?:credits|balance|quota)", re.I)


def classify(text):
    """The exception for a client's failure text: an input refusal, a quota refusal, or another error."""
    text = (text or "").strip()  # never clipped here: redaction comes first, then any clipping (Session)
    if INPUT_TOO_LONG.search(text):
        return Refused("input", text)
    if QUOTA.search(text):
        return Refused("quota", text)
    return ClientError(text or "no output")


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
        env["HOME"] = throwaway_home(home)
        env["TMPDIR"] = throwaway_tmp(home)
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

    def preflight(self, state):
        """Raise SystemExit when the state folder would send the runs elsewhere than the route (Codex's config)."""

    # The login file the client's own login writes in its state folder (relative), or None. `login_evidence` finds it.
    login_file = None

    def login_evidence(self, state):
        """The client's login file in its state folder, a regular non-empty file not a link; None when there is none.
        (Devin: any credentials.toml or auth.json under the folder; the others: their one file.)"""
        found = [os.path.join(state, self.login_file)] if self.login_file else \
            [f for f in login_files(state) if os.path.basename(f) in ("credentials.toml", "auth.json")]
        for f in found:
            if os.path.isfile(f) and not os.path.islink(f) and os.path.getsize(f) > 0:
                return f
        return None

    # The login is checked by its file too before every run (Claude: its status alone can be answered by a login
    # kept elsewhere, the everyday one in the Keychain).
    needs_login_file = False

    def allowed_link(self, rel, target, env=None):
        """Whether a link the client itself makes in its state folder may leave it (none but Codex's helpers)."""
        return False

    def allowed_link_for(self, env=None):
        return lambda rel, target: self.allowed_link(rel, target, env)

    def answered_model(self, state, handle, after=None):
        """(model, issue, evidence): the model that answered, where the client's output leaves it out but its state
        folder has it (Codex), bound to this invocation (`after`: turn_mark before it). The others: nothing to add."""
        return None, None, None

    def turn_mark(self, state, handle):
        """What the session's record holds before an invocation (Codex: its file, size and turn ids), or None."""
        return None

    def other_models(self, state, handle):
        """The models other than the requested one that the session's whole record names (Codex), or None where the
        client keeps no such record (the run-level check does not apply)."""
        return None

    def version_command(self):
        return [self.binary, "--version"]

    def version(self, env, run=None, writable=None):
        run = run or _run
        argv = self.version_command() if writable is None else confine(self.version_command(), env, writable)
        redact = Redactor(env, [env.get("HOME"), env.get("TMPDIR"), *(writable or ()), os.path.expanduser("~")])
        try:
            code, out, err = run(argv, env=env, cwd=None, stdin=None, timeout=60)
        except subprocess.TimeoutExpired:
            raise ClientError(f"{self.binary} --version did not answer within 60 s", kind="timeout") from None
        except OSError as e:
            raise ClientError(f"{self.binary} --version could not be run ({type(e).__name__})", kind="spawn") from None
        line = (out or err).strip().splitlines()
        if code or not line:
            # What the client printed is redacted whole, then clipped (never clipped first: a clipped key escapes its
            # redaction); it reaches only the console log.
            raise ClientError(f"{self.binary} --version failed: {redact(err or out)[-300:]}", kind="exit-nonzero")
        # What the client printed, redacted whole, then clipped: for the run's console log and its private record
        # only (harness/probe.py). No public result carries a client version.
        return redact((out or err).strip())[:300]

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
    """Claude Code, on a Claude login (claude-subscription). Its secure storage is the Keychain with a plaintext
    fallback; under its throwaway HOME `security` finds no Keychain, so the login is <state folder>/.credentials.json."""
    harness, client_id, binary = "claude", "claude-code", "claude"
    login_file, needs_login_file = ".credentials.json", True
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
            raise ClientError("no usage in the result", kind="no-usage")
        read, created = u.get("cache_read_input_tokens") or 0, u.get("cache_creation_input_tokens") or 0
        made = u.get("cache_creation") or {}
        models = list((result.get("modelUsage") or {}).keys())
        turns = result.get("num_turns")
        calls = 1 if turns == 1 and len(models) == 1 else max(turns or 0, len(models), 2)
        return Usage(total=(u.get("input_tokens") or 0) + read + created, cached=read, write=created, calls=calls,
                     model=models[0] if len(models) == 1 else None,
                     write_5m=made.get("ephemeral_5m_input_tokens"), write_1h=made.get("ephemeral_1h_input_tokens"),
                     handle=result.get("session_id"))


# The records of a Codex session file that bear on which model answered a turn, and on which turn a record is of.
CODEX_MODEL_RECORDS = ("turn_context", "model_reroute")
CODEX_TURN_EVENTS = ("task_started", "task_complete", "turn_started", "turn_complete", "turn_aborted")


def codex_records(path, start=0):
    """[(kind, turn id or None, model or None)] of the records of a Codex session file from byte `start` on: every
    `turn_context` (its model), every `model_reroute` (the model it rerouted to), every turn event, and any other
    record that carries a turn id (kind `other`). A line that is not JSON is kind `unreadable`."""
    out = []
    with open(path, "rb") as f:
        f.seek(start)
        data = f.read()
    for raw in data.decode("utf-8", "replace").splitlines():
        if not raw.strip():
            continue
        try:
            d = json.loads(raw)
        except ValueError:
            out.append(("unreadable", None, None))
            continue
        if not isinstance(d, dict):
            continue
        p = d.get("payload") if isinstance(d.get("payload"), dict) else {}
        tid = p.get("turn_id") if isinstance(p.get("turn_id"), str) and p.get("turn_id") else None
        if d.get("type") == "turn_context":
            out.append(("turn_context", tid, p.get("model") if isinstance(p.get("model"), str) else None))
        elif d.get("type") == "event_msg" and p.get("type") == "model_reroute":
            out.append(("model_reroute", tid, p.get("to_model") if isinstance(p.get("to_model"), str) else None))
        elif d.get("type") == "event_msg" and p.get("type") in CODEX_TURN_EVENTS:
            out.append((p["type"], tid, None))
        elif tid:
            out.append(("other", tid, None))
    return out


def codex_mark(path):
    """What a Codex session file holds before an invocation: its path, its size and every turn id in it."""
    if not path:
        return {"path": None, "size": 0, "ids": []}
    try:
        size = os.path.getsize(path)
        ids = sorted({tid for _, tid, _ in codex_records(path) if tid})
    except OSError:
        return {"path": None, "size": 0, "ids": [], "unreadable": True}
    return {"path": path, "size": size, "ids": ids}


def codex_answer(path, mark, requested):
    """(model, issue, evidence) of the one invocation that ran after `mark` (codex_mark before it), read from the
    records it added to the session file. The check counts only when:
      - the records added carry exactly one turn id, never seen before in the file (a repeated or older id is not
        this invocation's turn), and every turn record added carries an id;
      - every model record added (`turn_context`, `model_reroute`) carries that turn's id, and together they name
        exactly one model;
      - that model is the requested one.
    Otherwise: `no-model` (no new turn, or a new turn with no model record), `ambiguous-model` (a model record of no
    turn or of another turn, an older turn id, two new turns, two models for the turn, a file that changed under the
    mark, or a line that cannot be read), or `other-model` (one clear model, not the requested one)."""
    if not path:
        return None, "no-model", None
    if mark is None or mark.get("unreadable") or (mark.get("path") and mark["path"] != path):
        return None, "ambiguous-model", None
    try:
        if os.path.getsize(path) < mark["size"]:
            return None, "ambiguous-model", None
        records = codex_records(path, mark["size"])
    except OSError:
        return None, "ambiguous-model", None
    if any(kind == "unreadable" for kind, _, _ in records):
        return None, "ambiguous-model", None
    old = set(mark.get("ids") or ())
    ids = []
    for kind, tid, _ in records:
        if tid and tid not in ids:
            ids.append(tid)
        if not tid and kind != "other":
            return None, "ambiguous-model", None  # a turn or model record of no turn
    if any(t in old for t in ids) or len(ids) > 1:
        return None, "ambiguous-model", None
    if not ids:
        return None, "no-model", None
    models = {m for kind, tid, m in records if kind in CODEX_MODEL_RECORDS}
    if any(kind in CODEX_MODEL_RECORDS and not m for kind, _, m in records):
        return None, "ambiguous-model", None  # a model record without a model name
    if not models:
        return None, "no-model", None
    if len(models) > 1:
        return None, "ambiguous-model", None
    model = models.pop()
    if model != requested:
        return model, "other-model", None
    return model, None, "own-turn"


CODEX_MODEL_KEYS = ("model", "to_model", "from_model")


def codex_models(path):
    """Every model name any record of a Codex session file carries, read whole from its first byte (any `model`,
    `to_model` or `from_model` string, at any depth of any record). A line that is not JSON, or a file that cannot be
    read, gives `<unreadable>`: it cannot be shown to name only one model."""
    found = set()

    def walk(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if k in CODEX_MODEL_KEYS and isinstance(v, str):
                    found.add(v)
                else:
                    walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    try:
        with open(path, "rb") as f:
            for raw in f.read().decode("utf-8", "replace").splitlines():
                if not raw.strip():
                    continue
                try:
                    walk(json.loads(raw))
                except ValueError:
                    found.add("<unreadable>")
    except OSError:
        found.add("<unreadable>")
    return found


# The item types of a Codex turn that are not a tool call: a turn with any other item made more than one request.
CODEX_TEXT_ITEMS = {"agent_message", "reasoning"}
# Codex refuses a message above MAX_USER_INPUT_TEXT_CHARS (1,048,576 characters) before it sends anything.
CODEX_CAP = re.compile(r"1,?048,?576|(?:maximum|max) (?:input |message )?(?:length|size).{0,40}characters", re.I)


class Codex(Client):
    """OpenAI's Codex CLI, on a ChatGPT plan (codex-subscription)."""
    harness, client_id, binary = "codex", "codex-cli", "codex"
    login_file = "auth.json"
    cumulative = True  # `codex exec resume --json` reports the thread's running total, not the last turn
    prompt_mode = "stdin"
    defaults = ("~/.codex",)

    def home_vars(self, home):
        return {"CODEX_HOME": home}

    # The ChatGPT plan's route is Codex's built-in provider `openai` with the ChatGPT login: forced on every command
    # line (`-c model_provider="openai"`, Codex's documented `-c key=value` override of config.toml), and a state
    # folder whose config.toml selects anything else is refused before any run (preflight).
    PROVIDER = "openai"
    # config.toml keys that could send a run elsewhere: a provider, a profile (its model_provider would win over the
    # command line's), provider definitions, other base URLs.
    ROUTE_KEYS = ("model_provider", "profile", "profiles", "model_providers", "chatgpt_base_url", "openai_base_url")
    # The helpers Codex links into CODEX_HOME at every start (arg0 dispatch): both point to the codex executable.
    HELPER_LINK = re.compile(r"^tmp/arg0(?:-macos)?/codex-arg0[A-Za-z0-9]{6}/(?:apply_patch|applypatch)$")

    def _config(self):
        # The login is a file in the state folder; never the Keychain, where the everyday login may be.
        return ["-c", 'cli_auth_credentials_store="file"', "-c", f'model_provider="{self.PROVIDER}"',
                "-c", f'model_reasoning_effort="{self.effort}"']

    def login_command(self):
        return ["codex", "login", "status", "-c", 'cli_auth_credentials_store="file"',
                "-c", f'model_provider="{self.PROVIDER}"']

    def preflight(self, state):
        path = os.path.join(state, "config.toml")
        if not os.path.lexists(path):
            return
        import tomllib
        try:
            with open(path, "rb") as f:
                cfg = tomllib.load(f)
        except (OSError, ValueError) as e:
            raise SystemExit(f"codex-cli: <client-home>/codex-cli/config.toml cannot be read ({type(e).__name__}): "
                             "refused (the route must be the ChatGPT plan's)")
        bad = [k for k in self.ROUTE_KEYS if k in cfg and not (k == "model_provider" and cfg[k] == self.PROVIDER)]
        if bad:
            raise SystemExit(f"codex-cli: <client-home>/codex-cli/config.toml sets {', '.join(bad)}: a run could go to "
                             f"another provider than `{self.PROVIDER}` (the ChatGPT plan): remove them")

    def allowed_link(self, rel, target, env=None):
        import shutil
        exe = shutil.which("codex", path=(env or os.environ).get("PATH"))
        return bool(self.HELPER_LINK.match(rel)) and bool(exe) and target == os.path.realpath(exe)

    def rollout(self, state, handle):
        if not state or not handle or not re.fullmatch(r"[0-9A-Za-z-]{8,64}", str(handle)):
            return None
        found = sorted(glob.glob(os.path.join(state, "sessions", "*", "*", "*", f"rollout-*-{handle}.jsonl")))
        return found[-1] if found else None

    def turn_mark(self, state, handle):
        # A new session (no handle yet): its file is all this invocation's.
        return codex_mark(self.rollout(state, handle) if handle else None)

    def answered_model(self, state, handle, after=None):
        """From the thread's session file in CODEX_HOME/sessions (`codex exec --json` prints no model): the model of
        the one turn this invocation added, bound to it by its turn id, and only when it is the requested model (see
        codex_answer; `after` is turn_mark before the invocation). Only that one string is read out; the file stays in
        the state folder."""
        return codex_answer(self.rollout(state, handle), after, self.model)

    def other_models(self, state, handle):
        """Every model but the requested one that the thread's session file names anywhere, read whole (codex_models);
        `<no session file>` when there is none to read. Names a public record cannot hold become `<unrecognised>`."""
        path = self.rollout(state, handle)
        if not path:
            return {"<no session file>"}
        return {m if m.startswith("<") else (model_text(m) or "<unrecognised>")
                for m in codex_models(path) if m != self.model}

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
                raise Refused("client-cap", text.strip())
            raise classify(text if text.strip() else (stdout or f"exit {code}"))
        if expect and expect.get("session") and tid and tid != expect["session"]:
            raise ClientError(f"the output is of thread {tid}, not of the resumed one", kind="wrong-turn")
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
                raise ClientError(f"the export is of session {d.get('session_id')}, not of the resumed one",
                                  kind="wrong-turn")
            said = steps[last_user].get("message") if last_user >= 0 else None
            said = said if isinstance(said, str) else json.dumps(said)
            if (expect.get("prompt") or "").strip()[:200] not in (said or ""):
                raise ClientError("the export's last user step is not the prompt just sent: no new turn", kind="wrong-turn")
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
        u, failure, other, usages, runs = None, [], [], [], 0
        for d in json_lines(stdout):
            kind = str(d.get("payload_type") or d.get("type") or "")
            if kind == "run.started":
                runs += 1
            elif kind == "run.usage":
                u = d.get("payload") or {}
                usages.append(u)
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
            raise ClientError("no run.usage line" + (f"; usage-like events: {' | '.join(other[:2])}" if other else ""),
                              kind="no-usage")
        # Every run in the output counts: two runs (two run.started, or two run.usage) are at least two calls, never
        # the last run's figures alone.
        # A count is what Muse said: an explicit 0 is no call, an absent or non-integer count is unknown (None), and
        # neither is ever promoted to one; a check counts only on an explicit single call (harness/probe.py).
        ms = [m for x in usages for m in (x.get("models") or [])]
        counts = [x.get("calls") for x in usages]
        if not all(isinstance(c, int) and not isinstance(c, bool) and c >= 0 for c in counts):
            calls = None
        else:
            calls = sum(counts)
            if runs > 1 or len(usages) > 1:
                calls = max(calls, runs, len(usages))
        names = {m.get("model") for m in ms}
        return Usage(total=sum(m.get("input_tokens", 0) for m in ms), cached=sum(m.get("cached_tokens", 0) for m in ms),
                     write=None, calls=calls, model=ms[0].get("model") if len(names) == 1 and ms else None)


CLIENTS = {c.harness: c for c in (Claude, Codex, Devin, Muse)}


# Every client's everyday folders (pi's ~/.pi too): no state folder lies in any of them, whichever client it is for.
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


def links_out(folder, allowed=None):
    """Symbolic links under `folder`, at any depth, whose target leaves it (or does not resolve). `allowed(rel, target)`
    names the links a client itself makes there (Codex's helpers): those, and only those, are left out."""
    real, out = os.path.realpath(folder), []
    for d, dirs, files in os.walk(folder, followlinks=False):
        for name in dirs + files:
            p = os.path.join(d, name)
            if os.path.islink(p) and not inside(os.path.realpath(p), real):
                rel = os.path.relpath(p, folder)
                if allowed and allowed(rel, os.path.realpath(p)):
                    continue
                out.append(rel)
    return sorted(out)


# Folders a sync service copies off the machine: no state folder, throwaway home or captured output lies in one.
CLOUD_SYNC = ("~/Library/Mobile Documents", "~/Library/CloudStorage", "~/Dropbox", "~/Google Drive", "~/OneDrive",
              "~/iCloud Drive")
CLOUD_PART = re.compile(r"^(?:Mobile Documents|CloudStorage|Dropbox(?: \(.*\))?|Google Drive|My Drive|OneDrive(?: - .*)?"
                        r"|iCloud Drive|com~apple~CloudDocs)$", re.I)


def in_cloud_sync(path, user_home):
    """The sync folder that holds `path`, or None: iCloud Drive, ~/Library/CloudStorage (Dropbox, Google Drive, OneDrive,
    Box), and the older ~/Dropbox, ~/Google Drive, ~/OneDrive*; a path component with one of their names counts too."""
    real = os.path.realpath(path)
    for d in CLOUD_SYNC:
        top = os.path.realpath(user_home + d[1:])
        if inside(real, top) or inside(os.path.abspath(path), user_home + d[1:]):
            return d
    for part in real.split(os.sep) + os.path.abspath(path).split(os.sep):
        if CLOUD_PART.match(part) or part.startswith("OneDrive"):
            return part
    return None


def check_folder(what, path, root, user_home):
    """A folder the run writes to: outside the repository, any Git checkout, every everyday folder and every folder a
    sync service copies off the machine."""
    real = os.path.realpath(path)
    if real == user_home or any(inside(real, os.path.realpath(user_home + d[1:])) for d in EVERYDAY):
        raise SystemExit(f"{what} is an everyday folder of a client (or inside one)")
    sync = in_cloud_sync(path, user_home)
    if sync:
        raise SystemExit(f"{what} is inside a folder a sync service copies off this computer ({sync}): use a local "
                         "folder such as ~/groundtruth-clients")
    if inside(real, os.path.realpath(root)):
        raise SystemExit(f"{what} is inside the repository")
    checkout = in_git_checkout(real)
    if checkout:
        raise SystemExit(f"{what} is inside a Git checkout")


def check_private(what, path, mode=0o700):
    """A folder (mode 700) or a login file (mode 600) of the night: the owner's, not a link, and nobody else's to read."""
    st = os.lstat(path)
    import stat as S
    if S.S_ISLNK(st.st_mode):
        raise SystemExit(f"{what} is a link: refused")
    if st.st_uid != os.getuid():
        raise SystemExit(f"{what} belongs to another user: refused")
    if S.S_IMODE(st.st_mode) != mode:
        raise SystemExit(f"{what} has mode {S.S_IMODE(st.st_mode):o}, not {mode:o}: run `chmod {mode:o}` on it "
                         "(docs/own-clients-RUN.md, step 1)")


# A client's login file, wherever in its state folder the client keeps it: mode 600, never a link.
LOGIN_NAMES = {".credentials.json", "auth.json", "credentials.toml"}


def login_files(state):
    out = []
    for d, dirs, files in os.walk(state, followlinks=False):
        out += [os.path.join(d, n) for n in files + dirs if n in LOGIN_NAMES]
    return sorted(out)


def prepare_home(what, state, base, root, user_home, allowed=None):
    """The client's throwaway HOME (throwaway_home), made when missing (mode 700): under <client-home>, never a link out
    of it, outside the repository, every Git checkout, every everyday folder and every synced folder, private (700),
    holding no link that leaves it."""
    home = throwaway_home(state)
    for kind, folder in (("HOME", home), ("TMPDIR", throwaway_tmp(state))):
        rel = f"<client-home>/{os.path.basename(os.path.dirname(folder))}/{os.path.basename(state)}"
        if os.path.islink(folder) or os.path.islink(os.path.dirname(folder)) or \
                (os.path.lexists(folder) and not os.path.isdir(folder)):
            raise SystemExit(f"{what}: its {kind} {rel} is not under <client-home> (a link out of it, or not a folder): "
                             "refused")
        for d in (os.path.dirname(folder), folder):
            if not os.path.isdir(d):
                os.mkdir(d, 0o700)
                os.chmod(d, 0o700)
        real, real_base = os.path.realpath(folder), os.path.realpath(base)
        if not inside(real, real_base) or real == real_base:
            raise SystemExit(f"{what}: its {kind} {rel} is not under <client-home> (a link out of it): refused")
        check_folder(f"{what}: its {kind}", folder, root, user_home)
        check_private(f"{what}: {os.path.dirname(rel)}", os.path.dirname(folder))
        check_private(f"{what}: its {kind} {rel}", folder)
        out = links_out(folder, allowed)
        if out:
            raise SystemExit(f"{what}: its {kind} holds links that leave it: {', '.join(out[:5])}")
    return home


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
    if client.harness == "devin":
        # A positive login only, read with the terminal's styling removed: a line that says it is logged in, nothing
        # that says otherwise, and no mention at all of an API, a token or a key (whatever the wording, any such status
        # may be another login than the subscription's). The exit code alone is never a login.
        plain = strip_ansi(text)
        if re.search(r"api|token|key", plain, re.I):
            return "the status mentions an API, a token or a key: not the subscription login"
        if DEVIN_NOT_LOGGED_IN.search(plain):
            return "the status does not show a login (it says it is not, or no longer, logged in)"
        if not any(DEVIN_LOGGED_IN.fullmatch(line.strip()) for line in plain.splitlines()):
            return "the status does not say 'Logged in'"
        return None
    if re.search(r"api[ _-]?key", text, re.I):
        return "the status names an API key"
    return None


# The Devin CLI's status: a whole line `Logged in`, `Logged in.`, `Logged in as <who>` or `Logged in (via <how>)` (the
# wording in its 3000.14 binary), and none of its negative wordings.
DEVIN_LOGGED_IN = re.compile(r"logged in(?:\.|\s+as\s+\S.*|\s+\(via\s+[^)]+\)\.?)?", re.I)
DEVIN_NOT_LOGGED_IN = re.compile(r"not\s+(?:logged|signed)\s+in|(?:logged|signed)\s+out|no\s+longer|log\s*in\s+first"
                                 r"|re-?authenticat|expired|not\s+authori[sz]ed|no\s+credentials", re.I)
# Terminal styling and control sequences (CSI, OSC, single escapes) and any other control character but a newline.
ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)?|\x1b[@-Z\\-_]|[\x00-\x09\x0b-\x1f\x7f]")


def strip_ansi(text):
    return ANSI.sub("", text or "")


def state_folder(client, base, root, user_home=None, env=None, run=None, check_login=True):
    """The client's state folder, `<base>/<client id>` made absolute, or SystemExit. It must exist, lie outside the
    repository, every Git checkout, every everyday folder and every synced folder, be private (700, as <client-home>
    is), hold no symbolic link that leaves it but the ones the client itself makes (Client.allowed_link), keep its
    login file at mode 600, pass the client's own preflight (Codex: the provider its config selects), and be logged in
    with the login the route needs (its status output read, not only its exit code)."""
    if not base:
        raise SystemExit(f"{client.client_id}: --client-home (or GROUNDTRUTH_CLIENT_HOME) is required for an own client")
    user_home = os.path.realpath(user_home or os.path.expanduser("~"))
    name = client.client_id
    lexical = os.path.abspath(os.path.join(base, name))
    home = os.path.realpath(lexical)
    if not os.path.isdir(home):
        raise SystemExit(f"{client.client_id}: its state folder <client-home>/{name} does not exist: "
                         "create it and log the client in there first (docs/own-clients-RUN.md)")
    check_folder(f"{client.client_id}: <client-home>", base, root, user_home)
    check_private(f"{client.client_id}: <client-home>", os.path.abspath(base))
    check_folder(f"{client.client_id}: the state folder", home, root, user_home)
    check_private(f"{client.client_id}: the state folder <client-home>/{name}", lexical)
    allowed = client.allowed_link_for(env)
    out = links_out(home, allowed)
    if out:
        raise SystemExit(f"{client.client_id}: the state folder holds links that leave it: {', '.join(out[:5])}")
    for f in login_files(home):
        check_private(f"{client.client_id}: the login file <client-home>/{name}/{os.path.relpath(f, home)}", f, 0o600)
    client.preflight(home)
    prepare_home(f"{client.client_id}", home, base, root, user_home)
    if check_login:
        if client.needs_login_file and not client.login_evidence(home):
            raise SystemExit(f"{client.client_id}: refused: no login file in its state folder (<client-home>/{name}/"
                             f"{client.login_file}, non-empty): its status could be answered by a login kept elsewhere")
        why = login_status(client, home, env, run)
        if why:
            raise SystemExit(f"{client.client_id}: refused: {why}")
        for k in client.passthrough:
            if not (env if env is not None else os.environ).get(k):
                raise SystemExit(f"{client.client_id}: {k} is not set (read it from the Keychain into the environment)")
    return home


def login_status(client, state, env=None, run=None):
    """None when the client's own status command, run in its folders and sandbox, shows the subscription login; else
    why not."""
    cmd = client.login_command()
    if not cmd:
        return None
    e = env if env is not None else client.environment(state)
    try:
        code, o, er = (run or _run)(confine(cmd, e, [state, e.get("HOME"), e.get("TMPDIR")]), env=e, cwd=None,
                                    stdin=None, timeout=120)
    except subprocess.TimeoutExpired:
        return f"the status command did not answer within 120 s ({' '.join(cmd[:4])})"
    why = login_ok(client, code, o, er)
    return f"{why} ({' '.join(cmd[:4])})" if why else None


# --- the OS-level layer: each client process under sandbox-exec, no write under the home folder but its own folders --

SANDBOX_EXEC = "/usr/bin/sandbox-exec"


def sandbox_profile(writable, user_home=None):
    """A Seatbelt profile: everything as usual, but no file write under the owner's real home folder except under
    `writable` (the client's state folder, its throwaway HOME, its temporary folder)."""
    user_home = os.path.realpath(user_home or os.path.expanduser("~"))
    paths = sorted({os.path.realpath(w) for w in writable if w})
    for p in [user_home, *paths]:
        if '"' in p or "\\" in p:
            raise SystemExit(f"sandbox: a folder name with a quote or a backslash cannot be confined: {p!r}")
    for p in paths:
        if inside(user_home, p):
            raise SystemExit("sandbox: an allowed folder is the home folder or holds it: refused (it would allow every "
                             "write the profile exists to deny)")
    allow = " ".join(f'(subpath "{p}")' for p in paths)
    return (f'(version 1)(allow default)(deny file-write* (subpath "{user_home}"))'
            + (f"(allow file-write* {allow})" if allow else ""))


CONFINED = sys.platform == "darwin"  # Linux and others: the environment's isolation only (recorded by the probe)


def confine(argv, env, writable, user_home=None):
    """`argv` under sandbox-exec on macOS (see sandbox_profile); as it is elsewhere."""
    if not CONFINED:
        return list(argv)
    if not os.path.exists(SANDBOX_EXEC):
        raise SystemExit(f"{SANDBOX_EXEC} is missing: a client is never run without its write boundary on macOS")
    return [SANDBOX_EXEC, "-p", sandbox_profile(writable, user_home), *argv]


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
        paths = [p for p in paths if p and p != os.sep]
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

    def scrub(self, text):
        """The secret values (as they are, and as JSON writes them), the run's folders and any home-folder path: for a
        public record or a console log, whose other fields (session ids, model names) must stay readable."""
        text = text or ""
        for v in self.secrets:
            text = text.replace(v, "<secret>").replace(json.dumps(v)[1:-1], "<secret>")
        for p in self.paths:
            if len(p) > 1:
                text = text.replace(p, "<folder>").replace(json.dumps(p)[1:-1], "<folder>")
        return HOME_PATH.sub("<home>", text)


MODEL_TEXT = re.compile(r"[A-Za-z0-9._:/@+-]{1,100}")


def model_text(name):
    """A model id as a public record may hold it, or None (no model evidence): a reply naming anything else names no
    model."""
    return name if isinstance(name, str) and MODEL_TEXT.fullmatch(name) else None


def write_private(path, text):
    """A new file, mode 600, never through a link (O_NOFOLLOW) and never over an existing one (O_EXCL)."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(text)
    os.chmod(path, 0o600)


def _run(argv, env, cwd, stdin, timeout):
    p = subprocess.run(argv, cwd=cwd, env=env, stdin=stdin if stdin is not None else subprocess.DEVNULL,
                       capture_output=True, text=True, timeout=timeout)
    return p.returncode, p.stdout, p.stderr


class Session:
    """start() and resume() for the loops, from a client's command() and parse(). `io` holds the prompt and export
    files (deleted after each invocation); `work` is the client's working folder and stays empty."""

    def __init__(self, client, env, io, work, run=None, timeout=900, create=True, home=None, keep=None, writable=None):
        self.client, self.env, self.io, self.work = client, env, io, work
        self.run, self.timeout = run or _run, timeout
        # `writable`: the folders the client may write under the owner's home folder (its state folder, its throwaway
        # HOME, its temporary folder); every invocation then runs under sandbox-exec (confine). None: not confined.
        self.writable, self.home = writable, home
        # Every text of the client's that leaves this object (an error, a refusal, a kept output) is redacted.
        self.redact = Redactor(env, [home, home and os.path.dirname(home), io, work, os.path.dirname(io),
                                     (env or {}).get("HOME"), (env or {}).get("TMPDIR"), *(writable or ()),
                                     os.path.expanduser("~")])
        # A private folder for the redacted raw output (smoke runs), or None: checked and made (mode 700) by the
        # caller (harness/probe.py, private_capture_folder); every file in it is written mode 600.
        self.keep, self.count = keep, 0
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
        # The session's turns before this invocation: a model read from its record afterwards must be a newer turn's.
        mark = self.client.turn_mark(self.home, resume)
        if self.client.prompt_mode == "arg":
            argv = [prompt if a == pf else a for a in argv]
        if self.writable is not None:
            argv = confine(argv, self.env, self.writable)
        try:
            with open(pf) as stdin:
                try:
                    code, out, err = self.run(argv, env=self.env, cwd=self.work,
                                              stdin=stdin if self.client.prompt_mode == "stdin" else None,
                                              timeout=self.timeout)
                except subprocess.TimeoutExpired:
                    # Never the exception's text: it holds the command line, the sandbox profile and its folders.
                    raise ClientError(f"the client did not answer within {self.timeout} s", kind="timeout") from None
                except OSError as e:
                    raise ClientError(f"the client could not be run ({type(e).__name__})", kind="spawn") from None
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
                write_private(os.path.join(self.keep, f"{self.count:03d}-{'check' if resume else 'start'}-{name}.txt"),
                              self.redact(text))
        expect = {"prompt": prompt, "session": resume}
        try:
            u = self.client.parse(out, err, code, contents, expect=expect)
        except Refused as e:
            # Redacted whole, then clipped: a clipped key would escape its redaction. Its text is for the console log
            # and the limits walk; a public result records only the kind.
            r = Refused(e.kind, self.redact(e.text)[-2000:])
            r.code = code  # the client's exit code, kept with a refusal row
            raise r from None
        except ClientError as e:
            r = ClientError(self.redact(str(e))[-1500:], kind=e.kind or ("exit-nonzero" if code else "parse"))
            r.code = code
            raise r from None
        except (ValueError, KeyError, TypeError) as e:
            r = ClientError(self.redact(f"unreadable output ({type(e).__name__}): {e}")[-1500:], kind="parse")
            r.code = code
            raise r from None
        if u.handle is None:
            u.handle = resume or session
        if u.model is None:
            # Only this invocation's own turn: never a model carried over from an earlier one.
            u.model, u.model_issue, u.model_evidence = self.client.answered_model(self.home, u.handle, after=mark)
        if u.model is not None:
            shown = model_text(self.redact(str(u.model)))
            if shown != u.model:
                # A model name a public record cannot hold as it is: no model evidence at all.
                u.model, u.model_issue, u.model_evidence = None, "no-model", None
        return u

    def start(self, prompt):
        u = self._go(prompt)
        return u.handle, u

    def resume(self, handle, prompt):
        return self._go(prompt, resume=handle)
