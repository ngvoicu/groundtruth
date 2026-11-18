# OpenRouter's chat models released since 2026-08-17: cache lifetimes, straight with a key of its own, 2026-11-18

**State of this folder: batch 1 (the seven big releases), pushed 2026-11-18 about 10:55 UTC (Muse Ember's entry and the others' as in `manifest-entries.json` and the separate list), while the measuring goes on.** Runs still running or not yet
started are listed as such in `results.md`; a run gets its entry only once it has finished. The folder is complete in
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
  priming by that key. A run in which a check (the control included) was answered by another upstream than its
  sample's priming is **not in `manifest-entries.json`**: it is in `manifest-entries-upstream-changed.json`, with the
  entry it would have and the checks that crossed upstreams and their outcome, for the reviewer (the chief's decision,
  m-10723: such a check says nothing about one upstream's lifetime but is what a caller of the default route gets).
- **GPT-6.2 Sol pinned to OpenAI** (`openai--gpt-6.2-sol-pinned-openai`): a second Sol run with
  `{"provider": {"order": ["openai"], "allow_fallbacks": false}}` (in its recorded options), as evidence whether the
  lifetime holds when the upstream cannot change; the chief's go (m-10723), in the separate list too.
- **Free models** (`:free`): OpenRouter allows 20 free requests a minute. The first free run
  (`baidu/ernie-5.5-flash-preview:free`, unpaced, 08:44) was refused during its priming (HTTP 429
  "free-models-per-min"); on the chief's go (m-10711 B) the free runs are **paced**, `--concurrency 1 --prime-pause
  3500` (one priming request every ~3.5 s), one free run at a time, after the big releases; Ernie got a new paced run
  (`…-paced`). Only a refusal that names OpenRouter's free limit leaves the remaining free ones; an upstream's 429
  ("Provider returned error") ends that run only.
- **Runs at once**: up to 12 paid runs (20 from 10:21 UTC, when the money committed stayed far under the stop and runs that stay warm to 2 hours were holding the slots) and 1 free run (`status.py`, `MAX_PAID`), started 15 s apart so that their
  priming bursts (4 requests at a time) do not overlap. A run mostly waits; the number is held down by the money (below)
  and by the load on this Mac (the owner's working machine), not by OpenRouter's rate limit, which never refused a paid
  request for rate.
- **Probe version.** The probe's changes for this folder (the upstream reply fields, the reply id and the sample key in
  the usage log; HTTP 402 as a refusal) are commit `e0d1afb`, first named 0.3.3; `campaign-1-long` already had another
  0.3.3, so the version was renamed 0.3.4 (commit `5977b0b`, code unchanged). The run files that recorded "0.3.3" with this code (started before `5977b0b`, 09:07 UTC): `anthropic--claude-fable-5.2`, `baidu--ernie-5.5-flash-preview-free`, `deepseek--deepseek-v4.1-flash-1017`, `google--gemini-4-carbon`, `google--gemini-4-hydrogen`, `ibm-granite--granite-4.2-8b`, `inclusionai--ling-3.0-flash-vl`, `inclusionai--ling-3.1-flash`, `liquid--lfm-2.5-24b-a2b`, `meta--muse-ember`, `nex-agi--nex-n2.5-mini`, `nex-agi--nex-n2.5-pro`, `openai--gpt-6.2-astra`, `openai--gpt-6.2-sol`, `particle-ai--particle-1`, `qwen--qwen4-max`, `scaledown--extract`, `scaledown--summarize`, `tencent--hy4-flash`, `upstage--solar-mini4`; every later run records "0.3.4". The run files are not edited.
- `scripts/build_observed.py`: commit `83b05bb` accepts a run dated from 14 November whose control missed (no checks);
  `main` carries the same rule from `campaign-1-long` (`f005ffa`, refined by `1444a55`); the assembler puts them
  together.

## Results

`results.md` (written by `summary.py`) has one row per run: the control, warm checks per age, warm through, first all
cold, the upstreams, the checks that crossed upstreams, the cost, and the entry's documented lifetime on providers.dev
on 2026-11-18 (holds, contradicted, by how much). 

**The seven big releases** (warm through = every check of every age up to there warm; first all cold = the first age
with no warm check):

| Model | Control | Warm checks per age | Warm through | First all cold | Upstreams | Where it stands |
|---|---|---|---|---|---|---|
| `openai/gpt-6.2-sol` | warm | 3/3 to 10 min, 1/3 at 15 and 20, 3/3 at 25, 0/3 at 30 and 40 | 10 min | 30 min | Amazon Bedrock, OpenAI | the four misses at 15 and 20 min are the four checks primed on Bedrock and answered by OpenAI: separate list |
| same, pinned to OpenAI | warm | 3/3 at every age to 30 min, 0/3 at 40 and 50 | **30 min** | 40 min | OpenAI | separate list (pinned) |
| `google/gemini-4-hydrogen` | **cold** (0 of 2,345) | – | – | – | Google | no observable cache with the default ~2,500-token prompt |
| `google/gemini-4-carbon` | **cold** (0 of 2,384) | – | – | – | Google, Google AI Studio | the control's last re-send fell back from Google (504) to Google AI Studio: separate list |
| `qwen/qwen4-max` | warm | 2/3 at 2.5 min, 3/3 from 5 to 20, 1/3 at 25, 2/3 at 30, 0/3 at 40 and 50 | none (2/3 at 2.5) | 40 min | Alibaba | in the entries |
| `meta/muse-ember` | warm | 3/3 to 15 min, 2/3 at 20, 3/3 at 25 and 30, 0/3 at 40, 1/3 at 50 min to 75 min, 3/3 at 90, 2/3 at 2 h | 15 min | 40 min | Google, Meta | 2h r3 primed on Google, answered by Meta, cold: separate list |
| `anthropic/claude-fable-5.2` | warm | 3/3 at 2.5 and 5 min, 0/3 at 7.5 and 10 | **5 min** | 7.5 min | Anthropic, Azure, Google | in the entries; Anthropic's 5-minute default, as on Anthropic's API (`../direct-2026-11-17`) |
| `openai/gpt-6.2-astra` | warm | 3/3 to 25 min, 2/3 at 30, 0/3 at 40 and 50 | 25 min | 40 min | Azure, OpenAI | in the entries; providers.dev documents 30 min: **contradicted**, one of three cold at 30 min (no upstream change in that check) |

providers.dev documented no lifetime for six of the seven on 2026-11-18; for GPT-6.2 Astra 30 minutes. Every other run
is in `results.md` with the same columns.

## Input windows, from a refusal only

For the four models whose two OpenRouter figures disagree (`context_length` / `top_provider.context_length`:
`xiaomi/mimo-v2.6-flash` 1,050,000 / 1,048,576, `nvidia/nemotron-3.5-super-vl` 1,048,576 / 262,144,
`xiaomi/mimo-v2.6-pro` 1,050,000 / 1,048,576, `deepseek/deepseek-v4-flash-vision-exp` 1,048,576 / 1,048,575):
after the model's cache run, one Chat Completions request of " hello" × 1,200,000 (about 1.2 million tokens), 16
output tokens, `transforms: []` (`window.py`, `windows.jsonl`, as `../logins-2026-11-17` recorded Fable's refusal).
No accepted request near a limit. 

None sent yet at batch 1 (each comes after its model's cache run).

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

Runs whose entry waits for OpenRouter's generation record of their last replies (a few minutes late) are marked
"entry pending" in `results.md`. Nothing was left out for money at batch 1.

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

## Picking up

`python3 results/openrouter-2026-11-18/status.py` rebuilds from the files what has finished, what runs (a live pid of
`logs/<label>.pid` whose command names the label) and what is left, the money and the upstreams; it sends nothing. The
supervisor's pid is in `logs/supervisor.pid`; if it is gone, start it again (the command is in `supervise.py`). A run
cut off (pid gone, no final file) is kept as it is and not resumed. `summary.py` writes `results.md`,
`manifest-entries.json` and the separate list; `scratch_build.py` proves the entries against `main`.

## Files

- `<label>-<time>.json` / `.md`: the probe's result of each run (the failed ones included).
- `logs/<label>.usage.jsonl`: one line per reply (time, label, model, sample key, status, usage as reported, reply id,
  stop reason; never a header, the prompt or the answer), added with `git add -f`; `logs/windows.usage.jsonl` the same
  for the window requests. Not in the repository: `logs/<label>.log`, `.pid`, `.dry-run.txt`, `launches.txt`,
  `supervisor.log`.
- `plan.py`, `plan.json`: the list and the order (`plan.json` edited by hand for the paced free runs and the pinned Sol
  run, its `note` says so); `sources/`: the website's entries and OpenRouter's model list as read.
- `run.sh`, `key.py`, `key_usage.py`, `status.py`, `supervise.py`, `decisions.json` (left out, refusals seen),
  `offered.jsonl`, `upstream.py`, `upstreams.jsonl`, `window.py`, `windows.jsonl`.
- `ledger.py`, `ledger.jsonl`, `ledger.md`, `key-readings.jsonl`: the cost.
- `summary.py`, `results.md`, `results.json`, `manifest-entries.json`, `manifest-entries-upstream-changed.json`,
  `scratch_build.py`.
