# OpenAI and Anthropic APIs, straight with the owner's keys: cache lifetimes, 2026-11-17

Plain probe (`src/cli.ts`, 0.3.0 with `--usage-log`) straight to `https://api.openai.com/v1` and
`https://api.anthropic.com/v1`, no proxy in between (route `openai-api` / `anthropic-api`, client `direct`). One OpenAI
API key, one Anthropic API key (the owner's, read by `key.py` from his Provimux configuration into the probe's
environment, never written). 3 samples per age, every run starting with the control and 2.5, 5 and 7.5 minutes.
`run.sh` holds every run's command; all were started between 12:19 and 12:24 UTC.

- **OpenAI**: Responses format, a `prompt_cache_key` per sample, about 2,400-token prompts, nothing asked about caching,
  the standard schedule (to 2 hours, stopping after two fully cold ages), as `../openai-direct-2026-11-15`.
- **Anthropic**: Messages format, the prefix marked with `cache_control`, about 4,300 – 4,450-token prompts. The default
  cache (no ttl) checked at 2.5, 5, 7.5, 10 and 15 minutes; the 1-hour cache (`ttl: "1h"`) at 2.5 – 50 minutes, 1 hour,
  65 and 75 minutes, as `../claude-login-2026-11-16`.

| Run | Model | Request | Control | Warm at each age | Lifetime | Documented |
|---|---|---|---|---|---|---|
| `oa-luna` | `gpt-6-luna` | default | warm | 3/3 from 2.5 to 30 min; 0/3 at 40 and 50 min | **30 – 40 min** | 30 min: holds |
| `oa-terra` | `gpt-6.1-terra` | default | warm | the same | **30 – 40 min** | 30 min: holds |
| `oa-sol6` | `gpt-6-sol` | default | warm | the same | **30 – 40 min** | 30 min: holds |
| `oa-astra` | `gpt-6-astra` | default | warm | the same | **30 – 40 min** | 30 min: holds |
| `oa-chat-latest` | `chat-latest` | default | warm | 3/3 at every age from 2.5 min to 2 h | **≥ 2 h** (never cold) | none documented: the run gives the first value |
| `an-haiku-list-5m` | `claude-haiku-5-5` | no ttl, `--filler list` | warm | 3/3 at 2.5 and 5 min; 0/3 at 7.5 and 10 min | **5 – 7.5 min** | 5 min: holds |
| `an-sonnet-5m` | `claude-sonnet-5-5` | no ttl | warm | the same | **5 – 7.5 min** | 5 min: holds |
| `an-opus-5m` | `claude-opus-5-5` | no ttl | warm | the same | **5 – 7.5 min** | 5 min: holds |
| `an-fable-5m` | `claude-fable-5-2` | no ttl | warm | the same | **5 – 7.5 min** | 5 min: holds |
| `an-haiku-list-1h` | `claude-haiku-5-5` | `ttl: "1h"`, `--filler list` | warm | 3/3 from 2.5 min to 1 h; 0/3 at 65 and 75 min | **1 h – 65 min** | 1 h: holds |
| `an-sonnet-1h` | `claude-sonnet-5-5` | `ttl: "1h"` | warm | the same | **1 h – 65 min** | 1 h: holds |
| `an-opus-1h` | `claude-opus-5-5` | `ttl: "1h"` | warm | the same | **1 h – 65 min** | 1 h: holds |
| `an-fable-1h` | `claude-fable-5-2` | `ttl: "1h"` | warm | the same | **1 h – 65 min** | 1 h: holds |

Every check ran within 6 s of its age; none was late, none failed, no sample had to be primed again.

**What the providers reported writing** (`logs/*.usage.jsonl`): OpenAI put every written token of the four GPT-6
models under its 30-minute tier (`cache_write_tokens_details.ttl_30m_tokens`, `ttl_12h_tokens` 0). `chat-latest`
reported cache hits (2,176 or 2,304 tokens, in blocks of 128) but no cache write at all (`cache_write_tokens` 0 on every request); OpenAI lists no cache-write
price for it. Anthropic put every written token of the default runs under `ephemeral_5m_input_tokens` and every one
of the 1-hour runs under `ephemeral_1h_input_tokens`.

## Left out, and why

- **`an-haiku-5m`**: Claude Haiku 5.5 with the default filler of random words. Anthropic answered with HTTP 200 and
  `stop_reason: "refusal"` (`stop_details` category `bio`) to 4 of the 17 requests sent (the cache was written and read
  even so). Stopped by hand after the control and the priming, at 12:20 UTC, so as not to send more such prompts on the
  owner's account; its partial file is kept (`an-haiku-5m-…partial.json`). Measured instead with the probe's
  `--filler list` (plain numbered sentences), as `../claude-login-2026-11-16` (CS7, CS8) did through the Claude login.
  The filler changes only the words of the prompt, not how it is cached.
- **`gpt-audio-1.5`** takes no plain text request: the Responses API refuses the model (`oa-audio`, HTTP 400
  `model_not_found`, "not supported with the Responses API"), and Chat Completions refuses a request with no audio
  (`oa-audio-chat`, HTTP 400 "This model requires that either input content or output modality contain audio").
  Nothing measured.
- **`gpt-6-cyber`, `gpt-daybreak-blue-latest`, `gpt-daybreak-red-latest`**: the key cannot call them. None is in the
  key's model list, and the control of each (`oa-cyber`, `oa-daybreak-blue`, `oa-daybreak-red`) got HTTP 404
  `model_not_found`. Nothing measured.
- **`gpt-6.1-sol`** was measured on 2026-11-15 (`../openai-direct-2026-11-15`), and the 12-hour setting is not in this
  wave.

The failed runs' files are kept; none of them is in `manifest-entries.json`. Their `excluded` entries are.

## Money

`ledger.py` computes the cost of every request from the usage the reply reported (`logs/*.usage.jsonl`) at the prices
of OpenAI's and Anthropic's pricing pages (read 2026-11-17, the same as providers.dev shows): uncached input, cache
writes at their own tier price (OpenAI 30-minute write 1.25× input; Anthropic 5-minute write 1.25×, 1-hour write 2×),
cache reads at the read price, output. `ledger.jsonl` has every request with its running total, `ledger.md` the sums.
**Total $10.01 of the $40 stop** (840 requests): OpenAI $2.61, Anthropic $7.40.

| Model | USD | | Model | USD |
|---|---|---|---|---|
| `gpt-6-luna` | 0.016 | | `claude-haiku-5-5` (both runs and the stopped one) | 0.064 |
| `gpt-6.1-terra` | 0.152 | | `claude-sonnet-5-5` | 1.053 |
| `gpt-6-sol` | 0.309 | | `claude-opus-5-5` | 2.107 |
| `chat-latest` | 0.597 | | `claude-fable-5-2` | 4.172 |
| `gpt-6-astra` | 1.541 | | | |

The refused requests (`gpt-audio-1.5`, `gpt-6-cyber`, the two Daybreak models) reported no usage and cost nothing. Before
starting, the worst case of every run (every request billed as a cache write) came to about $5 on OpenAI and $13 on
Anthropic ($7.20 of it Claude Fable 5.2), so every run fitted the stop; Fable was started last.

## Files

- `<run>-<time>.json` / `.md`: the probe's result of each run (the failed ones included).
- `logs/<run>.usage.jsonl`: one line per reply (time, run label, model, status, usage as reported, stop reason and stop
  details; never a header, the prompt or the answer), 840 lines, 17 of them `an-haiku-5m` (4 with
  `stop_reason: "refusal"`, category `bio`). `ledger.py` reads these; run in a clean copy it rewrites `ledger.jsonl`
  and `ledger.md` as committed. They are committed with `git add -f`, as is `an-haiku-5m-…partial.json`: `results/**/logs/`
  and `*.partial.json` stay ignored for every other folder.
- Not in the repository (they stay with the measuring task, git-ignored): `logs/<run>.log`, the probe's log;
  `logs/<run>.dry-run.txt`, the dry run made before; `logs/<run>.pid` and `logs/launches.txt`, the process of each run
  and when it started.
- `run.sh`, `key.py`: how the runs were started. `ledger.py`, `ledger.jsonl`, `ledger.md`: the cost.
- `manifest-entries.json`: the entries these runs add to `observed/manifest.json` (not applied here).
