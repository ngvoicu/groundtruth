# Subscription logins through CLIProxyAPI, 2026-11-17: narrower input windows, and the cache lifetimes again

Requests through the owner's local CLIProxyAPI (a build of 8.0.75 with his patches, no plugin, no pools, no aliases),
on the plans of four logins: Codex (ChatGPT plan), Devin, Meta (Muse Code) and Antigravity. No money was spent; every
request counts against a plan. `ledger.md` has what each request or run used.

**Findings.**

- **The Codex login missed at 2.5 minutes and at some later ages** (LC1, LC3, LC4, plain probe, 3 samples per age):
  GPT-6.1 Sol and GPT-6 Astra hit 2 of 3 at 2.5 minutes, GPT-6 Luna 1 of 3; at 5 minutes all three hit 3 of 3. After
  that, ages where every check hit alternate with ages that miss some (Sol 0 of 3 at 1 h, then 2 of 3 at 90 minutes
  and 2 hours; Astra 3 of 3 at 75 and 90 minutes, 1 of 3 at 2 hours; Luna cold at 1 h and 75 minutes, where it
  stopped). On providers.dev the safe value of `openai-codex/gpt-6.1-sol` and `gpt-6-luna` goes from 5 minutes to 0,
  and of `gpt-6-astra` from 2 hours (G1, through pi) to 0. What that 0 means, and what it does not, is under
  section 2 (Codex).
- **Every window is narrower now, and nothing contradicts an earlier walk.** Codex login: GPT-6.1 Sol, GPT-6 Astra and
  GPT-6 Luna accept 921,500 tokens and refuse 922,300 (documented: 922,000). Devin: its GPT models the same 921,500 /
  922,300 (Devin lists 1,000,000), its Claude 5.5 models 999,500 / 1,000,300, DeepSeek V4.1 Flash, DeepSeek V4 Pro and
  Gemini 4 Argon 1,048,076 / 1,048,876 (Devin lists 1,048,576).
- **Devin refused for request rate** two minutes into its lifetime runs; no Devin lifetime was measured.
- **Claude Fable 5.2 on the Claude login** (added by the owner at about 15:40): the 1-hour cache, as its siblings: warm
  in every check to 1 h, cold at 65 and 75 minutes, with and without `ttl: "1h"`. Its window refusal names 1,000,000.
- **Antigravity refused for rate** (429 `RESOURCE_EXHAUSTED`) 40 s into the runs of its other models (also added at
  15:40); none of them was measured.

## How the requests reached one account

- **Codex login.** The GPT ids are served by the Codex login and, at a lower priority, by an OpenAI API key. Every
  Codex request here used a temporary alias on the Codex login only (`probe/gpt-6.1-sol`, `probe/gpt-6.1-terra`,
  `probe/gpt-6-astra`, `probe/gpt-6-luna`, set and removed through CLIProxyAPI's management API, as `harness/pool.py`
  does); no API key serves a `probe/…` name. During the window walk the login's request counter rose by exactly its
  3 accepted and 3 refused requests and the API key's stayed at 0; it was still 0 at 14:39 and, after the restart
  below, at the end.
- **Devin** (`devin/…` ids), **Meta** (`muse-…`) and **Antigravity** (`gemini-3.8-flash-high`) ids are each served by
  one login only. The Devin login's counter rose by exactly the walk's 10 accepted and 12 failed requests.
- **Builds.** The owner restarted the proxy twice while this folder was made, each time on a new build of his:
  `ngvoicu-local-e8d8d777` (the process of 2026-11-16 18:48:58) until 16:18:13 local, `ngvoicu-local-a64b6855` (the
  same plus his PR #7634) until 18:09:07, `ngvoicu-local-c52243ab` after that. The configuration was rewritten at
  15:58 (the Claude and OpenAI API keys got model lists). What each build served:
  - e8d8d777: every window request but GLM-5.3's second one; LC1 – LC4, LM1 – LM3 and LA1 up to their 90-minute checks
    (LC2, LC4, LM2 and LA1 entirely); the Devin runs LD1 – LD6.
  - a64b6855: the 2-hour checks of LC1, LC3, LM1 and LM3 (14:27 UTC); Fable's window request and LF1, LF2; LA2 – LA4;
    GLM-5.3's second window request.
  - c52243ab: nothing of this folder.
- **Who answered the four 2-hour checks after the first restart.** The aliases live in the login file and were still
  listed after the restart (`/v1/models` at 16:31 showed all four `probe/…` ids), and no API key lists a `probe/…`
  name, also after the configuration change. From the restart to 16:29:29 the Codex login's request counter rose by
  exactly 6 (the two-hour checks of LC1 and LC3, 3 each) and the OpenAI API key's stayed at 0; the Meta login's rose by
  exactly 6 (LM1 and LM3; `muse-…` ids have no other account). So the logins answered them, and each run is proven to
  its last age. The `X-CPA-AUTH-KIND` header of a64b6855 was not recorded by the probe.

## 1. Input windows (`window_walk.py`, `run-windows.sh`)

`"Reply with just OK." + " hello" × N`, a 16-token reply; Responses format with low effort on the Codex login (as
`../limits-2026-11-13`), Chat Completions on Devin (as `../limits-2026-11-16`). A refusal is free, so each model got one
request just over the round number the published gap suggests (+300 tokens), then one just under it (−500 tokens),
sized with the earlier walk's tokens per word and overhead. Both landed on the expected side for every model, so each
gap closed to 800 tokens with one accepted request (the caps were 3 on the Codex login and 2 on Devin). The round
number: OpenAI's documented maximum input of 922,000 for the GPT models on both routes, the listed 1,000,000 for
Devin's Claude models and the listed 1,048,576 for the others. Devin, cheapest model first (OpenRouter's input price).

| Route | Model | Before: accepted / refused | Over: N → tokens | Under: N → tokens counted | Now: accepted / refused |
|---|---|---|---|---|---|
| Codex login | `gpt-6.1-sol` | 915,011 / 922,511 | 922,289 → refused | 921,489 → 921,500 | **921,500 / 922,300** |
| Codex login | `gpt-6-astra` | 915,011 / 922,511 | 922,289 → refused | 921,489 → 921,500 | **921,500 / 922,300** |
| Codex login | `gpt-6-luna` | 915,011 / 922,511 | 922,289 → refused | 921,489 → 921,500 | **921,500 / 922,300** |
| Devin | `deepseek-v4-1-flash-1017` | 1,047,489 / 1,052,864 | 1,048,463 → refused | 1,047,663 → 1,048,076 | **1,048,076 / 1,048,876** |
| Devin | `glm-5-3` | 1,047,470 / 1,052,845 | 1,048,482 → refused | 1,047,682 → **502**, no count | unchanged (see below) |
| Devin | `gpt-6-luna` | 911,390 / 923,890 | 921,910 → refused | 921,110 → 921,500 | **921,500 / 922,300** |
| Devin | `claude-haiku-5-5` | 999,072 / 1,004,446 | 499,864 → refused | 499,464 → 999,500 | **999,500 / 1,000,300** |
| Devin | `deepseek-v4-pro` | 1,047,542 / 1,052,917 | 1,048,410 → refused | 1,047,610 → 1,048,076 | **1,048,076 / 1,048,876** |
| Devin | `gpt-6-1-terra` | 911,390 / 923,890 | 921,910 → refused | 921,110 → 921,500 | **921,500 / 922,300** |
| Devin | `gemini-4-argon` | 1,047,490 / 1,052,865 | 1,048,462 → refused | 1,047,662 → 1,048,076 | **1,048,076 / 1,048,876** |
| Devin | `gpt-6-1-sol` | 915,390 / 925,390 | 921,910 → refused | 921,110 → 921,500 | **921,500 / 922,300** |
| Devin | `claude-sonnet-5-5` | 999,072 / 1,004,446 | 499,864 → refused | 499,464 → 999,500 | **999,500 / 1,000,300** |
| Devin | `claude-opus-5-5` | 999,072 / 1,004,446 | 499,864 → refused | 499,464 → 999,500 | **999,500 / 1,000,300** |
| Devin | `gpt-6-astra` | 911,390 / 923,890 | 921,910 → refused | 921,110 → 921,500 | **921,500 / 922,300** |

**The refused sizes in tokens.** No refusal states a count (Codex: "Your input exceeds the context window of this
model"; Devin: "There is an issue with this request, please try a different model"), so a refused N is converted with
`tokens = per word × N + overhead` from the accepted request of the same model in the same file. Every accepted request
here has exactly the overhead the earlier walks found for that model (Codex 11; Devin GPT 390, Claude 572 at 2 tokens
per word, DeepSeek V4.1 Flash 413, DeepSeek V4 Pro 466, Gemini 4 Argon 414), whose two accepted sizes per model fixed
the tokens per word. The limits rows in `manifest-entries.json` say so in their notes.

**GLM-5.3** refused 1,048,876 tokens, then answered the request of 1,048,076 tokens with HTTP 502 "devin upstream
returned an empty completion (0 output tokens)" after 143 s: neither accepted nor refused. With the chief's go it was
sent once more at 17:57 (build a64b6855, Devin quiet): no answer, the connection was closed after 125 s (the row with
status null). Neither row says anything about the window: **GLM-5.3's window is still open**, its published bounds
stay, and the rows are not a limits entry. The
first version of `window_walk.py` ended the whole Devin walk at that answer; the models it had not reached were walked
by a second command (`run-windows.sh`, comment at the end), with the script changed to end only that model. Its row
stays as published: this walk has no accepted size of GLM-5.3 to convert the refusal with (with the overhead of
2026-11-16, 394, the refusal is 1,048,876 tokens).

Not walked, as asked: `swe-2`, `grok-4-7`, `kimi-k3`, `kimi-k3-1-pro`, `muse-wonder-1-0`, `nemotron-3-5-super`, and
GPT-6.1 Terra on the Codex login (its walk of 2026-11-08 already has 920,870 / 921,886).

## 2. Cache lifetimes (`run-lifetimes.sh`, `supervise.py`)

The plain probe, 0.3.1, through CLIProxyAPI: the Responses format with a per-sample `prompt_cache_key`, as every earlier
run of these routes, the standard schedule (2.5 minutes to 2 hours, stopping after two fully cold ages), 3 samples per
age, a control first, and `--stop-on-refusal` (new in 0.3.1: a quota or rate refusal ends the run instead of being
retried). One supervisor per login started that login's runs side by side, 15 s apart, and ended them all at the
login's first refusal. Gemini 4 Argon and Gemini 3.8 Flash used a 5,000-token prefix, as their earlier runs (D5, A3).
Every check ran on time (the latest one 119.5 s after its 20-minute age on LA1, inside the probe's allowance; none was
left out as late).

**The Meta runs carry the 24-hour retention.** The probe does not send `prompt_cache_retention`, but CLIProxyAPI's
payload rule for `muse-*` (in the configuration since 2026-11-10) adds `"24h"` to every request to the Meta login. So
these runs are entered with that option, beside the earlier 24-hour runs (`meta-24h-2026-11-10`, through pi), and not
as successors of the plain runs of 4 and 6 November, which were made before the rule.

"Safe" is what providers.dev derives: the oldest age through which every check hit, the control included, the lowest
over the published evaluations of the entry and profile (`site/design/safe-cache-lifetime.md`, sections 3 and 4).

| Run | Model | Control | Warm / checks per age (2.5, 5, 7.5, 10, 15, 20, 25, 30, 40, 50 min, 1 h, 75, 90 min, 2 h) | Warm through | First all cold | Entry today → with this run |
|---|---|---|---|---|---|---|
| LC1 | Codex `gpt-6.1-sol` | hit | 2, 3, 1, 2, 2, 2, 3, 3, 2, 2, 0, 1, 2, 2 | – | 1 h | 5 min → **0** |
| LC2 | Codex `gpt-6.1-terra` | hit | 1, 0, 0 (stopped) | – | 5 min | 0 → 0 |
| LC3 | Codex `gpt-6-astra` | hit | 2, 3, 2, 2, 3, 2, 3, 1, 2, 2, 1, 3, 3, 1 | – | – | 2 h → **0** |
| LC4 | Codex `gpt-6-luna` | hit | 1, 3, 1, 2, 3, 2, 3, 1, 2, 2, 0, 0 (stopped) | – | 1 h | 5 min → **0** |
| LM1 | Meta `muse-ember-1.0` (24h) | hit | 3 at every age | 2 h | – | long 4 h; published with its continuation ML1 |
| LM2 | Meta `muse-spark-1.3` (24h) | hit | 3, 3, 3, 3, 2, 3, 3, 0, 0 (stopped) | 10 min | 30 min | long 5 min → 5 min |
| LM3 | Meta `muse-wonder-1.0` (24h) | hit | 3 at every age | 2 h | – | long 4 h; published with its continuation ML3 |
| LA1 | Antigravity `gemini-3.8-flash-high` | hit | 3, 2, 1, 0, 1, 0, 0 (stopped) | 2.5 min | 10 min | 2.5 min → 2.5 min |
| LD1 – LD8 | Devin, eight models | | rate refusal: no check (below) | | | unchanged |

- **Codex.** Each of LC1 to LC4 is the newest plain run of its model on this route, so it replaces X1 and X2b
  (`cpa-codex-long-2026-11-06`) as the published plain run; X1's checks to 12 hours stay in the file but are no
  longer shown. The safe values drop because of misses at 2.5 minutes, not because the runs are shorter. Whether a
  route that hits 2 of 3 at 2 hours but misses 1 of 3 at 2.5 minutes is "0" is the site's rule (a miss ends the safe
  value).

  **What the 0 is.** It means that there is no tested age through which every check hit; it does not mean that this
  route does not cache (at 5 minutes all three hit 3 of 3, and most checks hit). The earlier runs of Astra and Luna on
  this route (G1, G2) were made by another client (pi, low reasoning, larger prompts) and started at 5 minutes, so
  LC3 and LC4 are a first look at 2.5 minutes with plain requests. Of Sol's, C1 (`cpa-8.0.53`, 2026-11-04, the plain
  probe with a cache key) also checked from 2.5 minutes, and missed at 5 and 7.5 minutes (2 and 1 of 3); X1 started
  at 5 minutes; H1 and H2 were made by coding tools with low reasoning and larger prompts. None of this is a
  comparison that shows a change. The window walk sent three requests of 921,500 tokens to the same login one to two minutes
  before the priming, and the owner's own sessions use the login, so an effect of load at priming is not excluded
  (every sample, the late ones too, was primed in those first minutes). The missing `session_id` in the request record
  is not the cause: CLIProxyAPI copies the request's `prompt_cache_key` into the upstream session id. Runs that continue
  LC1, LC3 and LC4 were started on 2026-11-17 (branch `campaign/logins-long`, CL1, CL3, CL4), primed about four hours
  after these, with no window request before them; Sol and Astra missed again. They will be published together with
  these runs.
- **Meta Ember and Wonder** are completed runs, warm in all 42 checks each through 2 hours, which end there because the
  standard schedule ends there. Runs that continue them at 4, 8, 12 and 24 hours were started on 2026-11-17 (branch
  `campaign/logins-long`, ML1 and ML3). Each pair is published together, as one evaluation, when the continuing run
  has ended, whatever it shows; until then LM1 and LM3 are under `excluded` with that reason, and their files are
  here. The published long lifetime of 4 hours is that of `meta-24h-2026-11-10` (through pi).
- **Antigravity.** Google answered `MODEL_CAPACITY_EXHAUSTED` (HTTP 503, "No capacity available for model … on the
  server") to many requests between 12:27 and 12:59 UTC, which CLIProxyAPI turned into short pauses of the model; the
  probe retried them as transient errors (71 retries in all). That is the server's capacity, not the account's quota.
  The priming took 12 minutes, and the 15 samples overdue by then were primed again, so each was checked at its age.
  Same safe value as A3 (2.5 minutes).

### Devin: a rate refusal, no lifetime

The eight Devin runs (`claude-opus-5-5`, `deepseek-v4-pro`, `gemini-4-argon`, `glm-5-3`, `gpt-6-1-sol`, `grok-4-7`,
`kimi-k3`, `swe-2`) started at 14:37, 15 s apart, each priming 2 samples at a time. Within a minute Devin answered
`429 resource_exhausted: Reached request rate limit. Please switch to a different model or contact support. Your limit
will reset in 14 seconds`: LD1 (Opus), LD3 (Argon), LD4 (GLM-5.3) while priming, LD5 (GPT-6.1 Sol) at its first
request. Each probe ended at its refusal. The supervisor of that moment watched the logs only after it had started
every run, so it started LD5 and LD6 after the first refusal; it was ended by hand at 14:39:00 together with the two
runs still priming, LD2 (DeepSeek V4 Pro, all 42 samples primed) and LD6 (Grok 4.7, past its control). LD7 (`kimi-k3`)
and LD8 (`swe-2`) never started. `supervise.py` now watches between starts. No Devin request was sent after 14:39.
Files: LD1, LD3, LD4, LD5 (`failed`, with the refusal), LD2's last progress file (`LD2-…ended-by-hand.json`). LD6 left
only a log, which is not committed: nothing in this repository records LD6's control or what it used; what is said of
it here and in `ledger.md` (its control, about 5 requests) comes from that local log and from the login's request
counter, and cannot be checked from these files.

## 3. Claude Fable 5.2 on the Claude login (added at about 15:40)

Measured as its siblings on 2026-11-16 (`../claude-login-2026-11-16`, CS1 – CS8): plain probe, Messages format, the
control, then 2.5, 5, 7.5, 10, 15, 20, 25, 30, 40, 50, 60, 65 and 75 minutes, 3 samples each, 2 primes at a time, on
**Claude login A** (the one with the higher priority, −15, the login of CS1 – CS8), through a temporary alias
`probe/claude-fable-5-2` on that login only. Over the runs login A's request counter rose; the other Claude login's and
both Claude API keys' stayed at 0 (the API keys now list `claude-fable-5-2` by its plain name since the configuration
change of 15:58, not the alias). Anthropic took the default filler; `--filler list` was not needed. The process did
not change during these runs (16:18:13 throughout).

| Run | Request | Control | Warm at each age | Warm through | First all cold |
|---|---|---|---|---|---|
| LF1 | one `cache_control` marker, no ttl | hit | 3/3 from 2.5 min to 1 h; 0/3 at 65 and 75 min | 1 h | 65 min |
| LF2 | the marker with `ttl: "1h"` | hit | the same | 1 h | 65 min |

**Window** (`fable_window.py`, `limits-claude.jsonl`): one request of 500,500 " hello" (two tokens each), refused at
once: `prompt is too long: 1001190 tokens > 1000000 maximum`. No accepted large request was sent (Fable is the dearest
model on the plan), so the row has the named window (1,000,000) and no accepted size; the output limit was not tested.

providers.dev has no entry `claude-subscription/claude-fable-5-2` yet: these runs and the row name the model
`claude-fable-5-2` on route `claude-subscription`, as the siblings' rows do, and land there once the entry exists.

## 4. Antigravity: the login's other chat models (added at about 15:40)

The login's own model list (management API, `/credentials/models` for that login), as the login names them:

| Id | Name the login gives | Kind | CPA's local catalog says (not the login, not measured) | Run |
|---|---|---|---|---|
| `claude-opus-4-6-thinking` | Claude Opus 4.6 (Thinking) | chat | 200,000 / 64,000 output | LA2: control hit, refused while priming |
| `claude-sonnet-4-6` | Claude Sonnet 4.6 (Thinking) | chat | 200,000 / 64,000 | LA3: control hit, then ended |
| `gemini-3.8-flash-high` | Gemini 3.8 Flash | chat | 1,048,576 / 65,536 | LA1 (above) |
| `gemini-3.8-flash-tiered` | Gemini 3.8 Flash (Tiered) | chat | 1,048,576 / 65,536 | LA4: control hit, then ended |
| `gemini-3-flash` | Gemini 3 Flash | chat | 1,048,576 / 65,536 | not started |
| `gpt-oss-120b-medium` | GPT-OSS 120B (Medium) | chat | 114,000 / 32,768 | not started |
| `gemini-3.1-flash-lite` | Gemini 3.1 Flash Lite | chat | 1,048,576 / 65,535 | not started |
| `gemini-3.5-flash-lite` | Gemini 3.5 Flash Lite | chat | 1,048,576 / 65,535 | not started |
| `gemini-3.1-flash-image` | Gemini 3.1 Flash Image | image | none | not a chat model |

The login's list gives no window; the figures beside are CPA's local catalog (`models-local.json`). `owned_by` in
`/v1/models` is not the login: there `claude-sonnet-4-6` showed `antigravity` at 14:16 and `anthropic` after the
restart.

Each model was to get one run as LA1 (Responses format, 5,000-token prefix, standard schedule), through a temporary
alias `probe/ag-<id>` on the Antigravity login only, one prime at a time, started 15 s apart. 40 s in, while LA2 was
priming, Antigravity answered `429 RESOURCE_EXHAUSTED` (`RATE_LIMIT_EXCEEDED`: "You have exhausted your capacity on
this model. Resets in 0s."). LA2 ended at the refusal; the supervisor ended LA3 and LA4 (past their controls, which
all hit: 5,740 of 5,752, 5,760 of 5,772 and 2,633 of 4,672 tokens cached) and started nothing more. LA3 and LA4 left
only logs (not committed), so their tokens are not in the ledger, and their controls given here are read from those
local logs: no file in this repository records them. LA2's file is kept, not in `observed.json`.

**Result for the two Claude ids of this login** (`claude-opus-4-6-thinking`, `claude-sonnet-4-6`): the control hit (an
immediate re-send was served from the cache), no lifetime. By the chief's decision nothing more goes to them today.

**What the refusals mean for the owner's own use of this login today**, as far as the answers show: the 429 named one
model, `claude-opus-4-6-thinking` ("You have exhausted your capacity on this model. Resets in 0s."), a rate limit
(`RATE_LIMIT_EXCEEDED`) with no later reset time; nothing refused the account as a whole. The earlier 503s
(`MODEL_CAPACITY_EXHAUSTED`, 12:27 – 12:59 UTC, `gemini-3.8-flash-high`) were Google's server capacity, not this
account's.

## What was not measured (for the next task)

- **Devin lifetimes**, all eight: `devin/claude-opus-5-5`, `deepseek-v4-pro`, `gemini-4-argon`, `glm-5-3`,
  `gpt-6-1-sol`, `grok-4-7`, `kimi-k3`, `swe-2` (LD1 – LD8 above). The chief's pace for a retest: never more than one
  request to Devin at a time while priming (probe `--concurrency 1`, `--prime-pause` from probe 0.3.2), the next run
  only once the one before has logged `priming done`; on a 429, wait once for the reset it names plus a minute and go on
  at half the pace; a second 429, or any refusal that speaks of the plan, quota or credits, ends Devin.
- **Antigravity**: `gemini-3.8-flash-tiered`, `gemini-3-flash`, `gemini-3.1-flash-lite`, `gemini-3.5-flash-lite`,
  `gpt-oss-120b-medium`: no run. The chief's form for a second try: one run at a time, one request at a time while
  priming, cheapest first, the first refusal of any kind ends Antigravity. Not the two Claude ids.
- **GLM-5.3's window on Devin** (above).

## Files

- `limits-codex.jsonl`, `limits-devin.jsonl`, `limits-claude.jsonl`: every window request (the rows of `harness/limits.py`, plus
  `outputTokens`).
- `L*-2026-11-17T*.json` / `.md`: the lifetime runs (probe 0.3.1: `spent` sums what each run's answered requests used).
- `manifest-entries.json`: what these runs add to `observed/manifest.json`: 8 cache runs (LC1 – LC4, LM2, LA1, LF1,
  LF2), 13 limits rows that replace the rows of the same route, client and model, one new limits row (Fable), and 6
  `excluded` entries (LM1, LM3, the Devin runs, the GLM-5.3 window, the Antigravity runs LA2 – LA8).
- `ledger.md` (`ledger.py`): the tokens per request and per run, per login.
- `window_walk.py`, `run-windows.sh`, `fable_window.py`, `supervise.py`, `run-lifetimes.sh`: what ran. `logs/` stays local (git-ignored).

If a run's window is lost: the probes write `<label>-<time>.partial.json` as they go and their final files when done;
the supervisors log every process id they started in `logs/supervise-<login>.log`. A run cannot be resumed; one that
was cut off is kept as it is.
