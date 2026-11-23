# Measuring a login through its vendor's own client

A design, written on 2026-11-22. Nothing in it has been run: no request was sent to a provider or a login for it.
It says how groundtruth measures each login through the client its vendor ships, how OpenRouter's proxy-only
entries are measured again directly, what changes in `observed.json`, which runs are owed and what has to be built.

**Since the first night (2026-11-23), where 17 of the 25 runs stopped early.** Seven Devin runs ended `quota` on a
rate limit that named its reset, six Devin and three Codex runs on one cold control, DV12 on an unknown model id. So
(section 1, rules 3 and 5 to 7): a rate limit that says when it resets is `rate-limited`, waited for and sent again
(5 tries, 10 minutes a sample, a `rate-wait` line per wait), and a plan's limit stays `quota`; a client's runs share
one request budget per minute across processes (Devin 24, from the night's own counts); a cold control gets one more
in a fresh session, and only two cold controls end a run; every model id is checked against the client's own list
before the go (DV12 is now `deepseek-v4-pro-high`). `night.py status` and `stop` read `ps` in the C locale and
compare start times as times, so a lock written by a shell in another language still matches; `--go CX1,CX3,DV1`
re-runs chosen runs on a new date folder (`own-clients-RUN.md`, "Re-running some runs").

**Since the final check (2026-11-22): the first night is Codex CLI and Devin CLI only** (the owner's decision: the
two logins where differences were seen). Claude Code and Muse Code wait for a later night: their smoke and cache runs,
`login claude`, the Muse Keychain item and its fingerprint, and the Claude overage logic are out of every night
command (their drivers stay in `harness/clients.py`, tested). A public result carries no client error text at all,
only a kind from `clients.ERROR_KINDS`; the detail goes to the run's console log (mode 600), redacted whole before any
clipping. The launcher records its own pid before any run and looks for the client's stop mark before each start;
`stop` sets the mark, then signals only the pids the lock records (the launcher, then the runs), each checked by
its recorded start time and command line; never a process group. Since the eighth review the mark is the authority
and signals only the fast path: every run looks for the mark immediately before each client invocation and exits
without calling the client once it is there, and waits (5 s at most) for its own pid in the lock before its first
one; `stop` refuses, writing nothing, when the marks' folder resolves to an everyday folder. A night starts only from
a checkout whose `git config core.hooksPath` is `scripts` (each worktree runs its own commit hook). Since the ninth
review: that check reads the hook Git will really run (`git rev-parse --git-path hooks/pre-commit`: it must exist,
be executable and be the checkout's own `scripts/pre-commit`); every public line is written by one allowlist
(`probe.Public`: listed keys, numbers, booleans, strings of a fixed set or of the run's plan; a reported model is only
`model_matches`, a session only its number; the rest goes to the console log); and the everyday-folder guard compares
real folders (device and inode of the target and of each existing folder above it), not spellings. A check without
model evidence of its own turn is `check-invalid` (`no-model`) in the probe and never published by the builder;
Codex's model evidence is bound to the invocation's own new turn. A priming that is not one explicit model request is
retried, never used.

**Since the third review (2026-11-22): the last round before the night.** A login is done only when the client's
login file is in its state folder (non-empty, then 600) and its own status shows the subscription; a Claude run is
refused without that file. Each client's TMPDIR is its own, `<client-home>/tmp/<client>`, never the shell's, and no
sandbox exception may hold the home folder. Modes are exact (700, 600). Console logs are 600 and the probe's errors,
the version diagnostic and a timeout included, reach them and the public JSONL redacted. A Muse count of 0 is no call,
an absent one unknown; the builder refuses a check that is not one explicit call, and a check answered by another
model than the manifest's (Codex's model evidence is bound to the measured turn). The launcher records each worker's
pid as it starts, and `status`/`stop` also find a worker by its launch id. `scan_secrets.py --own-clients` reads no
proxy or pi file. The morning report says when the Keychain could not be listed. Claude runs stop at a first 5-minute
cache write (paid overage) unless `--allow-overage`; CC5 – CC8 do not start after such a stop.

**Since the second review (2026-11-22): the first night is the own clients' cache runs only** (the chief's decision).
It supersedes what the list below says of pi, Provimux, OpenRouter and the supervisor:

- **Out of the first night**: every pi run, `pi-setup` and the reading of Provimux's configuration (the parity pairs
  of section 7 come in a later night; `harness/clients.py` has no pi client any more); every OpenRouter run and window
  request of 4.1, with the money stop and its reservations; the supervisor. What stays is S1 – S4 and S3b, CC1 – CC8,
  CX1 – CX6, DV1 – DV18 with DV9d (pair DV-5 compares two Devin runs) and MC1 – MC3. The TypeScript probe (`src/`)
  stays as it is, shared and reached by no night command.
- **A launcher, not a supervisor**: `night.py --go <client>` (or `--go all`) starts each of that client's runs as its
  own background process, staggered by `--delay`, and returns; one lock file per client and night, created
  exclusively, refuses a second start. `status` reads each recorded run's process (its pid, its recorded start time,
  and its command line carrying the run's label and the launch's id); `stop <client>|all` signals exactly those pids. Every command honours
  `--dry-run` with no side effect. CC5 – CC8 begin 2 h 30 min after the go, when CC1 – CC4 are over.
- **The night's folders**: local (none under iCloud Drive, `~/Library/CloudStorage`, Dropbox, Google Drive or
  OneDrive), private (folders 700, login files 600), Codex's own two helper links allowed by their exact pattern;
  every client process runs under `sandbox-exec` (no file write under the home folder outside its state folder, its
  throwaway home and its temporary folder). The raw output of the smoke runs is kept under `<client-home>` only,
  through no link, folder 700 and files 600.
- **Codex** runs with `-c model_provider="openai"` on every command line, and a state folder whose `config.toml`
  selects another provider, a profile or another base URL is refused; the model that answered is read from the
  thread's session file, and a check counts only when the invocation added exactly one new turn there, with a
  `turn_context` carrying that turn's id and naming the requested model, and no other model record (a
  `model_reroute`, a context of another or an older turn); otherwise it is `check-invalid` (`no-model`,
  `ambiguous-model` or `other-model`), and the builder refuses a Codex check without `model_evidence` `own-turn`.
  At the run's level, every session file of the run is read whole after each check and at its end (`model-scan`):
  any model but the requested one anywhere stops and excludes the whole run. The public `model-scan` line carries no
  text from any session file: `final`, `other_models` (a count) and `unreadable`; the names go to the console log
  only.
- **Publication** of a night waits for its audit: `scripts/build_observed.py` refuses every own-client run of the
  new design until `results/own-clients-<date>/AUDIT.md` begins with `# Own-client night audit: passed`, which a
  person writes after reading the raw results, the Codex session files and the console logs
  (`own-clients-RUN.md`, the audit checklist). The commit hook and CI refuse any file under `results/own-clients-*`
  before that night's `AUDIT.md`, and the builder any symbolic link there and any `excluded` entry of an unaudited
  night.
- **The smoke review** is checked by `night.py` itself: S3b's cold control (`stop`/`no-observable-cache`) is an
  expected answer; a late control is refused, and a probe whose control can only be checked late stops
  (`control-late`).
- **M-3**: two replicas of one age are primed at least five minutes apart, whatever a slow priming did to its wave.

**Since the review of the build (2026-11-22).** What changed against the text below, as built on this branch:

- **The first night is narrowed** (the chief's decision): no input limit through an own client. The limits walks of
  4.4 and the refused request of each smoke run (4.2) are out of the plan; `harness/client_limits.py` stays, not yet
  trusted, and `scripts/build_observed.py` publishes no own-client limits row. A login's input limits stay the
  proxy's. The OpenRouter windows of 4.1 stay.
- **The parity design's measuring rules** (Provimux, `.github/provimux/design/client-parity.md`, section 4.5): M-1, the
  same model variant on both sides of a pair, a Devin id with its effort suffix given to Provimux as it is; M-2, the
  Devin CLI with `--process-model in-process` and `DEVIN_CACHE_KEEPALIVE_MAX_PINGS=0`, both recorded; M-3, an age's
  samples primed in three waves at least five minutes apart; M-4, a pi run records the Provimux build, pi's version,
  pi-provimux's commit, the transport and the payload rules: the `payload` section of Provimux's configuration,
  read by the run itself, nothing else of that file. The pairs of its section 7 are in the plan (without CX-3's
  second run, without CX-S (b), and without Antigravity), each pi run started beside its own-client run, pi from a
  state folder of its own that `night.py pi-setup` makes with pi's own `pi install`.
- **No Meta rule switch**: MC-1's pi run goes through Provimux's payload rules as configured (Muse Code caches no
  conversation, so the pair's question is answered); there is no second MC-1 pi run.
- **One go for the night**: after the smoke review, `night.py --go night` starts a detached supervisor that launches
  every part, starts the 5-minute Claude runs when CC1 – CC4 have ended, and writes the morning report of the
  everyday state at the end; `status` and `stop all` watch and stop it. The owner's part is the one-time setup (the
  folders, the snapshot, three logins, three keys, a look at the report), and he uses his computer as usual all night.
- **Claude Code's own retries** are switched off with `CLAUDE_CODE_MAX_RETRIES=0` (a variable of the 2.1.330
  binary); every Claude run records it and that a check may hide a retry if the client does not honour it.
- **Every new session's first line** names the measurement (`groundtruth cache measurement <salt> (an automated test,
  not a task).`), so that sessions a vendor lists in the account (Devin) can be told apart from the owner's work.
- **The everyday state is protected by isolation, and reported, never a stop.** Every client process of the night
  gets a throwaway home folder (`HOME=<client-home>/home/<client>`) beside its state folder, for the logins too; a
  client that ignores its state folder's variable writes there. Under that `HOME`, `security` finds no default
  keychain, so Claude Code keeps its login in its state folder (`.credentials.json`); this changes where a client
  looks by default, it is not a boundary around the owner's Keychain. The everyday folders (to their depth: path, size and modification time) and the Keychain's
  item names are snapshot before the logins and reported in the morning, for a person to judge (section 2.1).
- **The TypeScript probe** (0.3.5) sends a check and the control's re-send once.

## Why

providers.dev publishes, for each value, the most direct measurement that exists for its route:

- **An API-key route** (`anthropic-api`, `openai-api`, `openrouter`): only `direct` runs. A proxy run on such a
  route stays in the records and feeds no value.
- **A login** (`claude-subscription`, `codex-subscription`, `devin`, `meta-subscription`, `antigravity`): the
  vendor's own client first; a proxy such as Provimux (a distribution of CLIProxyAPI) only where no own client can be scripted.

What the records hold today (`observed.json` at `72e0c29`):

| Route | Cache runs | Limits rows |
|---|---|---|
| `claude-subscription` | `cliproxyapi` 8 | `cliproxyapi` 4 |
| `codex-subscription` | `cliproxyapi` 14, `pi+cliproxyapi` 4, `codex-cli` 2 | `cliproxyapi` 4 |
| `devin` | `pi+cliproxyapi` 20, `devin-cli` 12, `cliproxyapi` 8 | `cliproxyapi` 12 |
| `meta-subscription` | `cliproxyapi` 8, `pi+cliproxyapi` 6, `muse-code` 1 | `cliproxyapi` 3 |
| `antigravity` | `cliproxyapi` 2 | none |
| `openrouter` | `direct` 88, `cliproxyapi` 24 | `direct` 4, `cliproxyapi` 9 |

The own-client runs that exist (15, of 7 to 9 November) were made before the ladder rule: two or three samples per
age, other ages than today's start, and the clients' everyday folders. They stay as they are; section 4 measures
again.

**Where each statement below comes from.** *(help)*: the client's own `--help` on the version installed, read for
this design. *(doc)*: the vendor's documentation, read on 2026-11-22. *(src)*: the client's public source.
*(run)*: groundtruth's own raw files. *(open)*: not established; the smoke run of section 5, step 6, settles it.
Versions: Claude Code 2.1.330, Codex CLI 0.170.0, Devin CLI 3000.14, Muse Code 1.4.24, Antigravity CLI 1.5.14.

## 1. Per login

One method for all of them, the one `harness/probe.py` already has: every sample is a new session of the client
whose first message carries a block of text no other sample has; after its age the session is resumed once with a
short message, and the cached-token count the client reports for that request is read. A check is warm when the
cache covers the part every session shares (the client's own system prompt and tools) and at least half of the
sample's block: `cached >= baseline + unique / 2`.

Four rules are new, for every client, and three more came from the first own-client night (2026-11-23, where 17 of
25 runs stopped early: a rate limit taken for quota, one cold control, an unknown model id):

1. **One model request per check.** A client that makes two requests in one turn (a tool call, then the answer)
   reports their sum, and the second request reads what the first one wrote: a cold check would count as warm. A
   check counts only when the client shows that the turn was one model request; otherwise it is logged as
   `check-invalid` and left out.
2. **A check is never sent twice.** Today a failed resume is retried after 30 seconds. If the first try reached the
   provider, the second measures a re-send, not the age. A check that fails is logged as `check-failed` and its
   sample is lost. A priming may be retried. The one exception is a rate limit (rule 5): the vendor refused the
   request before any model read it, so sending it again measures the age, not a re-send.
3. **The control comes first.** The control sample is primed, checked at 30 seconds, and only then are the others
   primed. **One cold sample is not enough to give up on a model**: a control that misses gets one more control, in a
   fresh session with a block of its own (`prime` and `check` lines with `"age": "control"`, `"rep": 1`). The run
   ends (`no-observable-cache`, as the method says) only when both miss, after five requests instead of ninety; both
   controls are recorded, and the builder counts both (`control: {warm, total}`). On 2026-11-23 the Codex runs that
   went on were warm in 22 to 28 of 27 to 29 checks, and gpt-6-luna, warm in the smoke run an hour before, stopped
   on one cold control (CX6).
4. **A quota refusal ends the run.** It is never retried (`--stop-on-refusal` in the TypeScript probe). A quota
   refusal is a plan's limit: "usage limit", "quota", "out of credits", "insufficient credits", "billing period",
   "hit your …", whatever the text says of a reset (`harness/clients.py`, `PLAN_LIMIT`).
5. **A rate limit waits; it is not quota.** A refusal that names a rate limit ("rate limit", "too many requests",
   429) *and* says when it resets ("reset in N seconds", "retry in N s", "try again in N minutes", "Retry-After: N",
   "at HH:MM UTC") is `rate-limited` (`clients.classify`, `rate_reset`). The request waits until the reset (the later
   of the two when both are named) plus 1 to 5 random seconds and is sent again: at most 5 tries for one request and
   at most 10 minutes of such waits for one sample. Each wait is a public `rate-wait` line (`age`, `rep`, `try`,
   `waitSec`). A check that a wait made late keeps the `late` rule (age x 1.1 + 90 s); a control that would be checked
   late ends the run (`control-late`). Past either limit the request is lost like any refused one (a priming
   `prime-refused`, a check `check-failed`, both of kind `rate-limited`); the run goes on. A rate limit that names no
   reset stays `quota`. On 2026-11-23 Devin refused seven runs within nine seconds with "Reached request rate limit.
   … Your limit will reset in 2 seconds (at 11:15 UTC)": each of those runs ended `quota`.
6. **Pacing: a client's runs share one request budget.** All of one client's runs of a night ask one budget before
   every request (`harness/pacing.py`): at most N requests in any 60 seconds, all runs together; two requests at least
   60/N seconds apart, so that the waves of many runs are spread instead of bunched; the primings use at most
   N - N/4 of them, the rest is kept for checks, and a check that waits for its turn goes before any priming. A run
   never holds a check that falls due while its own priming waits for a turn. The budget is kept across processes in
   `<client-home>/night-<date>/pacing/<client>.json` under an exclusive lock (`.lock`), mode 600, folder 700.
   Devin's is 24 a minute (`night.py --pace devin=N` changes it; Codex has none). Where it comes from: the `prime`,
   `check`, `baseline` and `retry` lines of all DV runs of 2026-11-23, by minute up to the first refusal (UTC):
   11:02 2, 11:03 27, 11:04 33, 11:05 21, 11:06 28, 11:07 40, **11:08 68**, 11:09 55, 11:10 14, 11:11 30, 11:12 37,
   **11:13 63**, 11:14 15 answered and 7 refused (the first refusal at 11:14:14). No per-minute ceiling shows: 68 and
   63 passed, and the refused minute had 22. What the refusals came after is 430 requests in 11 minutes 26 seconds
   (11:02:48 to 11:14:14, 37.6 a minute), all in the quarter hour that ended at 11:15, the reset Devin named. 24 a
   minute is 360 in a quarter hour, below those 430, and below any minute that passed. The runs that went on did
   about 20 a minute from 11:15 to 11:19 without a refusal. `--dry-run` runs the whole selection on a simulated
   clock with this budget and the real loop, and gives each run's expected end and each client's request total.
7. **Model ids are checked before the go.** Every run's model id must be in its client's own model list, read
   without a prompt (`harness/model_ids.py`): Codex's bundled catalog (`codex debug models --bundled`, offline, run in
   a throwaway `CODEX_HOME` with the network denied) and Devin's account list (`devin models list --format json`: it
   asks Devin's server, no prompt, no session; run in the state folder and sandbox, and only with its login there).
   `--dry-run` runs no client: it reads the checked list, `harness/model-ids.json`, each id with how it was checked;
   `--go` reads the client's own and falls back to that list when it cannot be read, saying so. A run whose id is not
   listed is refused, by name, before anything starts. On 2026-11-23 DV12 asked Devin for `deepseek-v4-pro-low`
   ("Unknown model", three times): DeepSeek V4 Pro on Devin has the levels `high` and `max` only, so DV12 is
   `deepseek-v4-pro-high`.

Ages count from the start of the priming request, as the README says; `probe.py` counts from its end today.

### 1.1 `claude-subscription`: Claude Code (new client id `claude-code`)

**Driving it.**

```bash
# a sample's first message, the prompt on stdin
claude -p --output-format json --model <id> --effort low --session-id <uuid> \
       --strict-mcp-config --disable-slash-commands --permission-prompts none < prime.txt
# its one check
claude -p --output-format json --model <id> --effort low --resume <uuid> \
       --strict-mcp-config --disable-slash-commands --permission-prompts none \
       "Reply with OK only. Do not use any tools."
```

- `--strict-mcp-config` with no `--mcp-config`: no MCP server, also none of those attached to the account. They
  would put the owner's connector names in the request and change it from day to day.
- `--permission-prompts none`: nobody is asked; anything that would ask is denied *(help)*.
- Never `--bare`: it reads no login *(doc, headless)*. Never `--no-session-persistence`: the session could not be
  resumed *(help)*.
- A resumed session sends its recorded system prompt again, so the check's prefix is the priming's
  *(help: `--system-prompt-snapshot`, on by default; doc, prompt-caching)*.
- A session id is looked up first in the folder the session was started in *(doc, sessions)*: priming and check
  run in the same working folder.

**Reading it.** The `json` output is one result object *(doc, agent-sdk/typescript)*:

| Read | From |
|---|---|
| Input not from cache | `usage.input_tokens` |
| Cache read | `usage.cache_read_input_tokens` |
| Cache write | `usage.cache_creation_input_tokens` |
| Which lifetime was written | `usage.cache_creation.ephemeral_1h_input_tokens`, `.ephemeral_5m_input_tokens` |
| One model request | `num_turns` is 1 and `modelUsage` names one model |
| The model that answered | the key of `modelUsage` |
| A failure | `is_error`, `subtype`, the text in `result`; a non-zero exit |

`total = input + cache read + cache write`; `cached = cache read`. `usage` covers the main conversation of that
invocation only, so a resumed run reports the resumed turn, not the session's sum *(doc; open: confirmed by the
smoke run)*. `total_cost_usd` is the client's estimate, not a bill, and is not used.

**Input limit.**

- A prompt on stdin may be up to 10 MB *(doc, headless)*: about 1.6 million repetitions of `" hello"`, more than
  the window.
- Accepted: the request's `total`, which counts Claude Code's own system prompt and tools.
- Refused: Claude Code prints `Prompt is too long` *(doc, errors)*. Whether Anthropic's own sentence with the two
  counts (`prompt is too long: N tokens > M maximum`) reaches the output, stderr or `--debug-file` is *(open)*. If
  it does, the row has `context` as the proxy's row has; if not, the walk gives `input_accepted` and
  `input_refused`, the refused size converted from two accepted ones as `build_observed.py` already checks.
- Auto-compaction answers this error, but one exchange cannot be compacted *(doc, env-vars)*: a first message that
  is too long is refused, not cut.

**What Claude Code decides by itself.**

| Decision | What it is | Basis |
|---|---|---|
| Cache lifetime | The 1-hour lifetime for the main conversation on a subscription inside the plan's included usage, `-p` runs included; the 5-minute lifetime once the subscriber is in overage. A person can choose: `CLAUDE_CODE_PROMPT_CACHE_TTL=5m\|1h`, the `promptCacheTtl` setting, `FORCE_PROMPT_CACHING_5M`, `ENABLE_PROMPT_CACHING_1H` | doc, prompt-caching |
| What is cached | System prompt and tools, then project context, then the conversation. Where the markers sit is not documented | doc |
| The shared prefix | Its own system prompt and tool list in front of every conversation; the cache is "effectively scoped to one machine and directory" | doc |
| Window | The 1M window by default on Haiku 5.5, Sonnet 5 and later, Opus 4.7 and later, Fable | doc, model-config |
| Retries | Up to 10, with backoff, before it reports a failure. The harness does not see them | doc, errors |

**What the measurement means.** How long the cache of a paused Claude Code session lives on the login, with the
lifetime Claude Code asked for. The run records which lifetime was written, from the replies. A default run
therefore measures the 1-hour lifetime while the account is inside its included usage; in overage the same command
measures the 5-minute one. A run whose replies change lifetime on the way ends (`tier-changed`) and is excluded. It
does not say what a request that asks for nothing gets on the login: no own client sends such a request.

### 1.2 `codex-subscription`: Codex CLI (`codex-cli`, exists)

**Driving it** (as `probe.py` does, plus the state folder of section 2):

```bash
codex exec --json --skip-git-repo-check -m <id> -c model_reasoning_effort="low" -s read-only - < prime.txt
codex exec resume <thread-id> --json --skip-git-repo-check -m <id> -c model_reasoning_effort="low" "<short message>"
```

**Reading it.** `thread.started` gives the thread id; `turn.completed` gives `usage`: `input_tokens`,
`cached_input_tokens`, `cache_write_input_tokens`, `output_tokens`, `reasoning_output_tokens`. The figures are the
thread's running total, also after a resume *(src: `exec/src/event_processor_with_jsonl_output.rs`,
`core/src/session/mod.rs` at `rust-v0.170.0`; run: H1)*, so a check is the difference to its priming, as
`probe.py` already computes. One model request: the turn's events hold no tool item (`item.*` of a command or tool
call). A failure is `{"type":"error"}` followed by `turn.failed`; a plan's limit reads "You've hit your usage
limit" *(src: `protocol/src/error.rs`)*.

**Input limit: not through this client.** Codex refuses a single message above 1,048,576 characters before sending
it *(src: `MAX_USER_INPUT_TEXT_CHARS`)*. That is about 175,000 tokens of `" hello"`, where the login refused at
about 922,000 tokens through the proxy. A longer input can only be built over several turns, and then Codex's own
window and compaction (`model_context_window`, `model_auto_compact_token_limit`) decide, not the provider. The
route's input limit stays measured through the proxy.

**What Codex decides by itself** *(src, none of it in OpenAI's documentation)*: the ChatGPT backend as endpoint;
`store: false`; a `prompt_cache_key` that is the session id and stays the same across a resume; no retention asked
in `codex exec`, so the server's default applies; its own window per model and its own compaction.

**What the measurement means.** How long the cache of a paused Codex session lives on the plan, on the server's
default retention.

### 1.3 `devin`: Devin CLI (`devin-cli`, exists)

**Driving it** (as `probe.py` does, with one addition):

```bash
devin --process-model in-process --model <id>-<effort> --prompt-file prime.txt -p \
      --respect-workspace-trust false --export <file>
devin --process-model in-process -r <session-id> --prompt-file check.txt -p \
      --respect-workspace-trust false --export <file>
```

`--process-model in-process` is new. The default may serve a run from a background daemon that other `devin`
commands share *(help)*, and Devin has "a background cache-refresh task" for long-running tasks *(doc, changelog
3000.6.14)*. A sample must be a process that ends, so that nothing can touch its cache between priming and check.
Which process model the 12 existing `devin-cli` runs used was not recorded.

**Reading it.** `-p` has no JSON output; the export is the record: the last step with `metrics` gives
`prompt_tokens` (cached and not), `cached_tokens`, and `extra.cache_creation_input_tokens` *(run: D1c; the export
is the ATIF format, doc)*. One model request: the turn added exactly one step with `metrics`.

**Input limit.** `--prompt-file` carries the input. What Devin prints for an input that is too long is *(open)*.

**What Devin decides by itself.** Devin's service chooses the upstream and how it is asked to cache, per model; a
user sets nothing. The reasoning level is part of the model id (`claude-opus-5-5-low`). For some models the CLI
reported no cached token in any reply, also where the same account and model showed hits through the proxy the
same day (*run*: H9 against H10, GPT-6.1 Terra; `devin-harness-2026-11-08/run.sh` names GPT-6.1 Sol, GPT-6 Astra
and Muse Wonder). Whether Devin does not cache there or does not report it cannot be told from the client.

**What the measurement means.** What the Devin CLI reports for a paused session. Where it reports nothing at all,
it measured nothing (decision 1 of section 6).

### 1.4 `meta-subscription`: Muse Code (`muse-code`, exists)

**Driving it** (as `probe.py` does):

```bash
muse exec --json --model <id> --reasoning-effort low --session-id <uuid> --prompt-file prime.txt
muse exec --json --model <id> --reasoning-effort low --session-id <uuid> "<short message>"
```

**Reading it.** The `run.usage` line: `calls`, and per model `input_tokens`, `cached_tokens` *(run: H5)*. It
"counts every model call of the run", and when Muse Code cannot count a run it leaves the line out *(doc,
changelog)*: no line is no reading, never zero. One model request: `calls` is 1. Muse Code reports no cache write.

**Input limit.** `--prompt-file`. Muse Code's changelog names a `contextOverflow` failure; its output is *(open)*.

**What Muse Code decides by itself.** The credential order: `META_API_KEY`, then a stored key, then a browser
login *(doc, auth)*. The reasoning level (default high). Its compaction thresholds *(help)*. Whether it asks Meta
for a retention is not documented and not visible in its output. On 2026-11-07 it cached its own system prompt and
never the conversation *(run: H5, version not recorded)*.

**What the measurement means.** What a Muse Code session gets. H5 again on the ladder shows whether 1.4.24 still
does not cache the conversation; if so, the own-client value of the route is 0 (decision 2 of section 6).

### 1.5 `antigravity`: something scriptable exists

`agy`, Google's Antigravity CLI, is installed and has a print mode *(help)*:

```bash
agy -p --output-format json --model <id> --effort low < prime.txt
agy -p --output-format json --conversation <conversation-id> "<short message>"
```

The `json` object carries `conversation_id`, `status`, `response` and `usage` with `input_tokens`,
`output_tokens`, `thinking_tokens`, `cache_read_tokens`, `total_tokens` *(doc, cli/headless)*. So cache reads can
be read; there is no cache-write figure. Proposed client id: `antigravity-cli`.

Three things are *(open)*, and Antigravity moves to its own client only when the smoke run settles all three:

1. Whether `usage` after `--conversation` in a new process is that turn's or the conversation's sum (the
   documentation says "cumulative over the session"). If it is a sum, it is handled as Codex's is.
2. Whether a run can be kept out of the owner's history. The login is in the system keyring and the settings in a
   fixed folder *(doc, install, settings)*; no documented flag or variable moves them. `agy acp` has `--gemini-dir`
   and `--app-data-dir` *(help)*; whether print mode takes them is not known. Without them, every sample is a
   conversation in the owner's own list.
3. What a refusal looks like (quota, and an input that is too long).

Google's FAQ says headless mode "is intended for direct scripting and CI workflows", and that wrapping `agy` in
third-party agents or applications, and third-party software reaching Antigravity, are not supported on consumer
plans *(doc, faq)*. Which of the two a measuring script is, is the owner's reading (decision 6). Until the three
points are settled, `antigravity` stays on the proxy.

### 1.6 Summary

| Route | Own client | Cache read from | Cache write | Input limit through it |
|---|---|---|---|---|
| `claude-subscription` | `claude-code` (new) | `usage.cache_read_input_tokens` | yes, with its lifetime | yes; the wording of the refusal is open |
| `codex-subscription` | `codex-cli` | `cached_input_tokens`, less the priming's | `cache_write_input_tokens` | no: the client caps a message |
| `devin` | `devin-cli` | `metrics.cached_tokens` of the export | `extra.cache_creation_input_tokens` | open |
| `meta-subscription` | `muse-code` | `run.usage`, `cached_tokens` | not reported | open |
| `antigravity` | `antigravity-cli` (if the smoke run passes) | `usage.cache_read_tokens` | not reported | open |

## 2. The owner's setup

### 2.1 Running a client apart from everyday use

Four things keep a run out of the owner's settings, history and projects.

**A state folder per client, used for nothing else.** One folder outside the repository and outside the client's
default folder, named by `GROUNDTRUTH_CLIENT_HOME`; each client gets a subfolder. The client is pointed at it by
its own variable, and logged in there once by the owner. `probe.py` refuses to start when the folder is missing,
is not logged in, or is the client's default folder.

| Client | Pointed at the folder by | Login in that folder | Never |
|---|---|---|---|
| Claude Code | `CLAUDE_CONFIG_DIR`: settings, session history and plugins live under it *(doc, env-vars, authentication)* | `claude auth login` with the variable set and the throwaway home, once. Its secure storage is "Keychain, with a plaintext fallback" (2.1.330 binary): under the throwaway home `security` finds no Keychain (exit 37, no default keychain; 44 on a read), a non-transient failure, so the login is written to `<state folder>/.credentials.json`. The everyday login, a Keychain entry, is not reachable | `ANTHROPIC_API_KEY` or `ANTHROPIC_AUTH_TOKEN` in the environment: with `-p` a key is always used when present, and the run would be on the API, not the login *(doc)* |
| Codex CLI | `CODEX_HOME`: `config.toml`, `auth.json`, `sessions/`, `history.jsonl`, logs *(doc)* | `codex login -c cli_auth_credentials_store="file"` with the variable set, once, so the login is a file in that folder | Copying the everyday `auth.json`: both copies would refresh one token, and the copy that loses is logged out ("refresh token was already used") *(doc, auth; src)* |
| Devin CLI | `XDG_CONFIG_HOME`, `XDG_DATA_HOME`, `DEVIN_SESSIONS_DIR` *(doc)*; `--process-model in-process` | `devin auth login` with them set and the throwaway home, once. The token is a file, `credentials.toml` *(binary)*; wherever the build resolves it, it is under `<client-home>` | `devin auth logout` in any environment, until it is known that the two logins are apart |
| Muse Code | `XDG_CONFIG_HOME` (the credential file is `$XDG_CONFIG_HOME/muse/auth.json`, *launcher script*); `XDG_DATA_HOME` for the sessions *(open)*; `MUSE_NO_AUTO_UPDATE=1` | None: the subscription key in `META_API_KEY`, read from a Keychain item of groundtruth's into the client's environment, as `key.py` does for OpenRouter | The key on a command line or in a file |
| Antigravity CLI | Not established (1.5, point 2) | The everyday login: there is one keyring entry | — |

The alternative for Claude Code is a token from `claude setup-token` in `CLAUDE_CODE_OAUTH_TOKEN`. It works with
any folder, but it is a secret that lives for a year and has to be stored and passed by groundtruth. A login in
the state folder needs neither.

**A working folder with nothing in it.** A new folder under the system's temporary folder per run, outside every
repository, kept until the last check (a session is resumed from the folder it was started in). Not under
`results/` as today: a client reads `CLAUDE.md` or `AGENTS.md` from the folders above its working folder, and a
checkout of this repository can hold either.

**A throwaway home folder.** Every process of a client (each run, the login checks, the owner's login, `pi install`)
gets `HOME=<client-home>/home/<client>`, made and checked like the state folder (under `<client-home>`, no link out,
no checkout, no everyday folder). What each client finds through `HOME` (2.1.330, 0.171.0, 3000.14.30821, 1.4.25,
pi 1.6.0; binary strings and `--version`/`--help` under a throwaway home with writes to the real one denied):

| Client | Through `HOME` | Needs the real `HOME` |
|---|---|---|
| Claude Code (Bun) | its default folder `~/.claude` when `CLAUDE_CONFIG_DIR` is unset; the Keychain (through `security`, which finds the login keychain from `HOME`) | No: the login goes to `.credentials.json` in its folder |
| Codex CLI (Rust) | `~/.codex` when `CODEX_HOME` is unset (shown: `codex --help` without it writes `~/.codex/tmp/` under the throwaway home); the keyring only with another credential store than `file` | No |
| Devin CLI (Rust) | `~/.devin` (plans, hooks, worker cache, cloud setup: named so in its strings) whatever the XDG variables say; the other agents' folders (`.claude`, `.codex`, `.agents`) it reads rules and skills from | No |
| Muse Code (launcher + binary) | `~/.config/muse/auth.json` only without `XDG_CONFIG_HOME` (launcher); `.muse` folders (strings, not traced to `HOME`); the other agents' personal rules and skills; the Keychain for a stored login (the run's key comes in `META_API_KEY`, the lane that wins) | No |
| pi (Node) | `~/.pi/agent` when `PI_CODING_AGENT_DIR` is unset (shown: `pi --help` without it writes `~/.pi/agent/auth.json` under the throwaway home); `~/.agents` skills. pi-provimux finds pi's modules from `process.argv[1]` first, `HOME` only as a fallback | No |

So no client keeps the real `HOME`. A side effect: Devin and Muse no longer read the owner's personal rules and skills
from his home folder into a run's prompt.

**A clean environment.** The client's process gets a short allow-list (`PATH`, `USER`, `LANG`, `TERM`, `TMPDIR`),
its throwaway `HOME`, the variables of the table, and what the run itself sets. So no API key, base URL, proxy setting or
cache switch of the owner's shell reaches it. Updates are held for the run (`DISABLE_AUTOUPDATER=1` for Claude
Code, `MUSE_NO_AUTO_UPDATE=1`), so a run has one client version; nothing else is switched off, because a client
with its feature flags off may no longer ask for what it asks a user for.

**A report, not a stop.** The owner uses his computer and his tools during the night (pi's sessions append
`cache_warm` lines under `~/.pi`, Codex refreshes `~/.codex/auth.json`, his agents run Claude Code and Codex), so
his everyday folders change whatever the night does. `night.py untouched --save` records them before the logins
(path, size and modification time to their depth, `stat` only; the Keychain's item names, never a secret), and
`untouched --report` (by hand, in the morning) lists what changed, folder by folder, for a person to judge; a file
removed while the walk passes it is named, not an error. It sees additions, changes and removals, never a read. A
Claude Code Keychain item added or changed would be the sign that the isolation failed.

**A write boundary.** On macOS every client process runs under `sandbox-exec` with a profile that denies file writes
under the owner's real home folder except in the client's state folder, its throwaway home and its temporary folder
(`clients.confine`). All four clients answer `--version` and `--help` under it (2.1.330, 0.171.0, 3000.14.30821,
1.4.25; Codex's `login --help` too). It covers files only: reads, and requests to macOS services such as the
Keychain's, are outside it. A login run is untested under it (no login was made for this branch).

**What cannot be kept apart.** The quota is the account's: a run and the owner's own work draw on the same
allowance. A vendor that keeps sessions on its side (Devin) may list them in the account. Claude Code changes
lifetime when the account enters overage, so a Claude run is started when the plan's meter is low.

### 2.2 What it costs

A subscription's allowance is not published in tokens, so the cost is given as what the client will report.
Measured on the earlier runs *(run: H1, H3, H5, H7, D1c, D6c, D9c)*: a request carries 16,000 to 36,000 input
tokens (the client's own prompt, plus 7,000 to 11,000 of the sample's block), a priming takes 2 to 13 seconds, and
none of the seven logs holds a retry or a failure.

| Run | Samples | Requests | Input tokens, about | Of them read from cache while warm |
|---|---|---|---|---|
| Control only (the control missed) | 1 | 3 | 0.1 million | — |
| 5-minute lifetime (to 15 min) | 16 | 33 | 1.0 million | about two thirds |
| `std` with 65 min (to 2 h) | 46 | 93 | 2.7 million | about two thirds |
| `long` (to 12 h) | 52 | 105 | 3.0 million | about two thirds |

Output: a few tokens per request, plus reasoning at the lowest level. Claude Code's request size is not known
before its smoke run; the table assumes Codex's.

| Login | Cache runs (section 4) | Requests | Input tokens, at most |
|---|---|---|---|
| `claude-subscription` | 4 `std` + 4 short | 500 | 15 million |
| `codex-subscription` | 6 `long` | 630 | 18 million |
| `devin` | 14 `std` + 4 `long`, fewer where the control misses | 1,720 | 50 million |
| `meta-subscription` | 3 `std`, or 3 controls | 280 | 8 million |
| `antigravity` | 1 `std` | 93 | 2.7 million |

**Limits walks cost more per request.** A refused request is free. An accepted one just under a window of a
million tokens is a million tokens of the allowance: one per model where the refusal names the window, two or three
where it does not. Claude: 4 models, 4 to 12 million tokens. Devin: 12 models, 12 to 36 million.

**OpenRouter, in dollars**, by the ledger of `results/openrouter-2026-11-18` (a `std` run of 65 to 86 requests at
about 2,500 prompt tokens):

| Entry | Compared with | About |
|---|---|---|
| `openai/gpt-6-astra` | `openai/gpt-6.2-astra` $1.23, `~openai/gpt-astra-latest` $1.21 | $1.25 |
| `openai/gpt-6-luna` | `~openai/gpt-luna-latest` $0.02, `openai/gpt-6-luna-pro` $0.04 | $0.05 |
| `meta/muse-spark-1.3` | `meta/muse-spark-open` $0.20, `meta/muse-ember` $0.02 | $0.20 |
| `deepseek/deepseek-v4.1-flash` | `deepseek/deepseek-v4.1-flash-1017` $0.01 | $0.02 |
| `z-ai/glm-5.3-flash` | `~z-ai/glm-flash-latest` $0.02, `z-ai/glm-5.3-flashx` $0.06 | $0.05 |
| A second run at about 8,000 tokens, where the first control reads nothing | three times the first: DeepSeek, GLM and Muse Spark together | up to $0.80 |
| 9 window requests | refused by OpenRouter itself, not billed | $0 |

About $1.60, with those second runs about $2.40. A second Astra run would be about $3.75 and is not started without
a go; its control hit at 2,500 tokens through the proxy. A key made for the campaign with a limit of $5 and a stop
at $4, the prices read again before each run, as on 18 November.

### 2.3 How long it takes

| Part | Wall time | Note |
|---|---|---|
| Smoke, per client | 5 minutes | baseline, one sample checked at 30 seconds, one refused request |
| OpenRouter, 5 cache runs together | 2 h 15 min | another 2 h 15 min where a second run at 8,000 tokens is owed |
| OpenRouter, 9 window requests | 10 minutes | |
| Claude Code, 4 runs together | 2 h 10 min | then the 4 short runs, 25 minutes |
| Codex CLI, 6 runs together | 12 h 10 min | |
| Devin CLI, 19 runs together | 2 h 30 min to 3 h 05 for 16, 12 h 46 min for 3 | started 20 seconds apart, as on 8 November, and paced at 24 requests a minute (rule 6; `--dry-run` plans it) |
| Muse Code, 3 runs together | 2 h 10 min | minutes if the control misses |
| Limits walks | 10 to 20 minutes per model, one after the other per login | a request of a million tokens takes minutes |

The logins are different accounts and run side by side: the cache runs are one night of about 12 and a half
hours, with the computer kept awake (`caffeinate`) and on the network. A check that runs more than
`age × 1.1 + 90 s` after its priming is counted as late and left out, so a sleeping computer loses checks, not
truth.

## 3. `observed.json`

The file says which kind each client and each route is. providers.dev applies the rule; groundtruth does not
choose a winner. Everything is added; no existing key changes its type or its meaning, and `schema` stays 1.
providers.dev's import reads `clients` as a map of texts (client id to label) and refuses the file when a value is
anything else, while it tolerates a key it does not know. So `clients` stays as it is and the kinds are a map of
their own, with the three kind names the site's design uses.

**Two new top-level keys.**

```json
"client_kinds": {
  "direct": "direct",
  "claude-code": "own_client", "codex-cli": "own_client", "devin-cli": "own_client",
  "muse-code": "own_client", "antigravity-cli": "own_client",
  "cliproxyapi": "proxy", "pi+cliproxyapi": "proxy"
},
"route_kinds": {
  "anthropic-api": "api_key", "openai-api": "api_key", "openrouter": "api_key",
  "claude-subscription": "login", "codex-subscription": "login", "devin": "login",
  "meta-subscription": "login", "antigravity": "login"
}
```

- `client_kinds`: every key of `clients`, each `direct` (plain requests to the route's own address), `own_client`
  (a client the route's vendor ships, driven as its user drives it) or `proxy` (anything that goes through a proxy,
  with or without an agent in front; Provimux will be one).
- `route_kinds`: every key of `routes`, each `api_key` or `login`.
- `build_observed.py` refuses a client or a route without a kind, and an own client on a route that is not its
  vendor's: `claude-code` only on `claude-subscription`, `codex-cli` on `codex-subscription`, `devin-cli` on
  `devin`, `muse-code` on `meta-subscription`, `antigravity-cli` on `antigravity`.

**The rule, as providers.dev applies it.** Rank the kinds: `direct` 0, `own_client` 1, `proxy` 2.

1. On a route of kind `api_key`, only runs and rows of kind `direct` count.
2. On a route of kind `login`, for one value (a cache lifetime of one model in one retention profile; the input
   window of one model), the runs or rows that count are those of the lowest rank present among the ones the site
   counts today. Between clients of the same kind, today's rule stands (the lowest decides).
3. Every other run and row stays in the file and is shown as measured.

**New keys on a cache entry made by `harness/probe.py`** (computed from the raw file, absent on older runs):

- No client version: what `<client> --version` printed is the client's own text, so it goes only to the run's
  console log (mode 600) and its private record (`<client-home>/private-runs/`), for the night's audit; a README may
  name the version number, written by hand.
- `written_ttl`, only where the client reports the lifetime of its cache writes (Claude Code): `"1h"` or `"5m"`.
  A run whose writes are mixed is refused.

`options` keep their meaning: what the person running the client asked for. A default Claude Code run has no
`ttl` there, as the proxy's runs without a ttl have none, though the client asked for one hour by itself;
`written_ttl` says so. A run made with `CLAUDE_CODE_PROMPT_CACHE_TTL=5m` has `"ttl": "5m"`, and
`build_observed.py` refuses it when `written_ttl` says otherwise.

**Two new `known` rows** for `claude-subscription` / `claude-code` / `*`, from Anthropic's documentation
(https://code.claude.com/docs/en/prompt-caching): `ttl_s` 3600 inside the plan's included usage, and `ttl_s` 300
with `"when": {"usage": "overage"}`.

**Three rules for what may become an entry.**

- **Cache, own client:** a run in which no reply reported a cached token (baseline, primings and checks all 0) is
  not a run: it goes in `excluded` with that reason (decision 1). `build_observed.py` refuses it in `runs`.
- **Cache, own client:** a run needs the state folder and the empty working folder of section 2; the raw file's
  `start` event records both, and `build_observed.py` refuses an own-client run dated after this design without
  them.
- **Limits, own client:** a row needs `context` or `input_refused`, from the provider's own answer. A walk that
  ended at a cap of the client's (Codex's message size) gives no row: an `input_accepted` alone would stand in
  front of the proxy's refusal by rule 2 and publish less than the login accepts.

**providers.dev's side, not part of this repository:** read the two maps, apply the rule, and name the two new
clients in its labels file (an undescribed client is published as "Another client").

## 4. The run plan

Folders: `results/own-clients-<date>/` and `results/openrouter-direct-<date>/`, each with its README, its `run.sh`
and its raw files. Every run: 3 samples per age, the control first, the lowest reasoning level the model has.

### 4.1 OpenRouter, directly (first: it needs no login)

Method of `results/openrouter-2026-11-18`: the TypeScript probe straight to `https://openrouter.ai/api/v1`,
Responses format, a `prompt_cache_key` per sample, about 2,500 prompt tokens of the default filler, 16 output
tokens, nothing asked about caching, `std`, `--stop-on-refusal`, `--usage-log`, no upstream pinned, each reply's
upstream looked up afterwards, the ledger and the money stop. Each model is checked as still offered just before
its run; one that is gone is written down and not run.

| Id | Model | Today, through the proxy |
|---|---|---|
| OR1 | `openai/gpt-6-astra` | G8: warm through 30 min, cold at 40 |
| OR2 | `openai/gpt-6-luna` | G9: warm through 30 min, cold at 40 |
| OR3 | `meta/muse-spark-1.3` | S1: misses from 2.5 min, last hit at 15 |
| OR4 | `deepseek/deepseek-v4.1-flash` | F6: every check warm through 2.5 min, hits to 60; about 6,000 prompt tokens |
| OR5 | `z-ai/glm-5.3-flash` | F4: last hit at 30 min, cold at 40; about 6,000 prompt tokens |
| OR1b – OR5b | the same at about 8,000 prompt tokens | only where the first run's control read no cached token; OR1b only with a go (2.2) |

Windows, one Chat Completions request each of `" hello"` × 1,200,000 with 16 output tokens and `transforms: []`
(`window.py` of that folder); the refusal names the endpoint's window, nothing near a limit is accepted:

| Id | Model | Id | Model |
|---|---|---|---|
| OW1 | `anthropic/claude-haiku-5.5` | OW6 | `meta/muse-wonder` |
| OW2 | `anthropic/claude-opus-5.5` | OW7 | `moonshotai/kimi-k3.1-pro` |
| OW3 | `anthropic/claude-sonnet-5.5` | OW8 | `openai/gpt-6.1-sol` |
| OW4 | `deepseek/deepseek-v4.1-flash` | OW9 | `openai/gpt-6.1-terra` |
| OW5 | `google/gemini-4-argon` | | |

Cheapest first. A request that is answered instead of refused ends the list: it was billed for over a million
tokens, and the next one waits for a decision.

### 4.2 The smoke runs (before any login's batch)

*First night: the baseline and the control only, no request above the window (the limits walks are out).*

One model per client: the baseline, one sample checked at 30 seconds, one request far above the window. Three
answered requests and one refused. They settle every *(open)* of section 1 and give the test fixtures of section
5. They are published in the folder and listed in `excluded`.

| Id | Client | Model |
|---|---|---|
| S1 | Claude Code | `claude-haiku-5-5` |
| S2 | Codex CLI | `gpt-6-luna` |
| S3 | Devin CLI | `claude-haiku-5-5-low`, then `gpt-6-1-terra-low` (does it still report nothing?) |
| S4 | Muse Code | `muse-spark-1.3` |
| S5 | Antigravity CLI | `gemini-3.8-flash-high` |

### 4.3 Cache lifetimes through the own clients

`std+65` is `--ages 10m,15m,20m,25m,30m,40m,50m,60m,65m,75m,90m,120m` on top of the ladder's start: `std` and the
65-minute age the proxy's Claude runs have.

| Id | Route | Client | Model | Ages | Setting |
|---|---|---|---|---|---|
| CC1 | `claude-subscription` | `claude-code` | `claude-fable-5-2` | `std+65` | default; plain numbered filler |
| CC2 | | | `claude-opus-5-5` | `std+65` | as CC1 |
| CC3 | | | `claude-sonnet-5-5` | `std+65` | as CC1 |
| CC4 | | | `claude-haiku-5-5` | `std+65` | as CC1 (this model refused the random filler on the login) |
| CC5 – CC8 | | | the same four | to 15 min | `CLAUDE_CODE_PROMPT_CACHE_TTL=5m` |
| CX1 | `codex-subscription` | `codex-cli` | `gpt-6.2-sol` | `long` | default |
| CX2 | | | `gpt-6.2-astra` | `long` | |
| CX3 | | | `gpt-6.1-sol` | `long` | |
| CX4 | | | `gpt-6.1-terra` | `long` | |
| CX5 | | | `gpt-6-astra` | `long` | |
| CX6 | | | `gpt-6-luna` | `long` | |
| DV1 – DV3 | `devin` | `devin-cli` | `claude-opus-5-5`, `claude-sonnet-5-5`, `claude-haiku-5-5` | `std` | default |
| DV4 – DV7 | | | `gpt-6-1-sol`, `gpt-6-1-terra`, `gpt-6-astra`, `gpt-6-luna` | `std` | |
| DV8 – DV11 | | | `deepseek-v4-1-flash-1017`, `glm-5-3`, `kimi-k3-1-pro`, `nemotron-3-5-super` | `long` | warm at 2 h in November's runs |
| DV12 – DV18 | | | `deepseek-v4-pro`, `gemini-4-argon`, `grok-4-7`, `kimi-k3`, `muse-wonder-1-0`, `swe-2`, `gemini-4-neon` | `std` | DV12 at `high` (`deepseek-v4-pro-high`): the model has no `low` on Devin (rule 7) |
| MC1 – MC3 | `meta-subscription` | `muse-code` | `muse-wonder-1.0`, `muse-ember-1.0`, `muse-spark-1.3` | `std` | default |
| AG1 | `antigravity` | `antigravity-cli` | `gemini-3.8-flash-high` | `std` | only if S5 settles 1.5 |

A model the client no longer offers is written down and not run. The 11 Devin models that have a `devin-cli` run
are measured again: two samples per age, no 2.5-minute age and an unrecorded process model are not what the rule
should rest on.

### 4.4 Input limits through the own clients (after 4.3, and after decision 3)

*Not in the first night (the chief's decision of 2026-11-22): `harness/client_limits.py` is not yet trusted.*

Per model: one request far above the window (free), and, where the provider's answer names the window, one
accepted request about 1,000 tokens under it. Where it names nothing: one small accepted request, one accepted
under the proxy's `input_accepted`, one refused above the proxy's `input_refused`.

| Id | Client | Models |
|---|---|---|
| CL1 – CL4 | `claude-code` | the four of CC1 – CC4 |
| DL1 – DL12 | `devin-cli` | the 12 with a proxy row, if S3 shows a provider's refusal |
| ML1 – ML3 | `muse-code` | the three of MC1 – MC3, if S4 shows a provider's refusal |
| — | `codex-cli` | none (1.2) |

## 5. What a worker builds

Steps 1 to 5 send nothing and are tested without a network. Step 6 is the first that reaches a login.

1. **`harness/probe.py`: the adapters.** Each client is one class with the same five parts, so the loop knows no
   client by name:

   ```python
   class Client:                      # Claude, Codex, Devin, Muse, Agy (and Pi, unchanged)
       harness: str                   # the --harness value
       client_id: str                 # the id in observed.json
       cumulative: bool               # the client reports a session's running total
       def environment(self, home: str) -> dict[str, str]: ...   # the allow-list and the folder's variables
       def version(self) -> str: ...                              # `<client> --version`
       def command(self, prompt_file: str, resume: str | None) -> list[str]: ...
       def parse(self, stdout: str, stderr: str, code: int, files: dict[str, str]) -> Usage: ...
   # Usage: total, cached, write, calls, model, and write_5m / write_1h where the client reports them.
   # parse raises Refused(kind, text) for a quota or an input refusal, ClientError(text) for anything else.
   ```

   `parse` is a pure function of what the client printed. *Tests:* one recorded output per client and case (a
   priming, a warm check, a cold check, a two-request turn, a quota refusal, an input refusal) under
   `test/fixtures/clients/`, each parsed to the expected `Usage` or refusal. Until step 6 the fixtures are the
   shapes of section 1 and the usage lines of the existing raw files; step 6 replaces them with what the clients
   really printed, with the prompt, ids and any account detail taken out. *Tests:* each `command` is the argument
   list of section 1; each `environment` holds the folder's variables and none of `ANTHROPIC_API_KEY`,
   `ANTHROPIC_AUTH_TOKEN`, `OPENAI_API_KEY`, a base URL or a cache switch that the test put in its own
   environment.
2. **`harness/probe.py`: the loop.** `--client-home` (required for an own client; refused when it is missing or
   the client's default folder), the working folder under the temporary folder, the control first, no second try
   of a check, `check-invalid` for a turn of more than one request, `stop` events (`no-observable-cache`, `quota`,
   `tier-changed`), ages from the start of the priming, `--filler list`, and a `start` event that records
   `client` (never its version: console log and private record only), the command with `<prompt>` in the prompt's place, and `isolation`
   (`{"home": "dedicated", "HOME": "throwaway", "work": "temporary"}`; never a path). *Tests:* the loop against a fake client and a
   fake clock: a cache that lives 5 minutes gives warm, warm, cold in order; two controls that miss end the run after
   five requests; a failed check is not sent again; a quota refusal during priming ends the run and the primed
   samples are not checked; a two-request check is not counted; a late check is flagged.
3. **`harness/client_limits.py`** (new; `harness/limits.py` stays the plain-request walk). It walks an input size
   through a client, with the adapters of step 1, and writes the rows `build_observed.py` reads today (`kind`,
   `model`, `n`, `status`, `promptTokens`, `message`, `at`), plus `client` and the client's exit
   code (its version on the console only). `status` is 200 for an answered request; for a refused one it is the HTTP status the client printed, or
   the text `refused`. `--dry-run` prints the plan and sends nothing. *Tests:* the plan for a named window and
   for none; a refusal's window read by `limits.named_limit`; a client-side cap (Codex's message size) ends the
   walk with no refusal row.
4. **`scripts/build_observed.py`.** `CLIENT_KINDS`, `ROUTE_KINDS` and the own client of each login; `client_kinds`
   and `route_kinds` in the output; the clients `claude-code` and `antigravity-cli` and their `--harness` names;
   `written_ttl` (no client version for an own client); `check-invalid` rows ignored; the refusals of section 3. *Tests* in
   `test/test_build_observed.py`: every client and route has a kind; an own client on another vendor's route is
   refused; a run with no cached token in any reply is refused; `ttl` in the options against `written_ttl`; an
   own-client limits row with `input_accepted` alone is refused. Rebuilding `observed.json` at this step adds the
   two maps, the two client names and the two `known` rows; no run and no limits row changes.
5. **The scan and the texts.** `harness/scan_secrets.py`: a client's state folder and its session files are never
   committed (as pi's are not), and `META_API_KEY` and `CLAUDE_CODE_OAUTH_TOKEN` join the variables whose value is
   searched for. *Test:* a tree holding a session file of each client is refused. `README.md` ("Method",
   "observed.json", "Pitfalls") and `CONTRIBUTING.md` say what this document says, shorter.
6. **The smoke runs** (4.2), after the owner has logged the clients in. They answer every *(open)*; this document
   and the fixtures are corrected from what they show before any batch starts.
7. **The runs** of 4.1, 4.3 and 4.4, each folder with its README, its entries in `observed/manifest.json`
   (`excluded` included), and `observed.json` rebuilt.

## 6. Decisions that are the owner's

1. **A client that reports no cached token at all.** Devin's CLI did so for several models. Recommended: such a
   run is excluded as an instrument that showed nothing, and the proxy's value stands. Counting it would publish 0
   for a model whose cache the same account shows through the proxy.
2. **A client that reports cache reads and does not cache the conversation** (Muse Code on 7 November). By the
   rule its 0 is the login's value, in front of the proxy's hours. Recommended: accept it. It is what the vendor's
   client gives, and the proxy's line stays beside it. It should be decided knowingly, because it lowers published
   values.
3. **Input limits.** Recommended: an own client's row counts only where the provider refused (section 3), so
   Codex's limit stays the proxy's; and the walks of 4.4 are made for Claude Code now and for Devin and Muse Code
   only once their smoke runs show a provider's refusal, because every confirmation costs about a million tokens
   of the allowance.
4. **Claude Code's second lifetime** (CC5 – CC8). Recommended: yes. Twenty-five minutes, and it is what the same
   login gives in overage.
5. **The logins.** Three one-time logins by the owner, in the state folders (Claude Code, Codex, Devin), and the
   Muse subscription key and an OpenRouter key in the Keychain. Recommended over `claude setup-token`.
6. **Antigravity.** Recommended: run S5 only if its conversations can be kept out of the owner's list or the
   owner accepts them there; otherwise the route stays on the proxy. Google's FAQ calls the scripted print mode
   intended and third-party software on the login unsupported.
7. **When.** One night with the computer awake, at a time when the plans' meters are low. The Codex and Devin
   `long` runs can instead be `std` (2 h 10 min) with a second run for the ages past 2 hours.
