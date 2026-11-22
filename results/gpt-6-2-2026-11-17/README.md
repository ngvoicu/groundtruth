# GPT-6.2 Sol and GPT-6.2 Astra on the OpenAI API, straight with the owner's key: cache lifetimes and window refusals, 2026-11-17

OpenAI released GPT-6.2 Sol and GPT-6.2 Astra on 2026-11-17; the owner's API key lists both (`GET /v1/models`, read at
20:48 UTC). Both were measured the way `../direct-2026-11-17` measured `gpt-6-sol`, `gpt-6-astra`, `gpt-6-luna` and
`gpt-6.1-terra`: plain probe (`src/cli.ts`, 0.3.2 with `--usage-log`) straight to `https://api.openai.com/v1`, no proxy
in between (route `openai-api`, client `direct`). One OpenAI API key (the owner's, read by `key.py` from his
Provimux configuration into the probe's environment, never written). Responses format, a `prompt_cache_key` per
sample, about 2,400-token prompts, nothing asked about caching, the standard schedule (to 2 hours, stopping after two
fully cold ages), 3 samples per age, a control first. `run.sh` holds both commands; Sol was started at 20:49:21 UTC,
Astra at 20:49:26.

## Cache lifetime (default, nothing asked about caching)

| Run | Model | Control | Warm at each age | Lifetime | Documented |
|---|---|---|---|---|---|
| `oa-sol62` | `gpt-6.2-sol` | warm (2,419 of 2,422 cached) | 3/3 at every age from 2.5 to 30 min; 0/3 at 40 and 50 min | **30 – 40 min** | 30 min minimum: holds |
| `oa-astra62` | `gpt-6.2-astra` | warm (2,356 of 2,359 cached) | the same | **30 – 40 min** | 30 min minimum: holds |

Every check ran within 6.3 s of its age; none was late, none failed, no sample had to be primed again (74 requests
per run: control 2, priming 42, checks 30). The same result as the four older GPT-6 models on the same day.

**What OpenAI reported writing** (`logs/*.usage.jsonl`): every written token of both models under the 30-minute tier
(`cache_write_tokens_details.ttl_30m_tokens`; `ttl_12h_tokens` 0 on every reply). Each cold check at 40 and 50 minutes
was billed as a new 30-minute write.

**What OpenAI documents** (read 2026-11-17, about 20:50 UTC). The prompt caching guide
(<https://developers.openai.com/api/docs/guides/prompt-caching>), for GPT-5.6 and later: `"30m"` (default) is a
"Minimum lifetime" of 30 minutes, and "OpenAI may retain entries longer than the requested minimum"; "Omitting both
settings preserves the default \"30m\" behavior." The guide names GPT-6.2 Sol and GPT-6.2 Astra among the models whose
cache reads cost 0.05× input "regardless of the selected lifetime". The two model pages
(<https://developers.openai.com/api/docs/models/gpt-6.2-sol>, `.../gpt-6.2-astra`) say: "The cache write price is for 30
minutes of retention. A 12-hour cache write costs $5 [Astra: $20] per million tokens for short-context requests at
Standard pricing." Nothing model-specific beyond that.

## Input window: one refusal per model (`refusal.py`, `refusal.jsonl`)

One request per model, `"Reply with just OK." + " hello" × 1,100,000` (the request of `harness/limits.py`, Responses
format, a 16-token reply, low effort), above both figures OpenAI documents for the two models (maximum input 922,000,
context window 1,050,000). Sol first; Astra was sent only once Sol had been refused. No request near the limit was
sent (on Astra a request of about 920,000 tokens would cost about $15 at the long-context input price of $16 per
million tokens).

| Model | Sent (UTC) | Answer |
|---|---|---|
| `gpt-6.2-sol` | 20:49:07 | HTTP 400 `invalid_request_error`, code `context_length_exceeded`, param `input`: "Your input exceeds the context window of this model. Please adjust your input and try again." |
| `gpt-6.2-astra` | 20:49:12 | the same |

**Neither refusal names a figure**, so the window is left open: no limits row (a row needs a window the answer names,
or an accepted size). The refusal only says that about 1,100,000 tokens are over the window of both models, which
agrees with what OpenAI documents. Both refusals reported no usage and cost nothing. The model pages (read 2026-11-17)
give for both: "1,050,000 context window", "Maximum input tokens: 922,000", "128,000 max output tokens".

## models.dev (read 2026-11-17, 20:47 UTC, `https://models.dev/api.json`, provider `openai`)

Both entries exist: `openai/gpt-6.2-sol` (input $2, output $10, cache read $0.10, cache write $2.50; context 1,050,000,
input 922,000, output 128,000; released 2026-11-17) and `openai/gpt-6.2-astra` (input $8, output $40, cache read $0.40,
cache write $10; the same limits and date); above 272K tokens both list the doubled rates. The runs are entered on
those two entries (`manifest-entries.json`).

## Left out, and why

Nothing of what was run. Not in this part: the 12-hour setting (`prompt_cache_options.ttl: "12h"`), the `-pro` and
`-fast` variants, anything through the Codex login, and any accepted request near the window.

## Money

`ledger.py` computes the cost of every request from the usage the reply reported (`logs/*.usage.jsonl`) at the prices
of OpenAI's pricing page (<https://developers.openai.com/api/docs/pricing>, Standard, read 2026-11-17 at about 20:50
UTC; the model pages and models.dev give the same): uncached input, 30-minute writes at 1.25× input, cache reads,
output; the long-context row above 272K input tokens (no accepted request reached it). `ledger.jsonl` has every
request with its running total, `ledger.md` the sums. **Total $1.51 of the $12 stop** (150 requests):
`gpt-6.2-sol` $0.30, `gpt-6.2-astra` $1.21, the two refusals $0.

| Model | Input | Cached input | 30m write | 12h write | Output |
|---|---|---|---|---|---|
| `gpt-6.2-sol` | $2.00 | $0.10 | $2.50 | $5.00 | $10.00 |
| `gpt-6.2-astra` | $8.00 | $0.40 | $10.00 | $20.00 | $40.00 |

## Files

- `oa-sol62-…json` / `.md`, `oa-astra62-…json` / `.md`: the probe's result of each run.
- `refusal.jsonl`: the two window requests, in the row format of `harness/limits.py` (`named`: the figure the message
  names, `null` for both). `refusal.py`: how they were sent.
- `logs/oa-sol62.usage.jsonl`, `logs/oa-astra62.usage.jsonl`, `logs/refusal.usage.jsonl`: one line per reply (time, run
  label, model, status, usage as reported; never a header, the prompt or the answer), 150 lines. `ledger.py` reads
  these; run in a clean copy it rewrites `ledger.jsonl` and `ledger.md` as committed. They are committed with
  `git add -f`: `results/**/logs/` stays ignored for every other folder.
- Not in the repository (they stay with the measuring task, git-ignored): `logs/<run>.log` and `logs/refusal.log`, the
  scripts' output; `logs/<run>.dry-run.txt`, the dry runs made before; `logs/<run>.pid` and `logs/launches.txt`, the
  process of each run and when it started.
- `run.sh`, `key.py`: how the runs were started. `ledger.py`, `ledger.jsonl`, `ledger.md`: the cost.
- `manifest-entries.json`: the entries these runs add to `observed/manifest.json` (not applied here).
