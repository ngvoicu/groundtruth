# OpenRouter's chat models released since 2026-08-17: cache lifetimes, straight with a key of its own, 2026-11-18

**State of this folder: final, 2026-11-18 about 14:45 UTC. Every run has ended; nothing runs.** Batches were pushed
while the measuring went on: batch 1 `f1cca4d`, batch 2 `6abf96d`, the reviewer's rulings `c40cc28`, batch 3 `87e12f4`,
the chief's rulings of m-10781 `d78171e`. A run gets its entry
only once it has finished. The folder is complete in
itself at every pushed commit.

Plain probe (`src/cli.ts`) straight to `https://openrouter.ai/api/v1`, no proxy in between (route `openrouter`, client
`direct`). One OpenRouter key of the owner's, made for this campaign, with a limit of $20 (read from the macOS Keychain
by `key.py` straight into the probe's environment, never printed or written). `run.sh` holds the command of every
run; `supervise.py` (detached, every 3 minutes) starts them through `status.py --launch`, which keeps the $18 stop.

## Which models

The website's OpenRouter entries of type `chat`, released on or after 2026-08-17, with no cache evaluation
(`cache_lifetime.short.evaluations` and `.long.evaluations` both 0): **85** at 08:3x UTC, dataset `d45a948137b1bc07`,
the same 85 as the chief's list (`plan.py`; the entries as read in `sources/providers-dev-entries.json`). Every one
was on OpenRouter's model list (`sources/openrouter-models.json`); each was checked again just before its run started
(`offered.jsonl`: still offered, the price), and the ledger uses that price.

Order (`plan.json`): the seven big releases first (`openai/gpt-6.2-sol`, `google/gemini-4-hydrogen`,
`google/gemini-4-carbon`, `qwen/qwen4-max`, `meta/muse-ember`, `anthropic/claude-fable-5.2`, `openai/gpt-6.2-astra`),
then the others from the cheapest input price to the dearest, last OpenAI's `-pro` variants (`openai/*-pro`) and the
`~…-latest` aliases. Other models whose names end in `-pro` (`nex-agi/nex-n2.5-pro`, `xiaomi/mimo-v2.6-pro`,
`kt/midm-k-3.0-pro`) are models of their own, not variants, and run in price order.

## How

The method of `../openrouter-direct` and `../openrouter-direct-v0.2` (the measured direct OpenRouter rows R2 – R11,
R1b), the launch files and the ledger of `../direct-2026-11-17`:

- Responses format (`POST /responses`), a `prompt_cache_key` per sample, a ~2,500-token prefix of the default filler,
  16 output tokens, **nothing asked about caching**, the standard schedule (control, then 2.5 min to 2 h, stopping
  after two fully cold ages), 3 samples per age, `--stop-on-refusal` (a rate, credit or key-limit refusal ends the run,
  never retried), `--usage-log`.
- **Anthropic** (`anthropic/claude-fable-5.2`, `anthropic/claude-sonnet-5.5`): as R1b, the only measured direct
  OpenRouter row of that lab without a ttl, a top-level `cache_control: {"type": "ephemeral"}` (`--body-extra`) and a
  per-sample `session_id`. The run file records the body extra as sent, and `scripts/build_observed.py` requires it in
  the options as sent, so these rows carry `{"cache_control": {"type": "ephemeral"}, "session_id": true}` where R1b
  (whose 0.2.0 file records no request) carries `"top-level"`. No lifetime is asked in either, so both land in the short
  profile (`lifetimeAsked` in `site/src/core/cache.ts` reads `ttl`, `prompt_cache_retention`,
  `prompt_cache_options.ttl`); `scratch_build.py` prints it.
- **Upstreams.** OpenRouter can serve a model from several upstream providers, and a cache lives at one of them. The
  existing direct rows pinned nothing (no `provider` field), so these runs pin nothing either: they measure OpenRouter's
  default route, the website's entry. OpenRouter's Responses replies do not name the upstream, so every reply id
  (logged by the probe since 0.3.4) is looked up once in `GET /api/v1/generation` (free) by `upstream.py`:
  `upstreams.jsonl` has, per reply, the upstream that answered, every attempt OpenRouter made (a fallback shows there),
  the model version and the session id OpenRouter used (the `prompt_cache_key`). Each check is paired with its sample's
  priming by that key. **Crossings** (the reviewer's rulings on batch 1, m-10767): a run whose timed checks include
  checks answered by another upstream than their sample's priming is published as what the default route gives, in
  `manifest-entries.json`, with the crossings told in its entry's `note` (which checks, primed where, answered where,
  the outcome, and that such a miss shows failed reuse through the default route, not expiry at the upstream); the
  observed crossings stay out of `options`. A crossing in a control that missed, with no timed check (Gemini 4
  Carbon), is excluded: no lifetime measured. Until batch 2 these runs were kept apart in
  `manifest-entries-upstream-changed.json` (the chief's decision, m-10723); that list is now empty and kept only so
  that the earlier commits read the same.
- **GPT-6.2 Sol pinned to OpenAI** (`openai--gpt-6.2-sol-pinned-openai`): a second Sol run with
  `{"provider": {"order": ["openai"], "allow_fallbacks": false}}` (in its recorded options), as evidence whether the
  lifetime holds when the upstream cannot change; the chief's go (m-10723). A pinned run is never a manifest run (the
  site would pool it with the default route's row): it is in `excluded` as supplemental evidence, its `provider`
  option stated (ruling 2, m-10767).
- **Free models** (`:free`): OpenRouter allows 20 free requests a minute. The first free run
  (`baidu/ernie-5.5-flash-preview:free`, unpaced, 08:44) was refused during its priming (HTTP 429
  "free-models-per-min"); on the chief's go (m-10711 B) the free runs are **paced**, `--concurrency 1 --prime-pause
  3500` (one priming request every ~3.5 s), one free run at a time, after the big releases; Ernie got a new paced run
  (`…-paced`). Only a refusal that names OpenRouter's free limit leaves the remaining free ones; an upstream's 429
  ("Provider returned error") ends that run only.
- **OpenAI's `-pro` variants answer with ~8,900-token prompts** where the same request to the plain model counts
  ~2,400 (OpenRouter's reply; the probe sent the same ~2,500-token prefix): something in front of the model adds
  about 6,300 tokens. Their checks count as warm on the cached share of that whole prompt (e.g. 8,670 of 8,878 at the
  control). From 12:38 UTC the `-pro` runs not yet started were planned with 9,000 prompt tokens per request.
- **The money guard**, changed twice during the day (`status.py`): from 12:28 UTC `--enforce` stops runs only when
  the money spent comes within $0.75 of the stop, not when reservations alone pass it (a `-pro` run's grown worst
  case would otherwise have stopped it); from 12:50 UTC a running run reserves its worst case for its requests not
  yet sent, not its whole worst case less its spending; and the spent figure is the highest of the ledger,
  OpenRouter's per-reply figure and the key's usage. No run was stopped for money.
- **Runs at once**: up to 12 paid runs (20 from 10:21 UTC, when the money committed stayed far under the stop and runs that stay warm to 2 hours were holding the slots) and 1 free run (`status.py`, `MAX_PAID`), started 15 s apart so that their
  priming bursts (4 requests at a time) do not overlap. A run mostly waits; the number is held down by the money (below)
  and by the load on this Mac (the owner's working machine), not by OpenRouter's rate limit, which never refused a paid
  request for rate.
- **Probe version.** The probe's changes for this folder (the upstream reply fields, the reply id and the sample key in
  the usage log; HTTP 402 as a refusal) are commit `e0d1afb`, first named 0.3.3; `campaign-1-long` already had another
  0.3.3, so the version was renamed 0.3.4 (commit `5977b0b`, code unchanged). The run files that recorded "0.3.3" with this code (started before `5977b0b`, 09:07 UTC): `anthropic--claude-fable-5.2`, `baidu--ernie-5.5-flash-preview-free`, `deepseek--deepseek-v4.1-flash-1017`, `google--gemini-4-carbon`, `google--gemini-4-hydrogen`, `ibm-granite--granite-4.2-8b`, `inclusionai--ling-3.0-flash-vl`, `inclusionai--ling-3.1-flash`, `liquid--lfm-2.5-24b-a2b`, `meta--muse-ember`, `nex-agi--nex-n2.5-mini`, `nex-agi--nex-n2.5-pro`, `openai--gpt-6.2-astra`, `openai--gpt-6.2-sol`, `particle-ai--particle-1`, `qwen--qwen4-max`, `scaledown--extract`, `scaledown--summarize`, `tencent--hy4-flash`, `upstage--solar-mini4`; every later run records "0.3.4". The run files are not edited.
- **A larger prompt where the control read nothing** (the chief's decision, m-10759): a control that read 0 cached
  tokens at about 2,500 tokens may only mean the prompt is under that upstream's smallest cacheable size. Every model
  whose first run's control read 0 cached tokens gets one more run of its own (label `…-8k`) with
  `--prefix-tokens 8000`, the size of the repository's earlier larger-prompt Gemini row
  (`../cpa-latest-2026-11-06`, L1b, after L1's ~2.3k prompt was not cached; the older O4 / O5 used 5,000);
  everything else as the first run (pacing for the free one). `status.py` adds such a run to `plan.json` as soon as a
  first run ends that way, the dearest first, ahead of the first runs not yet started, with its own worst case (9,000
  prompt tokens per request). Its manifest entry carries `"prefix_tokens": 8000` in its options, as L1b's; no lifetime
  is asked, so it lands in the short profile like the first run (`scratch_build.py`). `manifest-entries-cold-control.json`
  lists every first run whose control read 0, with its larger-prompt run and what that showed. Where the larger
  prompt's control hit, only the larger-prompt run is a manifest run (the chief's ruling, m-10781): the ~2,500-token run
  is under `excluded` ("no cache read at about 2,500 tokens; the 8,000-token run shows the prompt was under the
  smallest cacheable size") and the larger run's note says the small prompt read nothing. The site would not keep the
  two apart by itself: `observed.json` gives them different options (`{}` and `{"prefix_tokens": 8000}`), so both are
  `latest`, but neither asks a lifetime, so `site/src/core/resolve.ts` puts both in the short profile of the same
  entry and their results would be pooled. Where both sizes read 0 (ScaleDown Summarize, Perceptron Mk1.5), both runs
  are listed, each noting it.
- **Runs that ended on an upstream's rate answer after answered checks** (the chief's ruling, m-10781, as round two's
  cut-off runs): listed as runs, the answered checks standing, with a note on how and where they ended; the build takes
  a run file of status `failed` by its checks. `google--gemini-4-carbon-8k` is the one (2.5 and 5 minutes answered,
  ended at 7.5 on HTTP 504 after Google AI Studio's 429). `inclusionai/ling-3.2-flash:free` stays excluded (its one
  answered check is at 5 minutes, not 2.5, and the build's rule for an evaluation needs 2.5); the paced Ernie run
  answered only its control.
- `scripts/build_observed.py`: commit `83b05bb` accepts a run dated from 14 November whose control missed (no checks);
  `main` carries the same rule from `campaign-1-long` (`f005ffa`, refined by `1444a55`); the assembler puts them
  together.

## Results

`results.md` (written by `summary.py`) has one row per run: the control, warm checks per age, warm through, first all
cold, the upstreams, the checks that crossed upstreams, the cost, and the entry's documented lifetime on providers.dev
on 2026-11-18: holds (every check up to it warm), contradicted only in the site's sense (fewer than half the checks
of an age at or below it hit), otherwise the misses as they are ("2 of 3 at 30m; all warm through 25m"). 

**The seven big releases** (warm through = every check of every age up to there warm; first all cold = the first age
with no warm check):

| Model | Control | Warm checks per age | Warm through | First all cold | Upstreams | Where it stands |
|---|---|---|---|---|---|---|
| `openai/gpt-6.2-sol` | warm | 3/3 to 10 min, 1/3 at 15 and 20, 3/3 at 25, 0/3 at 30 and 40 | 10 min | 30 min | Amazon Bedrock, OpenAI | the four misses at 15 and 20 min are the four checks primed on Bedrock and answered by OpenAI: in the entries, the crossings in its note |
| same, pinned to OpenAI | warm | 3/3 at every age to 30 min, 0/3 at 40 and 50 | **30 min** | 40 min | OpenAI | supplemental evidence, excluded (pinned) |
| `google/gemini-4-hydrogen` | **cold** (0 of 2,345) | – | – | – | Google | no observable cache with the default ~2,500-token prompt |
| `google/gemini-4-carbon` | **cold** (0 of 2,384) | – | – | – | Google, Google AI Studio | the control's last re-send fell back from Google (504) to Google AI Studio, the control missed and there is no timed check: excluded; its larger-prompt run failed (below) |
| `qwen/qwen4-max` | warm | 2/3 at 2.5 min, 3/3 from 5 to 20, 1/3 at 25, 2/3 at 30, 0/3 at 40 and 50 | none (2/3 at 2.5) | 40 min | Alibaba | in the entries |
| `meta/muse-ember` | warm | 3/3 to 15 min, 2/3 at 20, 3/3 at 25 and 30, 0/3 at 40, 1/3 at 50 min to 75 min, 3/3 at 90, 2/3 at 2 h | 15 min | 40 min | Google, Meta | 2h r3 primed on Google, answered by Meta, cold: in the entries, the crossing in its note |
| `anthropic/claude-fable-5.2` | warm | 3/3 at 2.5 and 5 min, 0/3 at 7.5 and 10 | **5 min** | 7.5 min | Anthropic, Azure, Google | in the entries; Anthropic's 5-minute default, as on Anthropic's API (`../direct-2026-11-17`) |
| `openai/gpt-6.2-astra` | warm | 3/3 to 25 min, 2/3 at 30, 0/3 at 40 and 50 | 25 min | 40 min | Azure, OpenAI | in the entries; providers.dev documents 30 min: 2 of 3 at 30 min, all warm through 25 (not a contradiction in the site's sense, which needs fewer than half the checks of an age to hit); no upstream change in that check |

providers.dev documented no lifetime for six of the seven on 2026-11-18; for GPT-6.2 Astra 30 minutes. Every other run
is in `results.md` with the same columns.

**Batch 2** adds 26 finished runs. Among them: Claude Sonnet 5.5 warm through 5 minutes, cold at 7.5 (documented 5
minutes: holds); the larger-prompt runs, where Gemini 4 Hydrogen's control was cached at ~7,500 tokens (5,461) but no
age was fully warm (2/3 at 2.5 min, 1/3 at 5, cold at 7.5), ScaleDown Summarize and Perceptron Mk1.5 read 0 again
(two runs each say no observable cache), and the two ternary-bonsai and LFM3 1.7B were cached at ~9,000 tokens but cold
at 2.5 minutes; long lifetimes on single upstreams (Nex N2.6 warm in every check to 2 hours, Ripple 65B through 90
minutes, Pareto 26.10 Preview through 1 hour, Aion 3.5 Mini through 50 minutes, GLM 5.3 FlashX and Qwen3.8 Max 0902
through 30 minutes, Flint v1.0 free through 40 minutes); and three models spread over several upstreams that crossed
(MiMo v2.6 Flash, Nemotron 3.5 Super VL, Beam 1.0), in the entries with their crossings in the note. Where a
larger-prompt run read 0 again (ScaleDown Summarize, Perceptron Mk1.5), both runs' notes say "no cache read observed
with about 2,500- and 8,000-token prompts" (ruling 5, m-10767).

**Batch 3** adds 30 finished runs. The larger-prompt runs of MiDM K 3.0 Pro (warm in every check to 2 hours at
~9,500 tokens), LFM 2.5 24B (through 1 hour), Nemotron 3.5 Super VL free (through 90 minutes) and
`~deepseek/deepseek-flash-latest` (2.5 minutes, then hit-or-miss to 2 hours over 9 upstreams, 2 crossings) all read
the cache: their first runs' zeros were the prompt size. OpenAI's models on OpenRouter hold OpenAI's 30 minutes when
OpenAI answers (GPT-6 Sol, the Luna, Terra and Sol `-pro` variants, `~gpt-luna-latest`, `~gpt-terra-latest`: warm
through 30, cold at 40); where Azure or Bedrock also answered (GPT-6.2 Sol Pro, `~gpt-sol-latest`) checks crossed and
missed. Long lifetimes: Hy4 and MiMo v2.6 Pro Ultraspeed warm to 2 hours (the latter one miss at 15 minutes), GLM 5.3
FlashX Legal, Pareto 26.10 and `~unbiased/pareto-latest` through 1 hour, Aion 3.5 through 50 minutes.

## Input windows, from a refusal only

For the four models whose two OpenRouter figures disagree (`context_length` / `top_provider.context_length`:
`xiaomi/mimo-v2.6-flash` 1,050,000 / 1,048,576, `nvidia/nemotron-3.5-super-vl` 1,048,576 / 262,144,
`xiaomi/mimo-v2.6-pro` 1,050,000 / 1,048,576, `deepseek/deepseek-v4-flash-vision-exp` 1,048,576 / 1,048,575):
after the model's cache run, one Chat Completions request of " hello" × 1,200,000 (about 1.2 million tokens), 16
output tokens, `transforms: []` (`window.py`, `windows.jsonl`, as `../logins-2026-11-17` recorded Fable's refusal).
No accepted request near a limit. Every refusal so far came from OpenRouter itself, before any upstream, and names
the endpoint's window; `manifest-entries.json` has a limits row for each (the window named, no accepted size, as
`../logins-2026-11-17`'s Fable row):

| Model | OpenRouter's figures (context_length / top_provider) | The refusal |
|---|---|---|
| `xiaomi/mimo-v2.6-flash` | 1,050,000 / 1,048,576 | "This endpoint's maximum context length is 1050000 tokens. However, you requested about 1800021 tokens (1800005 of text input, 16 in the output)" |
| `nvidia/nemotron-3.5-super-vl` | 1,048,576 / 262,144 | "… maximum context length is 1048576 tokens …" |
| `deepseek/deepseek-v4-flash-vision-exp` | 1,048,576 / 1,048,575 | "… maximum context length is 1048576 tokens …" |
| `xiaomi/mimo-v2.6-pro` | 1,050,000 / 1,048,576 | "… maximum context length is 1050000 tokens …" |

OpenRouter counted the 1.2 million " hello" as about 1.8 million tokens (its own estimate before tokenizing).

## Left out, and why

Failed runs, kept with their files and in `excluded` of `manifest-entries.json`:

- `baidu/ernie-5.5-flash-preview:free` (unpaced): HTTP 429 "Rate limit exceeded: free-models-per-min" during its
  priming. A paced run of it is planned.
- `inclusionai/ling-3.2-flash:free`, `liquid/lfm-3-1.7b:free` (paced): HTTP 429 "Provider returned error", "…is
  temporarily rate-limited upstream": the upstream's limit on the free model, not OpenRouter's free limit; that run
  only ended (the free runs went on).
- `scaledown/extract`: HTTP 400, the model needs a `response_format` of type `json_schema` (or ScaleDown's entity
  options): it takes no plain request.
- `meta/muse-spark-1.2-contributor`, `meta/muse-spark-1.3-contributor`: HTTP 404, "0 endpoints … available matching
  your guardrail restrictions and data policy … Paid model training violation (account settings)": the account's data
  policy excludes their only endpoint. A setting of the account, which this task does not change.

- `google/gemini-4-carbon`, the run with the larger prompt (`google--gemini-4-carbon-8k`): its control was cached
  (5,474 of 7,528), then at the 7.5-minute check OpenRouter answered HTTP 504 "The operation was aborted" after a 429
  of Google AI Studio ("temporarily rate-limited upstream"). The probe's `--stop-on-refusal` read the upstream's rate
  wording in that answer and ended the run, not retried: 2.5 min 1/3, 5 min 0/3, the four misses all checks crossing
  from Google to Google AI Studio. Not started again (the chief, m-10781); listed as a run with its answered checks
  and a note (above).
- `sakana/fugu-max`, `sakana/fugu-ultra-v2`: HTTP 403 "not available in your region: Sakana AI blocks requests
  originating from your location". Nothing measured.

- `thinkingmachines/inkling-2-small:free`: HTTP 403 "This model is not available in your region" (the paid
  `inkling-2-small` was measured). `baidu/ernie-5.5-flash-preview:free`, paced: HTTP 429 "…temporarily rate-limited
  upstream" after its control (warm, 2,304 of 2,413): the upstream's limit, as for Ling and LFM; no free runs are left.
- **Left out for money**: `openai/gpt-6.2-astra-pro` (worst case $7.94 with its ~9,000-token prompts; at 13:54 UTC
  nothing else ran and $15.10 was committed of $18) and `openai/gpt-6-astra-pro` (worst case $9.93; at 14:36 UTC,
  after the last run, $16.31 was spent). `~openai/gpt-astra-latest` (worst case $2.72) did fit and ran: warm through
  25 minutes, 0 of 3 at 30 (documented 30 minutes: contradicted in the site's sense), $1.21.

Runs whose entry waits for OpenRouter's generation record of their last replies (a few minutes late) are marked
"entry pending" in `results.md`. Nothing was left out for money up to batch 2; see above for batch 3.

## Money

`ledger.py` computes every request's cost from the usage the reply reported (`logs/*.usage.jsonl`) at OpenRouter's
price read before the run: uncached input at the input price, cache writes at the cache-write price (input where none
is listed), reads at the read price, output at the output price; OpenRouter's own figure for each reply
(`usage.cost`) is summed beside it. The key's own usage (`GET /api/v1/key`) is read before the first run and at every
launch pass (`key-readings.jsonl`). Stop at $18, by the higher of the two. Before a run starts, its worst case (87
requests of 3,000 prompt tokens at the higher of the input and cache-write price, 32 output tokens each) must fit in
what is left to $18 after the spent money, what the running runs may still cost (their worst case, from their own
largest prompt and output so far, less what they spent) and the window requests still owed. 

At batch 1 (10:51 UTC, runs still going): ledger **$6.07**, OpenRouter's own per-reply figure $6.09, the key's usage **$6.09** (`key-readings.jsonl`; the two OpenRouter figures run about 0.3 % above the ledger, the stop takes the higher). Per model and run in `ledger.md`; the seven big ones: Fable 5.2 $2.13, GPT-6.2 Astra $1.23, GPT-6.2 Sol $0.63 ($0.32 unpinned + $0.30 pinned), Qwen4 Max $0.23, Muse Ember $0.02, Gemini 4 Carbon $0.01, Gemini 4 Hydrogen $0.01.

At batch 2 (12:02 UTC, runs still going): ledger **$11.39**, OpenRouter's own per-reply figure $11.47, the key's usage
**$11.47**. The difference is mostly the `~…-latest` aliases and `ricursiveai/ripple-65b-preview`, which OpenRouter
billed above the price its model list gives for them (the alias at the price of the model it resolved to); the stop
takes the higher figure. The larger-prompt runs of the two Gemini cost $0.75 (Carbon) and $0.61 (Hydrogen).

At batch 3 (13:57 UTC, one run still going): ledger **$16.05**, OpenRouter's own figure **$16.15**, the key's usage
**$16.15**. `~openai/gpt-astra-latest`, still running, spent $1.04 of it on its priming; what it may still cost is
reserved (about $1.4 at most).

**At the end (14:41 UTC): ledger $16.22, OpenRouter's own per-reply figure $16.31, the key's usage $16.31** of the
$20 limit, under the $18 stop. Readings of the key before the first run (08:40, $0), at every launch pass and at the
end are in `key-readings.jsonl` and `ledger.md`. 5,427 requests. The dearest models: Claude Fable 5.2 $2.13, GPT-6.2
Astra $1.23, `~gpt-astra-latest` $1.21, GPT-6.2 Sol Pro $0.77, Gemini 4 Carbon $0.76 (both runs), GPT-6 Sol Pro $0.75,
GPT-6.1 Sol Pro $0.72, Qwen3.8 Max Prime $0.70, GPT-6.2 Sol $0.63 (both runs), Gemini 4 Hydrogen $0.62 (both runs);
every model and run in `ledger.md`.

## Picking up

Nothing runs: every probe and the supervisor have ended (the supervisor ended by itself at 14:36 UTC, nothing left
to start). `python3 results/openrouter-2026-11-18/status.py` rebuilds from the files what has finished, what runs (a live pid of
`logs/<label>.pid` whose command names the label) and what is left, the money and the upstreams; it sends nothing. The
supervisor's pid is in `logs/supervisor.pid`; if it is gone, start it again (the command is in `supervise.py`). A run
cut off (pid gone, no final file) is kept as it is and not resumed. `summary.py` writes `results.md`,
`manifest-entries.json`, the cold-control list and the (now empty) upstream-changed list; `scratch_build.py` proves the entries against `main`.

## Files

- `<label>-<time>.json` / `.md`: the probe's result of each run (the failed ones included).
- `logs/<label>.usage.jsonl`: one line per reply (time, label, model, sample key, status, usage as reported, reply id,
  stop reason; never a header, the prompt or the answer), added with `git add -f`; `logs/windows.usage.jsonl` the same
  for the window requests. Not in the repository: `logs/<label>.log`, `.pid`, `.dry-run.txt`, `launches.txt`,
  `supervisor.log`.
- `plan.py`, `plan.json`: the list and the order (`plan.json` edited by hand for the paced free runs and the pinned Sol
  run, its `note` says so); `sources/`: the website's entries and OpenRouter's model list as read.
- `run.sh`, `key.py`, `key_usage.py`, `status.py`, `supervise.py` (the running supervisor was started from the
  version before its log filter also kept `added` lines; nothing else differs), `decisions.json` (left out, refusals seen),
  `offered.jsonl`, `upstream.py`, `upstreams.jsonl`, `window.py`, `windows.jsonl`.
- `ledger.py`, `ledger.jsonl`, `ledger.md`, `key-readings.jsonl`: the cost.
- `summary.py`, `results.md`, `results.json`, `manifest-entries.json`, `manifest-entries-upstream-changed.json`,
  `scratch_build.py`.
