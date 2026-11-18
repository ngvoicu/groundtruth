# Prompt-cache lifetimes, measured 4–5 November 2026

Measured with version 0.1.0 of this tool. Each sample primes a fresh ~2,500-token prefix once and checks it **once** at a fixed
age; 3 samples per age. A check is warm when ≥ 50 % of the prompt (and ≥ 500 tokens) is reported as cached. Requests use
the OpenAI Responses format with a per-sample `prompt_cache_key`, the way pi and Codex send one per conversation.

**Lifetime** = last age where all checks were warm – first age where all were cold. Mixed rows (some warm, some cold at
the same age) mean the provider spreads requests over cache nodes or evicts early; treat the lower bound as the safe value.

- `cpa-8.0.53/`: through a local [CLIProxyAPI](https://github.com/router-for-me/CLIProxyAPI) 8.0.53, each row pinned to
  one account by a temporary alias (removed afterwards).
- `openrouter-direct/`: straight to OpenRouter, no proxy. This is the baseline for what the upstream itself does.
- `openrouter-direct-v0.2/`: R1 measured again with probe 0.2.0 (R1b).

Known values were not measured: Claude subscription through CLIProxyAPI (CPA sets a 1 h cache) and a Claude API key
(5 min default).

## Through CLIProxyAPI 8.0.53

| Row | Route | Model | Lifetime | Notes |
|---|---|---|---|---|
| C1 | Codex subscription | `gpt-6.1-sol` | **2 h – 12 h** | warm at 2 h, 2 of 3 at 4 h, cold at 12 h; 8 h lost to a network outage |
| C2 | Codex subscription | `gpt-6.1-terra` | < 2.5 – 7.5 min | ran before the probe sent a cache key; superseded by C1 |
| D1 | Devin | `devin/claude-opus-5-5` | **≥ 2 h** | one cold check at 50 min, otherwise warm to 2 h |
| D2 | Devin | `devin/gpt-6-1-sol` | 30 – 40 min | |
| D5 | Devin | `devin/gemini-4-argon` | 2.5 – 15 min | |
| D7 | Devin | `devin/glm-5-3` | < 2.5 – 30 min | mixed |
| D8 | Devin | `devin/grok-4-7` | < 2.5 – 15 min | mixed |
| D9 | Devin | `devin/deepseek-v4-pro` | cold at 2.5 min | first attempt aborted with no checks (file kept) |
| D3, D4, D6 | Devin | `swe-2`, `muse-wonder-1-0`, `kimi-k3` | no observable cache | D4 reports no usage at all; D3 is free |
| M1 | Meta (Muse Code login) | `muse-wonder-1.0` | 2.5 min – 2 h | reliable to ~25 min, mixed after |
| M3 | Meta | `muse-spark-1.3` | 7.5 – 40 min | |
| A3 | Antigravity | `gemini-3.8-flash-high` | 2.5 – 15 min | |
| O1 | OpenRouter via `openai-compatibility` | `anthropic/claude-opus-5.5` | **no cache** | CPA sends no cache markers on this route |
| O2, O3 | same | `openai/gpt-6.1-sol`, `-terra` | 30 – 40 min | same as direct |
| O4 | same | `google/gemini-4-argon` | < 2.5 – 10 min | |
| O5 | same | `google/gemini-3.8-flash` | no observable cache | |
| O6 | same | `x-ai/grok-4.7` | < 2.5 – 15 min | |
| O7 | same | `moonshotai/kimi-k3.1-pro` | cold at 2.5 min | direct (R7) caches; mixed |
| O8 | same | `deepseek/deepseek-v4-pro` | **2 h – 4 h** | |
| O9 | same | `z-ai/glm-5.3` | 5 – 15 min | mixed |
| O10 | same | `meta/muse-wonder` | 2.5 – 7.5 min | |
| O11 | same | `mistralai/mistral-large-4-0` | ≥ 10 min | short run |
| K1 | Claude API key, Messages format, explicit `ttl: "1h"` | `claude-opus-5-5` | **30 – 65 min** | CPA passes an explicit 1 h through; the beta header is not needed |

Not measured: A1/A2 (not offered on the Antigravity account), M2 (404).

## OpenRouter through CLIProxyAPI with built-in OpenRouter support

CLIProxyAPI 8.0.53 plus router-for-me/CLIProxyAPI#7284 (cache markers, session id, reasoning levels), 2026-11-06,
real OpenRouter model ids through an `openai-compatibility` entry. Files in `cpa-8.0.53-or/`.

| Row | Model | Request | Lifetime | Notes |
|---|---|---|---|---|
| P1 | `anthropic/claude-haiku-5.5` | messages, no ttl | **5 – 7.5 min** | was "no cache" (O1) before #7284 |
| P2 | same | messages, `ttl: "1h"` | **30 – 65 min** | the client's 1-hour request reaches Anthropic |
| P3 | `openai/gpt-6.1-sol` | responses, `prompt_cache_options.ttl: "12h"` | warm at 30 min, cold at 1 h | the 12 h request is dropped: CPA's Responses → Chat Completions translation doesn't carry `prompt_cache_options`, so this is the 30-min default |

## Straight to OpenRouter

| Row | Model | Lifetime | Notes |
|---|---|---|---|
| R1 | `anthropic/claude-opus-5.5`, top-level `cache_control` + `session_id` | ~~cold at 2.5 min~~ | **probe error**: priming stalled ~6 min on retries, so the "2.5 min" and "5 min" checks ran at 6.6 and 6.7 min. Replaced by R1b |
| R1b | `anthropic/claude-haiku-5.5`, same request, probe 0.2.0 | **5 – 7.5 min** | every check within 3 s of its age; Anthropic's 5-minute tier, as through CPA (P1) |
| R1h | same, explicit `ttl: "1h"` | 30 – 65 min | |
| R2, R3 | `openai/gpt-6.1-sol`, `-terra` | 30 – 40 min | |
| R4 | `google/gemini-4-argon` | 5 – 7.5 min | |
| R5 | `google/gemini-3.8-flash` | cold at 2.5 min | |
| R6 | `x-ai/grok-4.7` | 2.5 – 15 min | |
| R7 | `moonshotai/kimi-k3.1-pro` | < 2.5 min – 1 h | mixed |
| R8 | `deepseek/deepseek-v4-pro` | ≥ 2 h | |
| R9 | `z-ai/glm-5.3` | 2.5 min – 1 h | mixed |
| R10 | `meta/muse-wonder` | 2.5 – 30 min | all warm but one check through 25 min |
| R11 | `mistralai/mistral-large-4-0` | 7.5 – 15 min | |

## Later runs (pi and vendor harnesses, one folder each)

- `harness-2026-11-07/`: vendor CLIs (Codex CLI, Muse Code, Devin CLI) vs pi through CLIProxyAPI, same accounts.
  Muse Wonder 1.0 through pi → CLIProxyAPI → Meta (H6) was warm in every check to 2 h.
- `devin-harness-2026-11-08/`, `devin-cache-investigation-2026-11-09/`: Devin models.
- `ember-2026-11-10/`: Muse Ember 1.0 through pi → CLIProxyAPI → Meta. At default retention (E1): 5 min 2/2, 30 min
  1/2, 1 h 0/2, 2 h 1/2 (random eviction). With `prompt_cache_retention: "24h"` (E2): 16/16 warm, 5 min to 4 h. See
  its README.
- `devin-repeat-2026-11-10/`: four Devin open-weight routes again, 5 samples per age (5 min – 2 h), pi → CLIProxyAPI →
  Devin. DeepSeek V4.1 Flash 25/25 warm (≥ 2 h); GLM-5.3 warm at 5 min, 30 min and 1 h, cold at 15 min and 2 h (whole
  batches); Gemini 4 Argon 3/5 at 5 min, then cold; Grok 4.7 4/10 through 15 min, then cold. See its README.
- `gpt6-2026-11-11/`: GPT-6 Astra and Luna on a ChatGPT plan, Devin, OpenRouter and an OpenAI API key (plus GPT-6.1 Sol
  on the key), 3 samples per age. OpenAI key and OpenRouter: warm at 30 min, cold at 40. Devin: warm at 30 min, cold at
  1 h. ChatGPT plan: Astra warm through 2 h; Luna misses from 15 min. Both accept ~915K input there. See its README.
- `limits-2026-11-13/`: the input limit of GPT-6.1 Sol on a ChatGPT plan: 915,011 accepted, 922,500 refused (about
  922,511 tokens), the same as the other GPT-6 models there. A walk on Devin's `swe-2` found no refusal up to 930K but
  could not show that the model reads such an input; the walk of 2026-11-16 did, to 300K. See its README.
- `meta-24h-2026-11-10/`: Meta's `prompt_cache_retention: "24h"` measured out to 24 hours, 3 samples per age. Nothing
  is warm at 12 or 24 hours. Muse Ember 1.0 lasts between 4 and 8 hours, Muse Wonder 1.0 between 4 and 12, and
  Muse Spark 1.3 under an hour even with the setting. See its README.
- `muse-spark-openrouter-2026-11-12/`: Muse Spark 1.3 on OpenRouter, 3 samples per age. No age fully warm: about half
  the checks hit between 5 and 15 minutes, none at 2.5, 30 or 40. No safe lifetime. See its README.
- `openrouter-flash-2026-11-12/`: GLM 5.3 Flash and DeepSeek V4.1 Flash on OpenRouter. GLM: about half the checks hit
  from 2.5 to 30 minutes (7 of 13 at 2.5 minutes), none at 40 minutes or 1 hour; no safe lifetime. DeepSeek: 13 of 13
  at 2.5 minutes, 12 of 13 at 5 minutes, then about 70% out to 1 hour with no trend; safe to 2.5 minutes. See its
  README.
- `limits-2026-11-16/`: input limits on the Meta login and on Devin. Muse Ember 1.0 and Muse Spark 1.3: the refusal
  names a 1,048,576-token window (input and output together); 1,047,604 accepted. Devin: GLM-5.3, DeepSeek V4.1 Flash,
  DeepSeek V4 Pro and Gemini 4 Argon accept their listed 1,048,576 (about 1,047,500 accepted, refused about 4K more);
  Claude Haiku, Sonnet and Opus 5.5 accept 999,072 and refuse about 1,004,000; GPT-6.1 Terra, GPT-6 Astra and GPT-6
  Luna accept 911,390 and refuse 923,500 although Devin lists 1,000,000. `swe-2` read both ends of a 300K input (above
  its listed 262K), no edge: in `observed.json` as read to 300,499 tokens, with no refusal. See its README.
- `claude-login-2026-11-16/`: Claude Opus 5.5 and Sonnet 5.5 on one Claude login, plain probe through CLIProxyAPI,
  Messages format, 3 samples per age (CS1 – CS4). With no ttl and with `ttl: "1h"` alike: 3/3 warm at every age from
  2.5 minutes to 1 hour, 0/3 at 65 and 75 minutes. This is the 1-hour cache that CLIProxyAPI asks for on Claude logins,
  now measured; the usage of single writes (`tier.jsonl`) puts every cached token in the 1-hour tier. Claude Haiku 5.5
  (CS7, CS8) gives the same, measured with the probe's `--filler list`: Anthropic refused the default filler of random
  words on this model (category "bio"; CS5 and CS6 kept as records, not in `observed.json`). The filler does not change
  caching. See its README.
- `openai-direct-2026-11-15/`: GPT-6.1 Sol straight to the OpenAI API with an API key, no proxy, 3 samples per age.
  Default: warm through 30 minutes, cold at 40 and 50. With `prompt_cache_options.ttl: "12h"`: warm at every age to
  12 hours, cold at 24. The run file does not record the request body: the 12-hour setting is known from the owner's
  note on the run and its label, and the result agrees with it (the default run, started the same minute, was cold at
  40 minutes). See its README.
- `direct-2026-11-17/`: straight to the OpenAI and Anthropic APIs with the owner's keys, no proxy, plain probe with
  `--usage-log`, 3 samples per age. GPT-6 Luna, GPT-6.1 Terra, GPT-6 Sol and GPT-6 Astra: warm through 30 minutes,
  cold at 40, OpenAI's documented 30 minutes. `chat-latest`: warm in every check to 2 hours, its first measured
  lifetime (OpenAI reported cache hits but no cache write). Claude Haiku, Sonnet and Opus 5.5 and Fable 5.2: 5 – 7.5
  minutes with no ttl, 1 hour – 65 minutes with `ttl: "1h"`, as documented; Haiku with `--filler list` (it refused
  the default filler again). `gpt-audio-1.5` takes no text request, and the key cannot call `gpt-6-cyber` or the two
  Daybreak models: nothing measured. Cost $10.01 (`ledger.md`). See its README.
- `logins-2026-11-17/`: the subscription logins through CLIProxyAPI, probe 0.3.1 with `--stop-on-refusal`. Codex
  login (LC1 – LC4), checked from 2.5 minutes: GPT-6.1 Sol and GPT-6 Astra hit 2 of 3 at 2.5 minutes, GPT-6 Luna 1 of 3,
  all three 3 of 3 at 5 minutes, then some later ages miss (Sol 0 of 3 at 1 hour, 2 of 3 at 2 hours). Their published
  value is 0: no tested age through which every check hit, which does not mean the route does not cache; a first look
  at 2.5 minutes with plain requests for Astra and Luna (Sol's C1 had also missed at 5 and 7.5 minutes), not a
  comparison that shows a change. Early misses also occurred without a preceding large request or overlapping model
  priming (GS1 and GA1, `logins-gpt-6-2-2026-11-17/`); their cause is not established. The runs continuing them (CL1, CL3, CL4,
  `logins-long-2026-11-17/`) are published with them.
  Meta login with the 24-hour retention CLIProxyAPI adds: Muse Spark 1.3 warm through 10 minutes, cold at 30 (LM2);
  Ember and Wonder (LM1, LM3) completed the standard schedule warm in all 42 checks to 2 hours, where that schedule
  ends; each is published with the run continuing it at 4, 8, 12 and 24 hours (ML1, ML3, `logins-long-2026-11-17/`),
  as one evaluation, whatever it showed. Antigravity Gemini 3.8 Flash: safe to 2.5 minutes, as
  A3 (LA1). Claude Fable 5.2 on a Claude login: warm to 1 hour, cold at 65 minutes, with and without `ttl: "1h"`
  (LF1, LF2); its refusal names a 1,000,000-token window. Narrower input windows (below). Devin and Antigravity's
  other models refused for request rate: no lifetime. See its README.
- `gpt-6-2-2026-11-17/`: GPT-6.2 Sol and GPT-6.2 Astra (released that day) straight to the OpenAI API with the owner's
  key, plain probe, 3 samples per age: both warm 3/3 through 30 minutes, 0/3 at 40 and 50 (30 – 40 minutes; OpenAI
  documents a 30-minute minimum). One window request each at 1,100,000 tokens, refused naming no figure: no limits row.
  See its README.
- `logins-gpt-6-2-2026-11-17/`: the same two models on the Codex login through CLIProxyAPI, made as LC1 and LC3 but
  with no large request before the priming, the models primed one after the other, and nothing else using the login.
  Sol (GS1): 2 of 3 at 2.5 minutes, cold from 5. Astra (GA1): 2 of 3 at 2.5 minutes, 3 of 3 from 5 to 30, cold from
  75. Both published as 0 (no tested age through which every check hit); early misses also occurred here without a
  preceding large request or overlapping model priming; their cause is not established. Both refuse 930,000 tokens naming no limit: no limits row. See its
  README.
- `logins-long-2026-11-17/`: the long cache setting on the logins, Antigravity's other models, and the 24-hour
  continuations. Asking for the long cache does nothing on the Codex login through CLIProxyAPI or on Devin (the proxy
  removes the field, or Devin's protocol has none): no long run, an `excluded` entry with the proof. CL1 – CL4 are
  plain runs continuing LC1 – LC4 (`removed_by_proxy`); CL1 and CL3 add data to 2 hours only (the proxy refused their
  later checks), CL4's control missed. Antigravity: on Gemini 3.1 Flash Lite, 3.5 Flash Lite, 3 Flash and GPT-OSS 120B
  Medium the control's re-send read less than half of the prompt from cache (2,031 of about 4,700 tokens on the three
  Gemini models, 67 of 4,780 on GPT-OSS), so the runs ended there with no timed check: lifetime inconclusive, under
  `excluded`, not published. Gemini 3.8 Flash (Tiered): its control was answered, its priming did not complete (no
  capacity); excluded. Muse Ember and Wonder on the Meta login, each read with LM1 / LM3: Ember warm
  through 2 hours, all cold at 4; Wonder warm through 4 hours, no data at 8 (the proxy's lookup of Meta's host timed
  out), all cold at 12. A restart of the Mac on 2026-11-18 cut off CL1, CL3, ML1 and ML3 before 24 hours; their
  progress files are their run files, unchanged. See its README.
- `openrouter-2026-11-18/`, **batch 1** (from `campaign/openrouter` at `f1cca4d`; the measuring goes on, later batches
  follow): OpenRouter's chat models released since 2026-08-17, straight to OpenRouter with a key of the campaign's,
  default route, plain probe, nothing asked about caching, 3 samples per age. **Released: 19 runs**, those of the folder's
  `manifest-entries.json` whose control hit and that are not in its upstream-changed list. Among the big releases:
  Claude Fable 5.2 warm through 5 minutes, cold at 7.5 (with a top-level `cache_control` and a `session_id`, as R1b);
  GPT-6.2 Astra warm through 25 minutes, 2 of 3 at 30, cold at 40; Qwen4 Max 2 of 3 at 2.5 minutes, cold at 40.
  **Held back in this batch, under `excluded`** (the folder lists them otherwise; the assembly holds them): the nine
  runs of `manifest-entries.json` whose control read 0 cached tokens (Gemini 4 Hydrogen and eight others), until a run
  with a larger prompt shows whether the ~2,500-token prompt was under the upstream's smallest cacheable size; and the
  five runs of `manifest-entries-upstream-changed.json` (GPT-6.2 Sol unpinned and pinned to OpenAI, Gemini 4 Carbon,
  Muse Ember, DeepSeek V4.1 Flash 1017), until it is decided how a run whose check crossed upstreams is published. Six
  failed runs are under `excluded` with the folder's reasons (one free model refused by OpenRouter's free-request
  limit, two free models refused by their upstream's rate limit, ScaleDown Extract takes no plain request, two Muse Spark contributor models excluded by the account's
  data policy). See its README and `results.md`.

## The limits rows of observed.json (2026-11-17)

Every `limits` row now gives the refused input in tokens, counted like the accepted one, and the day of its requests.
Where the refusal states no count (Codex, Devin), the refused size in filler words is converted with the tokens per
word and the overhead of the accepted requests of the same walk; each row's note says how. Codex login: 922,500 words
is 922,511 tokens (Sol, Astra, Luna). Devin: GPT-6.1 Sol 925,390; GPT-6.1 Terra, GPT-6 Astra and Luna 923,890; GLM-5.3
1,052,845; DeepSeek V4.1 Flash 1,052,864; DeepSeek V4 Pro 1,052,917; Gemini 4 Argon 1,052,865; Claude 1,004,446.

- The three Claude-login rows carry the request accepted just under the named window: 998,953 tokens.
- GPT-6.1 Terra on the Codex login is back (`limits-2026-11-08`): 920,870 accepted, a request of 921,875 words (921,886
  tokens) refused. It was left out on 2026-11-15 to keep the documented 922,000; providers.dev now applies a 1 % margin
  before a measurement contradicts documentation, so the row is shown beside 922,000 and does not replace it.
- Devin's `swe-2` has a row: 300,499 tokens accepted and read to the end, no refusal (`limits-2026-11-16`).
- The Devin GPT-6.1 Sol rows carry no time. They were added to the `limits-2026-11-08` file on 9 November, so the
  row is dated 2026-11-09. The OpenRouter rows of that file, which carry no time either, are dated 2026-11-08.

**2026-11-17** (`logins-2026-11-17`): one request just over the round number and one just under it closed each gap
to 800 tokens, and 13 rows were replaced. Codex login, GPT-6.1 Sol, GPT-6 Astra and GPT-6 Luna: 921,500 accepted,
922,300 refused (documented 922,000). Devin: GPT-6.1 Sol, GPT-6.1 Terra, GPT-6 Astra and Luna the same; Claude Haiku,
Sonnet and Opus 5.5 999,500 / 1,000,300; DeepSeek V4.1 Flash, DeepSeek V4 Pro and Gemini 4 Argon 1,048,076 /
1,048,876. GLM-5.3 got no answer under its edge (a 502, then nothing), so its row stays as it was. New row: Claude
Fable 5.2 on the Claude login, the window named by the refusal (1,000,000), no accepted size. For the models named
here, the refused sizes in the paragraph above are those of the rows before this day.

## What this means

- **Claude through CLIProxyAPI caches** on every route except OpenRouter via `openai-compatibility`: subscriptions (1 h,
  set by CPA), API keys (5 min, or 1 h when the client asks), Devin (≥ 2 h). A client that warms every ~4.5 min keeps
  any of them warm.
- **OpenRouter via `openai-compatibility` never caches Claude** on CPA without #7284, because CPA adds no
  `cache_control`. Direct OpenRouter does (R1h). With #7284 it does: 5 – 7.5 min by default (P1), 30 – 65 min when the
  client asks for 1 h (P2).
- **OpenAI's 12-hour lifetime doesn't pass through CPA to OpenRouter** yet (P3): the option is dropped when CPA
  translates Responses to Chat Completions.
- **Codex keeps the cache for hours when a cache key is sent** (C1). Without a key (C2) checks land on other cache
  nodes and look cold within minutes. Checked from 2.5 minutes with a key (C1 and `logins-2026-11-17`, LC1 – LC4), the
  same route misses some checks in the first minutes and at some later ages, with fully warm ages between (all of
  LC1 – LC4 3 of 3 at 5 minutes): no age through which every check hit, in today's runs.
- **GPT-6.1 elsewhere lasts 30–40 min**, matching OpenAI's documented ≥ 30 min, through CPA or not; so do the GPT-6
  models on an OpenAI key (`direct-2026-11-17`).
- Many open-weight routes (GLM, Kimi, Grok, Gemini) are mixed or short: a client should not assume they cache, and
  should stop warming when a warm-up reads nothing from cache.
