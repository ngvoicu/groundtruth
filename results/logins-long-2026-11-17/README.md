# The long cache setting on the Codex and Devin logins, the Antigravity login's other models, Meta to 24 h (2026-11-17)

Requests through the owner's local Provimux (his build of CLIProxyAPI 8.0.75, `ngvoicu-local-c52243ab`, process of 18:09:07
local; he restarted it at 18:38:51 on `ngvoicu-local-4c071f30`, the same plus one commit for the WebSocket auth-kind
event, nothing in these request paths). Probe 0.3.3, which records CLIProxyAPI's `X-CPA-AUTH-KIND` of every reply
(`oauth` = a login, `apikey` = an API key). Plan quota only; `ledger.md` has what each request or run used.

**Findings.**

- **Asking for the long cache does nothing on the Codex login through Provimux, and on Devin: the setting does not
  exist on these routes.** The proxy deletes `prompt_cache_retention` and `prompt_cache_options` from every Codex
  request to the login, and rebuilds every Devin request in a protocol that has no such field. Neither route gets a
  long-profile run; each has an `excluded` entry with the proof.
- **The Codex runs that asked (CL1 – CL4) are therefore plain runs** and are recorded as such (`options: {}`,
  `removed_by_proxy: {"prompt_cache_retention": "24h"}`), each continuing today's plain run of the same model
  (`../logins-2026-11-17`, LC1 – LC4) with ages out to 24 hours.
- **Antigravity: four more models, lifetime inconclusive** (Gemini 3.1 Flash Lite, 3.5 Flash Lite, 3 Flash, GPT-OSS
  120B Medium): the immediate re-send read part of the prompt from cache, less than the probe's half, so the runs
  ended at the control with no timed check. That shows neither a cache that expired nor that there is none; the four
  runs are under `excluded`, not published as a lifetime. Gemini 3.8 Flash (Tiered): its control was answered (warm),
  then its priming did not complete (Google had no capacity); no timed evidence, excluded.
- **Muse Ember and Muse Wonder on the Meta login** continue LM1 and LM3 (warm in every check to 2 h), each read with
  its continuation as one run: **Ember warm through 2 h, all cold at 4 h; Wonder warm through 4 h, no data at 8 h,
  all cold at 12 h.** Both runs were cut off before 24 h (section 5).
- **The Mac was restarted at 10:16 local on 2026-11-18** and ended CL1, CL3, ML1 and ML3 before their 24-hour checks.
  A run cannot be resumed: their progress files are their run files, committed unchanged (section 5).

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

What a real client sends: pi through Provimux sends neither field for any Codex-format model (its Codex-format
client ignores `PI_CACHE_RETENTION`); pi's direct OpenAI client and OpenAI's SDKs send `prompt_cache_retention: "24h"`.
The runs sent that.

**Devin.** Provimux turns every request into Devin's protobuf (`internal/runtime/executor/helps/devin_wire.go`,
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
| CL1 | `gpt-6.1-sol` | hit (2,560 / 2,707) | 2, 3, 1, 2, 3, 1, 3, 2, 2, 1, 2, 1, 2, 2 of 3 (2.5 min – 2 h); 4, 8, 12 h refused by the proxy (errors, below); 24 h never ran (section 5) | – | 2 h | – | 5 min |
| CL2 | `gpt-6.1-terra` | hit (2,560 / 2,682) | 1, 1, 1, 0, 0 of 3 (2.5 – 15 min), stopped | – | 7.5 min | 10 min | 0 |
| CL3 | `gpt-6-astra` | hit (2,560 / 2,714) | 3, 3, 3, 3, 2, 3, 1, 3, 1, 2, 2, 1, 2, 1 of 3 (2.5 min – 2 h); 4, 8, 12 h refused by the proxy (errors, below); 24 h never ran (section 5) | 10 min | 2 h | – | 2 h |
| CL4 | `gpt-6-luna` | **missed** (0 / 2,659, at 3 s and at 10 s) | none: ended at the control | – | – | – | 5 min |

Each continues LCn (`continues`): the entry carries LCn's checks and its own, in the short profile (no lifetime asked).
CL4 continues LC4 with only its missed control; Luna was not started again. Read as one run with LC1 and LC3, CL1 and
CL3 give: Sol 4, 6, 2, 4, 5, 3, 6, 5, 4, 3, 2, 2, 4, 4 of 6, Astra 5, 6, 5, 5, 5, 5, 4, 4, 3, 4, 3, 4, 5, 2 of 6
(2.5 min – 2 h); for both no age through which every check hit, last warm 2 h, no age all cold (LC1's 0 of 3 at 1 h
is 2 of 6 with CL1), and no data after 2 h. The safe values the site derives are those
of the merged checks; LC1 – LC4 already had misses at 2.5 minutes.

**The checks from 4 hours on were refused by the proxy; CL1's and CL3's data end at 2 hours.** At 20:50 local the
owner's other session rewrote Provimux's configuration with `oauth.excluded-models`, which among much else excludes
`gpt-6.1-sol`, `gpt-6-astra` and `gpt-6-luna` from the Codex login (the login now serves `gpt-6.2-sol`,
`gpt-6.2-astra`, `gpt-6.1-terra`, `codex-auto-review` and image models; the plain old ids are left to the OpenAI API
key). The login file was rewritten by a token refresh at 20:48:49 and holds no alias since; whether the refresh or the
owner's session emptied it, the files and the management API do not say. It is the same account (account id, e-mail
and plan in the file unchanged against the backup of 18:22, compared by script, not printed). The 2-hour checks (about
20:28 and 20:30 local) were still answered by the login; the 4-hour checks (22:28 and 22:31 local) were answered 400
`unknown provider for model probe/gpt-6.1-sol` / `probe/gpt-6-astra` by the proxy itself: nothing reached OpenAI. The
8- and 12-hour checks got the same answer: each is recorded as an error (it counts neither warm nor cold). The 24-hour
checks never ran: the restart of 2026-11-18 cut both runs off (section 5). The aliases were not put back, by the chief's decision: they would point
at models the owner had excluded from the login. No alias of this part is left in the proxy, and its backup
(`pre-logins-long-aliases-20261117-182253`) was deleted at 22:46 after one read for that comparison: it predates the owner's changes and must never be restored.

## 3. Antigravity: the login's other chat models (AG1 – AG5)

As A3 and LA1: Responses, per-sample `prompt_cache_key`, 5,000-token prefix, the standard schedule, 3 samples per age,
one request at a time (`--concurrency 1 --prime-pause 1000`), one run at a time, cheapest first, `--stop-on-refusal`;
a run not primed in 10 minutes is ended. Each id is served by the Antigravity login only, so the plain ids; every
answer was `oauth`. The probe's rule: warm = at least half of the prompt (and 500 tokens) read from cache.

| Run | Model | Control: prime / re-send read from cache | Result | In `observed/manifest.json` |
|---|---|---|---|---|
| AG1 | `gemini-3.1-flash-lite` | 0 / 2,031 of 4,670 | under the criterion; no timed check: lifetime inconclusive | `excluded` |
| AG2 | `gemini-3.5-flash-lite` | 0 / 2,031 of 4,698 | the same | `excluded` |
| AG3 | `gemini-3-flash` | 0 / 2,031 of 4,637 | the same | `excluded` |
| AG4 | `gemini-3.8-flash-tiered` | warm, 2,620 of 4,659 (re-send) | control answered; priming did not complete; no timed evidence, no run file | `excluded` |
| AG5 | `gpt-oss-120b-medium` | 67 / 67 of 4,780 | under the criterion; no timed check: lifetime inconclusive | `excluded` |

On AG1 – AG3 part of the prompt was read from cache on the re-send, but less than the rule's half, so the runs ended
at the control; nothing was repeated to get over the line. On the same login that day `gemini-3.8-flash-high` read
2,647 of 4,686 (LA1, warm). The same 2,031 tokens on three models suggests a fixed block read from cache, but the
records alone don't show it. A control under the criterion with no timed check is inconclusive about the lifetime:
it shows neither a cache that expired nor that there is none, so AG1 – AG3 and AG5 are not published as a lifetime
(they were entered as runs in the first assembly and moved to `excluded` after its review).

AG4 (`AG4-2026-11-17T16-28-48.not-primed.log`, times in UTC): Google answered 503 "No capacity available for model
gemini-3.8-flash-tiered on the server" (then Provimux's `auth_unavailable` while it paused the model) from 18:28:54
local; after five retries the control was answered at 18:30:48 local, warm (2,620 of 4,659 read from cache). The
priming of its 42 samples then did not complete (the same 503s and one TLS handshake timeout, answered 500 by the
proxy), and the run was ended by the 10-minute rule at 18:38:48 local. It left no run file and no timed evidence.
AG5's three requests ran across the proxy restart (18:38:49 – 18:39:05).

**What this means for the owner's own use of the login:** no refusal of the account. No 429, no quota or rate
answer; the only errors were Google's server capacity for `gemini-3.8-flash-tiered` and one TLS handshake timeout
on the way to Google, which the probe retried. The two
Claude ids of the login were not sent anything.

The website has no entry for these ids under `antigravity` (only `gemini-3.8-flash-high`); with the runs under
`excluded` it gets none from this folder.

## 4. Meta login: Ember and Wonder to 24 hours (ML1, ML3)

Made as LM1 and LM3: plain probe, no body extra, 2 primes at a time; Provimux's payload rule for `muse-*` adds
`prompt_cache_retention: "24h"` to every request, so they are recorded with that option (long profile). Ages 4, 8,
12 and 24 h (the probe always adds 2.5, 5 and 7.5 min, which add samples to those ages of LM1 / LM3). `muse-*` ids
have one account, the Meta login; every answer `oauth`; its counter was 0 before the runs.

| Run | Continues | Control | So far | Last check due |
|---|---|---|---|---|
| ML1 | LM1 (`muse-ember-1.0`) | hit (2,548 / 2,649) | 3/3 at 2.5, 5, 7.5 min; 4 h 0/3; 8 h no data (3 errors); 12 h 0/3; 24 h never ran | cut off |
| ML3 | LM3 (`muse-wonder-1.0`) | hit (2,548 / 2,618) | 3/3 at 2.5, 5, 7.5 min; 4 h 3/3; 8 h no data (3 errors); 12 h 0/3; 24 h never ran | cut off |

**8 hours: no data.** All three 8-hour checks of each run failed after their retries: Provimux answered HTTP 504
between 02:32 and 02:58 local on 2026-11-18, its lookup of Meta's API host having timed out (the run logs, local). The
Mac was awake. An errored check counts neither warm nor cold, so 8 h is an age without data, not a cold age.

**Each pair read as one run** (`continues`; LM1 and LM3 were held back to be published with these, whatever they
showed, a decision of 2026-11-17 taken before any of their later checks):

| Chain | Warm / checks per age (2.5, 5, 7.5 min; 10 min – 2 h; 4 h; 8 h; 12 h) | Warm through | Last warm | First all cold |
|---|---|---|---|---|
| LM1 + ML1 (Ember) | 6/6, 6/6, 6/6; 3/3 at every age; 0/3; –; 0/3 | 2 h | 2 h | 4 h |
| LM3 + ML3 (Wonder) | 6/6, 6/6, 6/6; 3/3 at every age; 3/3; –; 0/3 | 4 h | 4 h | 12 h |

Ember is gone between 2 and 4 hours; Wonder between 4 and 12 hours (8 h has no data, so it cannot be narrowed).

## 5. The restart that cut off CL1, CL3, ML1 and ML3

The Mac was restarted at 10:16 local on 2026-11-18 (an ordinary restart; the chief's record). It ended the four
day-long runs before their 24-hour checks (due about 18:27 – 18:31 local). No process of theirs is left. A run cannot
be resumed, so each is kept as the restart left it: the probe's progress file (`<label>-<start>.partial.json`, status
`"running"`), committed unchanged with `git add -f` (`*.partial.json` is ignored elsewhere), with no `.md`. The last
lines of their logs are from 06:28 – 06:32 local (the 12-hour checks).

| Run | Model | Checks in the file (warm / cold / error) | What happened |
|---|---|---|---|
| CL1 | `gpt-6.1-sol` | 51: 27 / 15 / 9 | answered through 2 h; the 4-, 8- and 12-hour checks refused by the proxy (HTTP 400, section 2; nothing reached OpenAI); 24 h never ran |
| CL3 | `gpt-6-astra` | 51: 30 / 12 / 9 | the same |
| ML1 | `muse-ember-1.0` | 18: 9 / 6 / 3 | 4 h: 0 of 3 warm; 8 h: all three failed (HTTP 504, section 4); 12 h: 0 of 3; 24 h never ran |
| ML3 | `muse-wonder-1.0` | 18: 12 / 3 / 3 | 4 h: 3 of 3 warm; 8 h: as ML1; 12 h: 0 of 3; 24 h never ran |

What the build makes of them (`scripts/build_observed.py`, `read_plain`): it reads a progress file as it reads a final
one; a check with an error is left out (neither warm nor cold), an age whose checks all errored has no row, and an age
that never ran has none either. So CL1 and CL3 add data to 2 h only (to LC1 and LC3), and the chains above are what
ML1 and ML3 give. Each manifest entry says the run was cut off and which ages have no data. No tooling change was
needed.

## Tooling changes (each its own commit)

- Probe 0.3.3: every reply's `X-CPA-AUTH-KIND` recorded (per check, control, counted per run); `--record-header`.
- `build_observed.py`: `removed_by_proxy` (a field the client sent that the proxy is shown to delete; not in
  `options`; the proof in the note). The site reads observed runs as loose objects, so the key passes into
  `observed.json`.
- `build_observed.py`: a run whose control missed is accepted without ages (the rule of 14 November had refused it). Since
  AG1 – AG3 and AG5 went to `excluded`, no published row relies on it.

## Files

- `CL*`, `AG*`, `ML*` `-2026-11-17T*.json` / `.md`: the runs that ended by themselves; CL1, CL3, ML1 and ML3 are
  their progress files `*.partial.json`, unchanged (section 5).
- `fields-codex.jsonl`, `fields-devin.jsonl`, `fieldtest.py`: the requests of section 1.
- `manifest-entries.json` (`make_entries.py`): 6 runs (CL1 – CL4, ML1, ML3), 7 excluded entries (AG1 – AG3 and AG5:
  lifetime inconclusive; AG4; the Codex long setting; the Devin long setting). CL1 – CL4 continue `logins-2026-11-17/LC1` – `LC4` (runs in that part); ML1 and ML3 continue LM1 and
  LM3, which that part put in `excluded` and the assembly must move to `runs`.
- `ledger.md` (`ledger.py`), `run.sh`, `sequence.py` (one run of a login priming at a time, a login stopped at its
  refusal), `status.py` (`logs/status.md`). `logs/` stays local.

**The proxy.** Nothing of this part is left to put back in the proxy: its four `probe/` aliases are gone (see section 2) and its
backup is deleted.

`python3 results/logins-long-2026-11-17/status.py` rebuilds `logs/status.md` from the files (a process id written
down before the machine's last boot counts as ended); the supervisors logged every process id in
`logs/sequence-<login>.log`. A run cannot be resumed; one that was cut off is kept as it is.
