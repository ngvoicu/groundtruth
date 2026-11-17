# The long cache setting on the Codex and Devin logins, the Antigravity login's other models, Meta to 24 h (2026-11-17)

Requests through the owner's local CLIProxyAPI (his build of 8.0.75, `ngvoicu-local-c52243ab`, process of 18:09:07
local; he restarted it at 18:38:51 on `ngvoicu-local-4c071f30`, the same plus one commit for the WebSocket auth-kind
event, nothing in these request paths). Probe 0.3.3, which records CLIProxyAPI's `X-CPA-AUTH-KIND` of every reply
(`oauth` = a login, `apikey` = an API key). Plan quota only; `ledger.md` has what each request or run used.

**Findings.**

- **Asking for the long cache does nothing on the Codex login through CLIProxyAPI, and on Devin: the setting does not
  exist on these routes.** The proxy deletes `prompt_cache_retention` and `prompt_cache_options` from every Codex
  request to the login, and rebuilds every Devin request in a protocol that has no such field. Neither route gets a
  long-profile run; each has an `excluded` entry with the proof.
- **The Codex runs that asked (CL1 – CL4) are therefore plain runs** and are recorded as such (`options: {}`,
  `removed_by_proxy: {"prompt_cache_retention": "24h"}`), each continuing today's plain run of the same model
  (`../logins-2026-11-17`, LC1 – LC4) with ages out to 24 hours.
- **Antigravity: no observable cache on four more models** (Gemini 3.1 Flash Lite, 3.5 Flash Lite, 3 Flash, GPT-OSS
  120B Medium): an immediate re-send read part of the prompt from cache, less than the probe's half. Gemini 3.8 Flash
  (Tiered) could not be measured: Google had no capacity for it for ten minutes.
- **Muse Ember and Muse Wonder on the Meta login** continue LM1 and LM3 (warm in every check to 2 h) at 4, 8, 12 and
  24 h. Running.

## 1. What the proxy does with the long setting

`fieldtest.py`, `fields-codex.jsonl`, `fields-devin.jsonl`: one small request per variant, 18:23 – 18:25 local, build
`ngvoicu-local-c52243ab`.

**Codex login** (`probe/gpt-6.1-sol`, Responses format). Answered 200: no field, `prompt_cache_retention` `"24h"` and
`"bogus-retention"`, `prompt_cache_options.ttl` `"12h"` and `"bogus-ttl"`, all with the same 309 input tokens. Refused:
an unknown top-level field, 400 `Unsupported parameter: unknown_field_xyz`. The ChatGPT backend refuses parameters it
does not know (and, as the knowledge base records from 2026-11-15, refuses both lifetime fields when a payload rule
puts them back), so 200 on invalid values means the fields never reach it. The source says why: the Codex translator
deletes both from every OpenAI Responses request (`internal/translator/codex/openai/responses/codex_openai-responses_request.go`;
commits `2ab25eae` "fix(codex): strip unsupported prompt_cache_options from OpenAI Responses requests", #4915, and
`2005788f` "fix(codex): filter out `prompt_cache_retention` in OpenAI→Codex responses request conversion", #5068),
the executor deletes `prompt_cache_retention` again, and `codex_executor_request.go` says: "OAuth and SIWC credentials
reject prompt_cache_options, so they keep the translator's removal" (only an OpenAI API key gets a client's
`prompt_cache_options.ttl` back, the owner's PR #7609). A 2,400-word prompt sent twice with each field was read from
cache on the second send (2,816 tokens), and the login reported no cache write in either tier (`ttl_30m_tokens` and
`ttl_12h_tokens` both 0): the backend does not show which tier it keeps.

What a real client sends: pi through CLIProxyAPI sends neither field for any Codex-format model (its Codex-format
client ignores `PI_CACHE_RETENTION`); pi's direct OpenAI client and OpenAI's SDKs send `prompt_cache_retention: "24h"`.
The runs sent that.

**Devin.** CLIProxyAPI turns every request into Devin's protobuf (`internal/runtime/executor/helps/devin_wire.go`,
`BuildDevinGetChatMessageRequest`): system prompt, messages, tools, max tokens, temperature, session id, the cascade id
(the cache key) and the model. No field carries a cache lifetime, and `cache_control` markers are skipped when the
content is read. `devin/swe-2` (Responses) answered 200 with the same 471 input tokens to no field,
`prompt_cache_retention` `"24h"` and `"bogus-retention"`, `prompt_cache_options.ttl` `"bogus-ttl"`, and an unknown
field. `devin/claude-haiku-5-5` in Claude's format answered 200 to a cache marker with `ttl: "1h"` and with
`ttl: "bogus-ttl"`; Anthropic refuses an invalid ttl with a 400. A long run would send Devin byte for byte what a short
run sends, so **no Devin run was made** (the chief's decision), for any of the 17 models of the website's `devin`
provider. Nothing else was sent to Devin.

## 2. Codex login: plain runs to 24 hours (CL1 – CL4)

The request of LC1 – LC4 (Responses, per-sample `prompt_cache_key`, 2,500-token prefix, 3 samples per age, a control
first, `--stop-on-refusal`), plus `prompt_cache_retention: "24h"`, which the proxy removed. Ages: the long schedule
plus 24 h, given as `--ages 10m,…,24h` (`--ages` replaces the schedule: `--schedule long --ages 24h` would check only
at 2.5, 5 and 7.5 min and 24 h). Pinned by temporary aliases `probe/<model>` on the Codex login only; every answer was
`oauth`, the OpenAI API key's counter stayed at 0. One run primed at a time, 2 requests at a time.

| Run | Model | Control | Warm / checks per age | Warm through | Last warm | First all cold | Published short today |
|---|---|---|---|---|---|---|---|
| CL1 | `gpt-6.1-sol` | hit (2,560 / 2,707) | running, see `logs/status.md` (to 24 h) | | | | 5 min |
| CL2 | `gpt-6.1-terra` | hit (2,560 / 2,682) | 1, 1, 1, 0, 0 of 3 (2.5 – 15 min), stopped | – | 7.5 min | 10 min | 0 |
| CL3 | `gpt-6-astra` | hit (2,560 / 2,714) | running (to 24 h) | | | | 2 h |
| CL4 | `gpt-6-luna` | **missed** (0 / 2,659, at 3 s and at 10 s) | none: ended at the control | – | – | – | 5 min |

Each continues LCn (`continues`): the entry carries LCn's checks and its own, in the short profile (no lifetime asked).
CL4 continues LC4 with only its missed control; Luna was not started again. The safe values the site derives are those
of the merged checks; LC1 – LC4 already had misses at 2.5 minutes.

## 3. Antigravity: the login's other chat models (AG1 – AG5)

As A3 and LA1: Responses, per-sample `prompt_cache_key`, 5,000-token prefix, the standard schedule, 3 samples per age,
one request at a time (`--concurrency 1 --prime-pause 1000`), one run at a time, cheapest first, `--stop-on-refusal`;
a run not primed in 10 minutes is ended. Each id is served by the Antigravity login only, so the plain ids; every
answer was `oauth`. The probe's rule: warm = at least half of the prompt (and 500 tokens) read from cache.

| Run | Model | Control: re-send read from cache | Result | `base_model` |
|---|---|---|---|---|
| AG1 | `gemini-3.1-flash-lite` | 2,031 of 4,670 | no observable cache | `google/gemini-3.1-flash-lite` |
| AG2 | `gemini-3.5-flash-lite` | 2,031 of 4,698 | no observable cache | `google/gemini-3.5-flash-lite` |
| AG3 | `gemini-3-flash` | 2,031 of 4,637 | no observable cache | null (models.dev has only `google/gemini-3-flash-preview`) |
| AG4 | `gemini-3.8-flash-tiered` | – | no run: 503 `MODEL_CAPACITY_EXHAUSTED` for 10 minutes | (`google/gemini-3.8-flash`) |
| AG5 | `gpt-oss-120b-medium` | 67 of 4,780 | no observable cache | null (models.dev lists `openai/gpt-oss-120b`, the site's catalog does not) |

On AG1 – AG3 part of the prompt was read from cache, but less than the rule's half, so the runs record no observable
cache and ended there; nothing was repeated to get over the line. On the same login today `gemini-3.8-flash-high`
read 2,647 of 4,686 (LA1, warm). The same 2,031 tokens on three models suggests a fixed cached block, but the records
alone don't show it. AG4: Google answered 503 "No capacity available for model gemini-3.8-flash-tiered on the server"
(then CLIProxyAPI's `auth_unavailable` while it paused the model) to every request from 18:28:54; ended by the
10-minute rule at 18:38:48, before its control was answered (`AG4-2026-11-17T16-28-48.not-primed.log`). AG5's three
requests ran across the proxy restart (18:38:49 – 18:39:05).

**What this means for the owner's own use of the login:** no refusal of the account. No 429, no quota or rate
answer; the only errors were Google's server capacity for `gemini-3.8-flash-tiered`, which the probe retried. The two
Claude ids of the login were not sent anything.

The website has no entry yet for these ids under `antigravity` (only `gemini-3.8-flash-high`); the rows land there
once entries exist.

## 4. Meta login: Ember and Wonder to 24 hours (ML1, ML3)

Made as LM1 and LM3: plain probe, no body extra, 2 primes at a time; CLIProxyAPI's payload rule for `muse-*` adds
`prompt_cache_retention: "24h"` to every request, so they are recorded with that option (long profile). Ages 4, 8,
12 and 24 h (the probe always adds 2.5, 5 and 7.5 min, which add samples to those ages of LM1 / LM3). `muse-*` ids
have one account, the Meta login; every answer `oauth`; its counter was 0 before the runs.

| Run | Continues | Control | So far | Last check due |
|---|---|---|---|---|
| ML1 | LM1 (`muse-ember-1.0`) | hit (2,548 / 2,649) | 3/3 at 2.5, 5, 7.5 min; running | ≈ 2026-11-18 18:31 local |
| ML3 | LM3 (`muse-wonder-1.0`) | hit (2,548 / 2,618) | 3/3 at 2.5, 5, 7.5 min; running | ≈ 2026-11-18 18:31 local |

## Tooling changes (each its own commit)

- Probe 0.3.3: every reply's `X-CPA-AUTH-KIND` recorded (per check, control, counted per run); `--record-header`.
- `build_observed.py`: `removed_by_proxy` (a field the client sent that the proxy is shown to delete; not in
  `options`; the proof in the note). The site reads observed runs as loose objects, so the key passes into
  `observed.json`.
- `build_observed.py`: a run whose control missed is accepted without ages (the rule of 14 November had refused it).

## Files

- `CL*`, `AG*`, `ML*` `-2026-11-17T*.json` / `.md`: the runs (a run still running has only its git-ignored
  `.partial.json` until it ends).
- `fields-codex.jsonl`, `fields-devin.jsonl`, `fieldtest.py`: the requests of section 1.
- `manifest-entries.json` (`make_entries.py`): 10 runs, 3 excluded entries (AG4, the Codex long setting, the Devin
  long setting). CL1 – CL4 continue `logins-2026-11-17/LC1` – `LC4` (runs in that part); ML1 and ML3 continue LM1 and
  LM3, which that part put in `excluded` and the assembly must move to `runs`.
- `ledger.md` (`ledger.py`), `run.sh`, `sequence.py` (one run of a login priming at a time, a login stopped at its
  refusal), `status.py` (`logs/status.md`). `logs/` stays local.

If this window is lost: `python3 results/logins-long-2026-11-17/status.py` rebuilds `logs/status.md` from the files;
the supervisors log every process id in `logs/sequence-<login>.log`. A run cannot be resumed; one that was cut off is
kept as it is.
