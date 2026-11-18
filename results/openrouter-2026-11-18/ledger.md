# Ledger

Computed by `ledger.py` from the usage each reply reported (`logs/*.usage.jsonl`), at OpenRouter's prices read before each run (`offered.jsonl`; `sources/openrouter-models.json` otherwise). Every request is in `ledger.jsonl` with its tokens, upstream, price, OpenRouter's own cost figure and the running total.

**Total: $6.0743** by the ledger (OpenRouter's own per-reply `usage.cost` summed: $6.0946), 2959 requests, stop at $18.

What OpenRouter reported as used by the key (`GET /api/v1/key`, `key-readings.jsonl`):

| At (UTC) | Usage USD | Limit | Note |
|---|---|---|---|
| 2026-11-18T08:38:00Z | 0 | 20 | before the first run (key check only) |
| 2026-11-18T08:40:45Z | 0 | 20 | before the first run |
| 2026-11-18T08:40:45Z | 0 | 20 | status.py --launch pass |
| 2026-11-18T08:42:30Z | 0.2534091 | 20 | status.py --launch pass |
| 2026-11-18T08:50:10Z | 3.414910707 | 20 | status.py --launch pass |
| 2026-11-18T08:57:21Z | 3.715359885 | 20 | status.py --launch pass |
| 2026-11-18T09:07:43Z | 3.772089561 | 20 | status.py --launch pass |
| 2026-11-18T09:12:15Z | 3.805772321 | 20 | status.py --launch pass |
| 2026-11-18T09:17:59Z | 4.152340265 | 20 | status.py --launch pass |
| 2026-11-18T09:21:49Z | 4.175853027 | 20 | status.py --launch pass |
| 2026-11-18T09:25:45Z | 4.303858204 | 20 | status.py --launch pass |
| 2026-11-18T09:29:45Z | 4.32391104 | 20 | status.py --launch pass |
| 2026-11-18T09:33:28Z | 4.350726706 | 20 | status.py --launch pass |
| 2026-11-18T09:37:13Z | 4.438824343 | 20 | status.py --launch pass |
| 2026-11-18T09:41:03Z | 4.446879508 | 20 | status.py --launch pass |
| 2026-11-18T09:44:48Z | 4.537857928 | 20 | status.py --launch pass |
| 2026-11-18T09:48:31Z | 4.543027255 | 20 | status.py --launch pass |
| 2026-11-18T09:52:16Z | 4.578940339 | 20 | status.py --launch pass |
| 2026-11-18T09:55:27Z | 4.599501679 | 20 | status.py --launch pass |
| 2026-11-18T09:59:11Z | 4.642981235 | 20 | status.py --launch pass |
| 2026-11-18T10:02:17Z | 4.64718724 | 20 | status.py --launch pass |
| 2026-11-18T10:05:26Z | 4.669845966 | 20 | status.py --launch pass |
| 2026-11-18T10:09:47Z | 4.755718305 | 20 | status.py --launch pass |
| 2026-11-18T10:13:11Z | 4.803096075 | 20 | status.py --launch pass |
| 2026-11-18T10:17:00Z | 4.857031978 | 20 | status.py --launch pass |
| 2026-11-18T10:20:14Z | 4.86089297 | 20 | status.py --launch pass |
| 2026-11-18T10:23:19Z | 4.862336302 | 20 | status.py --launch pass |
| 2026-11-18T10:31:16Z | 5.535273615 | 20 | status.py --launch pass |
| 2026-11-18T10:34:39Z | 5.550853029 | 20 | status.py --launch pass |
| 2026-11-18T10:38:26Z | 5.690484723 | 20 | status.py --launch pass |
| 2026-11-18T10:41:34Z | 5.701719651 | 20 | status.py --launch pass |
| 2026-11-18T10:44:49Z | 5.710735505 | 20 | status.py --launch pass |
| 2026-11-18T10:44:56Z | 5.714790615 | 20 | batch 1 |
| 2026-11-18T10:48:12Z | 5.841968231 | 20 | status.py --launch pass |
| 2026-11-18T10:51:21Z | 6.090930392 | 20 | batch 1 commit |
| 2026-11-18T10:51:30Z | 6.094628922 | 20 | status.py --launch pass |

| Model | Requests | USD (ledger) | USD (OpenRouter) |
|---|---|---|---|
| `aion-labs/aion-3.5-mini` | 65 | 0.0916 | 0.0916 |
| `anthropic/claude-fable-5.2` | 56 | 2.1277 | 2.1277 |
| `baidu/ernie-5.5-flash-preview:free` | 29 | 0.0000 | 0.0000 |
| `baidu/ernie-light-dt-1.0-intl` | 60 | 0.1574 | 0.1574 |
| `deepseek/deepseek-v4-flash-vision-exp` | 65 | 0.0546 | 0.0546 |
| `deepseek/deepseek-v4.1-flash-1017` | 65 | 0.0056 | 0.0111 |
| `elorian/glimpse` | 53 | 0.0940 | 0.0940 |
| `google/gemini-4-carbon` | 3 | 0.0145 | 0.0145 |
| `google/gemini-4-hydrogen` | 3 | 0.0109 | 0.0109 |
| `ibm-granite/granite-4.2-8b` | 56 | 0.0087 | 0.0088 |
| `inclusionai/ling-3.0-flash-vl` | 50 | 0.0084 | 0.0084 |
| `inclusionai/ling-3.1-flash` | 80 | 0.0078 | 0.0078 |
| `inclusionai/ling-3.2-flash:free` | 49 | 0.0000 | 0.0000 |
| `kt/midm-k-3.0-pro` | 3 | 0.0019 | 0.0019 |
| `liquid/lfm-2.5-24b-a2b` | 3 | 0.0005 | 0.0005 |
| `liquid/lfm-3-1.7b` | 3 | 0.0007 | 0.0007 |
| `liquid/lfm-3-1.7b:free` | 1 | 0.0000 | 0.0000 |
| `meta/muse-ember` | 86 | 0.0155 | 0.0155 |
| `meta/muse-spark-1.2-contributor` | 1 | 0.0000 | 0.0000 |
| `meta/muse-spark-1.3-contributor` | 1 | 0.0000 | 0.0000 |
| `meta/muse-spark-open` | 50 | 0.1536 | 0.1536 |
| `minimax/minimax-m3.1-flash` | 65 | 0.0210 | 0.0204 |
| `moondream/moondream3-preview` | 53 | 0.0426 | 0.0426 |
| `moondream/moondream3.1-9b-a2b` | 50 | 0.0403 | 0.0403 |
| `motif-technologies/motif-3` | 77 | 0.0364 | 0.0364 |
| `nex-agi/nex-n2.5-mini` | 87 | 0.0045 | 0.0045 |
| `nex-agi/nex-n2.5-pro` | 51 | 0.0110 | 0.0110 |
| `nex-agi/nex-n2.6` | 83 | 0.0172 | 0.0172 |
| `nvidia/nemotron-3.5-super-vl` | 80 | 0.0275 | 0.0275 |
| `nvidia/nemotron-3.5-super-vl:free` | 3 | 0.0000 | 0.0000 |
| `openai/gpt-6.2-astra` | 74 | 1.2324 | 1.2324 |
| `openai/gpt-6.2-sol` | 145 | 0.6274 | 0.6274 |
| `particle-ai/particle-1` | 65 | 0.0092 | 0.0092 |
| `particle-ai/particle-1:free` | 59 | 0.0000 | 0.0000 |
| `perceptron/perceptron-mk1.5` | 3 | 0.0013 | 0.0013 |
| `prism-ml/ternary-bonsai-2-27b` | 3 | 0.0007 | 0.0007 |
| `prism-ml/ternary-bonsai-2-9b` | 3 | 0.0007 | 0.0007 |
| `qwen/qwen3.8-flash` | 83 | 0.0328 | 0.0328 |
| `qwen/qwen3.8-omni-flash` | 53 | 0.0235 | 0.0235 |
| `qwen/qwen4-max` | 74 | 0.2289 | 0.2289 |
| `recursive/flint-v1.0:free` | 77 | 0.0000 | 0.0000 |
| `reflection/beam-1.0-501b-a23b` | 77 | 0.0462 | 0.0497 |
| `ricursiveai/ripple-65b-preview` | 83 | 0.0143 | 0.0286 |
| `scaledown/extract` | 1 | 0.0000 | 0.0000 |
| `scaledown/summarize` | 3 | 0.0004 | 0.0004 |
| `stepfun/step-5-preview` | 65 | 0.1198 | 0.1198 |
| `tencent/hy4` | 68 | 0.0517 | 0.0517 |
| `tencent/hy4-flash` | 59 | 0.0049 | 0.0049 |
| `tencent/hy4-preview` | 65 | 0.1021 | 0.1039 |
| `thinkingmachines/inkling-2-small` | 50 | 0.0483 | 0.0481 |
| `unbiased/pareto-26.10` | 65 | 0.0913 | 0.0913 |
| `unbiased/pareto-26.10-preview` | 65 | 0.0911 | 0.0911 |
| `upstage/solar-mini4` | 51 | 0.0067 | 0.0067 |
| `xiaomi/mimo-v2.6-flash` | 83 | 0.0280 | 0.0280 |
| `xiaomi/mimo-v2.6-pro` | 65 | 0.0609 | 0.0568 |
| `z-ai/glm-5.3-flashx` | 71 | 0.0501 | 0.0501 |
| `z-ai/glm-5.3-flashx-legal` | 71 | 0.0496 | 0.0496 |
| `z-ai/glm-5.3-prime` | 47 | 0.1981 | 0.1981 |

| Run | Requests | USD (ledger) | USD (OpenRouter) |
|---|---|---|---|
| `aion-labs--aion-3.5-mini` | 65 | 0.0916 | 0.0916 |
| `anthropic--claude-fable-5.2` | 56 | 2.1277 | 2.1277 |
| `baidu--ernie-5.5-flash-preview-free` | 29 | 0.0000 | 0.0000 |
| `baidu--ernie-light-dt-1.0-intl` | 60 | 0.1574 | 0.1574 |
| `deepseek--deepseek-v4-flash-vision-exp` | 65 | 0.0546 | 0.0546 |
| `deepseek--deepseek-v4.1-flash-1017` | 65 | 0.0056 | 0.0111 |
| `elorian--glimpse` | 53 | 0.0940 | 0.0940 |
| `google--gemini-4-carbon` | 3 | 0.0145 | 0.0145 |
| `google--gemini-4-hydrogen` | 3 | 0.0109 | 0.0109 |
| `ibm-granite--granite-4.2-8b` | 56 | 0.0087 | 0.0088 |
| `inclusionai--ling-3.0-flash-vl` | 50 | 0.0084 | 0.0084 |
| `inclusionai--ling-3.1-flash` | 80 | 0.0078 | 0.0078 |
| `inclusionai--ling-3.2-flash-free` | 49 | 0.0000 | 0.0000 |
| `kt--midm-k-3.0-pro` | 3 | 0.0019 | 0.0019 |
| `liquid--lfm-2.5-24b-a2b` | 3 | 0.0005 | 0.0005 |
| `liquid--lfm-3-1.7b` | 3 | 0.0007 | 0.0007 |
| `liquid--lfm-3-1.7b-free` | 1 | 0.0000 | 0.0000 |
| `meta--muse-ember` | 86 | 0.0155 | 0.0155 |
| `meta--muse-spark-1.2-contributor` | 1 | 0.0000 | 0.0000 |
| `meta--muse-spark-1.3-contributor` | 1 | 0.0000 | 0.0000 |
| `meta--muse-spark-open` | 50 | 0.1536 | 0.1536 |
| `minimax--minimax-m3.1-flash` | 65 | 0.0210 | 0.0204 |
| `moondream--moondream3-preview` | 53 | 0.0426 | 0.0426 |
| `moondream--moondream3.1-9b-a2b` | 50 | 0.0403 | 0.0403 |
| `motif-technologies--motif-3` | 77 | 0.0364 | 0.0364 |
| `nex-agi--nex-n2.5-mini` | 87 | 0.0045 | 0.0045 |
| `nex-agi--nex-n2.5-pro` | 51 | 0.0110 | 0.0110 |
| `nex-agi--nex-n2.6` | 83 | 0.0172 | 0.0172 |
| `nvidia--nemotron-3.5-super-vl` | 80 | 0.0275 | 0.0275 |
| `nvidia--nemotron-3.5-super-vl-free` | 3 | 0.0000 | 0.0000 |
| `openai--gpt-6.2-astra` | 74 | 1.2324 | 1.2324 |
| `openai--gpt-6.2-sol` | 71 | 0.3245 | 0.3245 |
| `openai--gpt-6.2-sol-pinned-openai` | 74 | 0.3029 | 0.3029 |
| `particle-ai--particle-1` | 65 | 0.0092 | 0.0092 |
| `particle-ai--particle-1-free` | 59 | 0.0000 | 0.0000 |
| `perceptron--perceptron-mk1.5` | 3 | 0.0013 | 0.0013 |
| `prism-ml--ternary-bonsai-2-27b` | 3 | 0.0007 | 0.0007 |
| `prism-ml--ternary-bonsai-2-9b` | 3 | 0.0007 | 0.0007 |
| `qwen--qwen3.8-flash` | 83 | 0.0328 | 0.0328 |
| `qwen--qwen3.8-omni-flash` | 53 | 0.0235 | 0.0235 |
| `qwen--qwen4-max` | 74 | 0.2289 | 0.2289 |
| `recursive--flint-v1.0-free` | 77 | 0.0000 | 0.0000 |
| `reflection--beam-1.0-501b-a23b` | 77 | 0.0462 | 0.0497 |
| `ricursiveai--ripple-65b-preview` | 83 | 0.0143 | 0.0286 |
| `scaledown--extract` | 1 | 0.0000 | 0.0000 |
| `scaledown--summarize` | 3 | 0.0004 | 0.0004 |
| `stepfun--step-5-preview` | 65 | 0.1198 | 0.1198 |
| `tencent--hy4` | 68 | 0.0517 | 0.0517 |
| `tencent--hy4-flash` | 59 | 0.0049 | 0.0049 |
| `tencent--hy4-preview` | 65 | 0.1021 | 0.1039 |
| `thinkingmachines--inkling-2-small` | 50 | 0.0483 | 0.0481 |
| `unbiased--pareto-26.10` | 65 | 0.0913 | 0.0913 |
| `unbiased--pareto-26.10-preview` | 65 | 0.0911 | 0.0911 |
| `upstage--solar-mini4` | 51 | 0.0067 | 0.0067 |
| `xiaomi--mimo-v2.6-flash` | 83 | 0.0280 | 0.0280 |
| `xiaomi--mimo-v2.6-pro` | 65 | 0.0609 | 0.0568 |
| `z-ai--glm-5.3-flashx` | 71 | 0.0501 | 0.0501 |
| `z-ai--glm-5.3-flashx-legal` | 71 | 0.0496 | 0.0496 |
| `z-ai--glm-5.3-prime` | 47 | 0.1981 | 0.1981 |

