# Input limits, 2026-11-16

Requests through a local CLIProxyAPI that serves every model under its own name (no plugin, no pools, no aliases):
`"Reply with just OK." + " hello" × N`, a 16-token reply. A refusal is free, so each model starts above the window
its vendor lists, then just below it; only accepted requests cost quota. Each id below is served by one login only
(Meta's `muse-…` ids by the Meta login, `devin/…` ids by the Devin login), so no pinning was needed. Rows:
`limits.jsonl` (format of `harness/limits.py`; "Input" is N, the tokens counted by the provider are in
`promptTokens`).

## Meta (Muse Code login): 1,048,576 tokens, shared by input and output

`harness/limits.py --format chat --hi 1050000 --no-output`, as `muse-wonder-1.0` on 2026-11-08 (`../limits-2026-11-08`).
The refusal names the window; one request just under it was accepted.

| Model | Listed window | Input | Answer | Counted tokens |
|---|---|---|---|---|
| `muse-ember-1.0` | 1,048,576 | 1,050,000 | refused: "The input (1050182 tokens) exceeds the model's context window of 1048576 tokens." | |
| | | 1,047,576 | accepted | 1,047,604 |
| `muse-spark-1.3` | 1,048,576 | 1,050,000 | refused: "The input (1050185 tokens) exceeds the model's context window of 1048576 tokens." | |
| | | 1,047,576 | accepted | 1,047,604 |

The output limit was not tested.

## Devin: every window as listed, except GPT (about 911K to 923K)

`devin_walk.py` (Chat Completions format): one request about 20,000 tokens above the window in Devin's own model list,
then one just under it, walking down by 2.5 % of the window while refused, then halving the gap; at most two accepted
requests per model, and a quota or rate refusal would have stopped the whole walk (none came). Every refusal is
Devin's `400 invalid_argument: There is an issue with this request, please try a different model.`: it names no
limit. Claude's tokenizer counts two tokens per " hello", so Claude requests used half the N.

| Model | Listed window | Accepted (tokens counted) | Smallest refused N | Requests (accepted) |
|---|---|---|---|---|
| `devin/glm-5-3` | 1,048,576 | 1,047,470 | 1,052,451 | 4 (1) |
| `devin/deepseek-v4-1-flash-1017` | 1,048,576 | 1,047,489 | 1,052,451 | 4 (1) |
| `devin/deepseek-v4-pro` | 1,048,576 | 1,047,542 | 1,052,451 | 4 (1) |
| `devin/gemini-4-argon` | 1,048,576 | 1,047,490 | 1,052,451 | 4 (1) |
| `devin/gpt-6-1-terra` | 1,000,000 | 911,390 | 923,500 | 7 (2) |
| `devin/gpt-6-astra` | 1,000,000 | 911,390 | 923,500 | 7 (2) |
| `devin/gpt-6-luna` | 1,000,000 | 911,390 | 923,500 | 7 (2) |
| `devin/claude-haiku-5-5` | 1,000,000 | 999,072 | 501,937 (≈ 1,004,446 tokens) | 4 (1) |
| `devin/claude-sonnet-5-5` | 1,000,000 | 999,072 | 501,937 (≈ 1,004,446 tokens) | 4 (1) |
| `devin/claude-opus-5-5` | 1,000,000 | 999,072 | 501,937 (≈ 1,004,446 tokens) | 4 (1) |

GLM-5.3, both DeepSeek models and Gemini 4 Argon accept their listed 1,048,576 and refuse about 4,000 tokens more.
The three Claude models accept 999,072 and refuse about 1,004,446 (the token count of a refused request is worked out
from the accepted one: 2 tokens per " hello" plus 572). GPT-6.1 Terra, GPT-6 Astra and GPT-6 Luna accept 911,390 and
refuse 923,500 although Devin lists 1,000,000: the same ~922K input limit as GPT-6.1 Sol on Devin (915,390 accepted,
925,000 refused, `../limits-2026-11-08`) and as these models on the ChatGPT plan.

## swe-2 on Devin: no edge, not published

Devin lists a 262,000-token window. The walk of `../limits-2026-11-13` found no refusal up to 930K, and a request
that needs both ends of its input (a code word before the filler and one after it; the answer must name both) got no
answer at 250K and 300K. The same both-ends request was sent again (`devin_walk.py --recall`, Responses format, low
effort, five minutes each):

| Filler | Output tokens allowed | Answer |
|---|---|---|
| 20,000 | 16 | status 200, empty reply |
| 50,000 | 16 | status 200, empty reply |
| 100,000 | 16 | status 200, empty reply |
| 150,000 | 16 | status 200, empty reply |
| 200,000 | 16 | status 200, empty reply |
| 20,000 | 256 | "APRICOT WALNUT" in 1.7 s (20,493 tokens) |
| 200,000 | 256 | "APRICOT WALNUT" in 1.8 s (200,497 tokens) |
| 300,000 | 256 | "APRICOT WALNUT" in 8.7 s (300,499 tokens) |

The first five asked for 16 output tokens, which the model's reasoning used up, so they show nothing. With 256 it
named both words at every size tried, 300,499 tokens included, which is above its listed window and a size that got
no answer three days earlier. That was the eighth and last request allowed, so there is still no edge: kept as a
record, **not** in `observed.json`. Rows: `swe-2-recall.jsonl` (the `maxOutput` rows also record the response's
status and output token count).
