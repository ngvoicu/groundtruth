# Ledger

Computed by `ledger.py` from the usage each reply reported (`logs/*.usage.jsonl`), at OpenRouter's prices read before each run (`offered.jsonl`; `sources/openrouter-models.json` otherwise). Every request is in `ledger.jsonl` with its tokens, upstream, price, OpenRouter's own cost figure and the running total.

**Total: $16.2185** by the ledger (OpenRouter's own per-reply `usage.cost` summed: $16.3146), 5427 requests, stop at $18.

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
| 2026-11-18T10:54:57Z | 6.371562148 | 20 | status.py --launch pass |
| 2026-11-18T10:58:13Z | 6.404008628 | 20 | status.py --launch pass |
| 2026-11-18T11:01:21Z | 6.42510625 | 20 | status.py --launch pass |
| 2026-11-18T11:04:32Z | 6.444352717 | 20 | status.py --launch pass |
| 2026-11-18T11:07:47Z | 6.475786856 | 20 | status.py --launch pass |
| 2026-11-18T11:11:30Z | 7.14159349 | 20 | status.py --launch pass |
| 2026-11-18T11:14:46Z | 7.253576371 | 20 | status.py --launch pass |
| 2026-11-18T11:19:28Z | 7.875902107 | 20 | status.py --launch pass |
| 2026-11-18T11:24:13Z | 8.047388918 | 20 | status.py --launch pass |
| 2026-11-18T11:27:45Z | 8.126680191 | 20 | status.py --launch pass |
| 2026-11-18T11:32:30Z | 8.640328434 | 20 | status.py --launch pass |
| 2026-11-18T11:37:02Z | 9.259568337 | 20 | status.py --launch pass |
| 2026-11-18T11:40:25Z | 9.332966404 | 20 | status.py --launch pass |
| 2026-11-18T11:44:20Z | 10.614419276 | 20 | status.py --launch pass |
| 2026-11-18T11:48:23Z | 11.179729138 | 20 | status.py --launch pass |
| 2026-11-18T11:52:05Z | 11.262032263 | 20 | status.py --launch pass |
| 2026-11-18T11:56:39Z | 11.358261246 | 20 | status.py --launch pass |
| 2026-11-18T12:01:09Z | 11.450040114 | 20 | status.py --launch pass |
| 2026-11-18T12:01:20Z | 11.450040114 | 20 | batch 2 |
| 2026-11-18T12:02:42Z | 11.46731341 | 20 | batch 2 commit |
| 2026-11-18T12:04:12Z | 11.476695178 | 20 | status.py --launch pass |
| 2026-11-18T12:07:35Z | 11.507217394 | 20 | status.py --launch pass |
| 2026-11-18T12:10:46Z | 11.532925353 | 20 | status.py --launch pass |
| 2026-11-18T12:14:51Z | 11.697771356 | 20 | status.py --launch pass |
| 2026-11-18T12:18:44Z | 12.139197049 | 20 | status.py --launch pass |
| 2026-11-18T12:22:02Z | 12.220894317 | 20 | status.py --launch pass |
| 2026-11-18T12:25:17Z | 12.271862978 | 20 | status.py --launch pass |
| 2026-11-18T12:29:00Z | 13.498418968 | 20 | status.py --launch pass |
| 2026-11-18T12:32:18Z | 13.5827259 | 20 | status.py --launch pass |
| 2026-11-18T12:35:28Z | 13.596861866 | 20 | status.py --launch pass |
| 2026-11-18T12:38:35Z | 13.617353987 | 20 | status.py --launch pass |
| 2026-11-18T12:41:46Z | 13.645953617 | 20 | status.py --launch pass |
| 2026-11-18T12:44:51Z | 13.654711143 | 20 | status.py --launch pass |
| 2026-11-18T12:47:54Z | 13.671749919 | 20 | status.py --launch pass |
| 2026-11-18T12:51:38Z | 14.318526758 | 20 | status.py --launch pass |
| 2026-11-18T12:54:45Z | 14.32803537 | 20 | status.py --launch pass |
| 2026-11-18T12:57:46Z | 14.398760295 | 20 | status.py --launch pass |
| 2026-11-18T13:01:30Z | 14.666779769 | 20 | status.py --launch pass |
| 2026-11-18T13:04:40Z | 14.689339459 | 20 | status.py --launch pass |
| 2026-11-18T13:07:43Z | 14.807121219 | 20 | status.py --launch pass |
| 2026-11-18T13:10:48Z | 14.815945648 | 20 | status.py --launch pass |
| 2026-11-18T13:13:55Z | 14.840383438 | 20 | status.py --launch pass |
| 2026-11-18T13:16:57Z | 14.870091664 | 20 | status.py --launch pass |
| 2026-11-18T13:20:03Z | 14.941650664 | 20 | status.py --launch pass |
| 2026-11-18T13:23:07Z | 14.959271864 | 20 | status.py --launch pass |
| 2026-11-18T13:26:11Z | 14.960438588 | 20 | status.py --launch pass |
| 2026-11-18T13:29:16Z | 14.981563358 | 20 | status.py --launch pass |
| 2026-11-18T13:32:19Z | 15.017725358 | 20 | status.py --launch pass |
| 2026-11-18T13:35:37Z | 15.017725358 | 20 | status.py --launch pass |
| 2026-11-18T13:38:55Z | 15.017725358 | 20 | status.py --launch pass |
| 2026-11-18T13:41:58Z | 15.078191558 | 20 | status.py --launch pass |
| 2026-11-18T13:44:59Z | 15.084607228 | 20 | status.py --launch pass |
| 2026-11-18T13:48:00Z | 15.085807198 | 20 | status.py --launch pass |
| 2026-11-18T13:51:03Z | 15.103846698 | 20 | status.py --launch pass |
| 2026-11-18T13:54:06Z | 15.104656221 | 20 | status.py --launch pass |
| 2026-11-18T13:57:22Z | 16.145741421 | 20 | status.py --launch pass |
| 2026-11-18T13:57:27Z | 16.149190621 | 20 | batch 3 |
| 2026-11-18T14:00:24Z | 16.152681021 | 20 | status.py --launch pass |
| 2026-11-18T14:03:26Z | 16.152681021 | 20 | status.py --launch pass |
| 2026-11-18T14:06:30Z | 16.156190221 | 20 | status.py --launch pass |
| 2026-11-18T14:09:33Z | 16.159656221 | 20 | status.py --launch pass |
| 2026-11-18T14:12:34Z | 16.163153421 | 20 | status.py --launch pass |
| 2026-11-18T14:15:37Z | 16.166629021 | 20 | status.py --launch pass |
| 2026-11-18T14:18:38Z | 16.166629021 | 20 | status.py --launch pass |
| 2026-11-18T14:21:41Z | 16.170145021 | 20 | status.py --launch pass |
| 2026-11-18T14:24:43Z | 16.170145021 | 20 | status.py --launch pass |
| 2026-11-18T14:27:44Z | 16.242385021 | 20 | status.py --launch pass |
| 2026-11-18T14:30:45Z | 16.242385021 | 20 | status.py --launch pass |
| 2026-11-18T14:33:46Z | 16.242385021 | 20 | status.py --launch pass |
| 2026-11-18T14:36:49Z | 16.314639021 | 20 | status.py --launch pass |
| 2026-11-18T14:41:03Z | 16.314639021 | 20 | end |

| Model | Requests | USD (ledger) | USD (OpenRouter) |
|---|---|---|---|
| `aion-labs/aion-3.5` | 83 | 0.4762 | 0.4762 |
| `aion-labs/aion-3.5-mini` | 83 | 0.1117 | 0.1117 |
| `anthropic/claude-fable-5.2` | 56 | 2.1277 | 2.1277 |
| `anthropic/claude-sonnet-5.5` | 56 | 0.5339 | 0.5339 |
| `baidu/ernie-5.5-flash-preview:free` | 33 | 0.0000 | 0.0000 |
| `baidu/ernie-light-dt-1.0-intl` | 87 | 0.2112 | 0.2112 |
| `deepseek/deepseek-v4-flash-vision-exp` | 81 | 0.0694 | 0.0694 |
| `deepseek/deepseek-v4.1-flash-1017` | 65 | 0.0056 | 0.0111 |
| `elorian/glimpse` | 53 | 0.0940 | 0.0940 |
| `fireworks/ember-1` | 74 | 0.4336 | 0.4336 |
| `google/gemini-4-carbon` | 55 | 0.7634 | 0.7634 |
| `google/gemini-4-hydrogen` | 59 | 0.6190 | 0.6190 |
| `ibm-granite/granite-4.2-8b` | 56 | 0.0087 | 0.0088 |
| `inclusionai/ling-3.0-flash-vl` | 50 | 0.0084 | 0.0084 |
| `inclusionai/ling-3.1-flash` | 80 | 0.0078 | 0.0078 |
| `inclusionai/ling-3.2-flash:free` | 49 | 0.0000 | 0.0000 |
| `kt/midm-k-3.0-pro` | 89 | 0.1070 | 0.1070 |
| `liquid/lfm-2.5-24b-a2b` | 86 | 0.0327 | 0.0327 |
| `liquid/lfm-3-1.7b` | 54 | 0.0371 | 0.0371 |
| `liquid/lfm-3-1.7b:free` | 1 | 0.0000 | 0.0000 |
| `meta/muse-ember` | 86 | 0.0155 | 0.0155 |
| `meta/muse-spark-1.2-contributor` | 1 | 0.0000 | 0.0000 |
| `meta/muse-spark-1.3-contributor` | 1 | 0.0000 | 0.0000 |
| `meta/muse-spark-open` | 77 | 0.1971 | 0.1971 |
| `minimax/minimax-m3.1-flash` | 65 | 0.0210 | 0.0204 |
| `moondream/moondream3-preview` | 53 | 0.0426 | 0.0426 |
| `moondream/moondream3.1-9b-a2b` | 50 | 0.0403 | 0.0403 |
| `motif-technologies/motif-3` | 86 | 0.0381 | 0.0381 |
| `nex-agi/nex-n2.5-mini` | 87 | 0.0045 | 0.0045 |
| `nex-agi/nex-n2.5-pro` | 51 | 0.0110 | 0.0110 |
| `nex-agi/nex-n2.6` | 86 | 0.0174 | 0.0174 |
| `nvidia/nemotron-3.5-super-vl` | 87 | 0.0287 | 0.0288 |
| `nvidia/nemotron-3.5-super-vl:free` | 92 | 0.0000 | 0.0000 |
| `openai/gpt-6-luna-pro` | 74 | 0.0385 | 0.0385 |
| `openai/gpt-6-sol` | 74 | 0.3080 | 0.3080 |
| `openai/gpt-6-sol-pro` | 74 | 0.7494 | 0.7494 |
| `openai/gpt-6.1-sol-pro` | 74 | 0.7164 | 0.7164 |
| `openai/gpt-6.1-terra-pro` | 74 | 0.3640 | 0.3640 |
| `openai/gpt-6.2-astra` | 74 | 1.2324 | 1.2324 |
| `openai/gpt-6.2-sol` | 145 | 0.6274 | 0.6274 |
| `openai/gpt-6.2-sol-pro` | 74 | 0.7713 | 0.7713 |
| `particle-ai/particle-1` | 65 | 0.0092 | 0.0092 |
| `particle-ai/particle-1:free` | 59 | 0.0000 | 0.0000 |
| `perceptron/perceptron-mk1.5` | 6 | 0.0056 | 0.0056 |
| `prism-ml/ternary-bonsai-2-27b` | 73 | 0.0503 | 0.0503 |
| `prism-ml/ternary-bonsai-2-9b` | 54 | 0.0387 | 0.0387 |
| `qwen/qwen3.8-flash` | 83 | 0.0328 | 0.0328 |
| `qwen/qwen3.8-max-0902` | 74 | 0.3509 | 0.3509 |
| `qwen/qwen3.8-max-prime` | 74 | 0.7046 | 0.7046 |
| `qwen/qwen3.8-omni-flash` | 53 | 0.0235 | 0.0235 |
| `qwen/qwen4-max` | 74 | 0.2289 | 0.2289 |
| `recursive/flint-v1.0:free` | 80 | 0.0000 | 0.0000 |
| `reflection/beam-1.0-501b-a23b` | 86 | 0.0503 | 0.0545 |
| `ricursiveai/ripple-65b-preview` | 86 | 0.0151 | 0.0302 |
| `sakana/fugu-max` | 1 | 0.0000 | 0.0000 |
| `sakana/fugu-ultra-v2` | 1 | 0.0000 | 0.0000 |
| `scaledown/extract` | 1 | 0.0000 | 0.0000 |
| `scaledown/summarize` | 6 | 0.0015 | 0.0015 |
| `stepfun/step-5-preview` | 74 | 0.1385 | 0.1385 |
| `tencent/hy4` | 86 | 0.0538 | 0.0538 |
| `tencent/hy4-flash` | 59 | 0.0049 | 0.0049 |
| `tencent/hy4-preview` | 86 | 0.1167 | 0.1215 |
| `thinkingmachines/inkling-2-small` | 50 | 0.0483 | 0.0481 |
| `thinkingmachines/inkling-2-small:free` | 1 | 0.0000 | 0.0000 |
| `unbiased/pareto-26.10` | 86 | 0.1098 | 0.1098 |
| `unbiased/pareto-26.10-preview` | 83 | 0.1051 | 0.1051 |
| `unbiased/pareto-26.9` | 74 | 0.3354 | 0.3354 |
| `upstage/solar-mini4` | 51 | 0.0067 | 0.0067 |
| `xiaomi/mimo-v2.6-flash` | 87 | 0.0288 | 0.0288 |
| `xiaomi/mimo-v2.6-pro` | 87 | 0.0761 | 0.0704 |
| `xiaomi/mimo-v2.6-pro-ultraspeed` | 86 | 0.5495 | 0.5495 |
| `z-ai/glm-5.3-flashx` | 77 | 0.0562 | 0.0562 |
| `z-ai/glm-5.3-flashx-legal` | 86 | 0.0592 | 0.0592 |
| `z-ai/glm-5.3-prime` | 86 | 0.2923 | 0.2923 |
| `~deepseek/deepseek-flash-latest` | 89 | 0.0194 | 0.0441 |
| `~deepseek/deepseek-pro-latest` | 50 | 0.0133 | 0.0205 |
| `~openai/gpt-astra-latest` | 71 | 1.2100 | 1.2100 |
| `~openai/gpt-luna-latest` | 74 | 0.0154 | 0.0154 |
| `~openai/gpt-sol-latest` | 74 | 0.3199 | 0.3199 |
| `~openai/gpt-terra-latest` | 74 | 0.1512 | 0.1512 |
| `~unbiased/pareto-latest` | 83 | 0.1055 | 0.1055 |
| `~z-ai/glm-flash-latest` | 80 | 0.0082 | 0.0223 |
| `~z-ai/glm-latest` | 62 | 0.0120 | 0.0386 |

| Run | Requests | USD (ledger) | USD (OpenRouter) |
|---|---|---|---|
| `aion-labs--aion-3.5` | 83 | 0.4762 | 0.4762 |
| `aion-labs--aion-3.5-mini` | 83 | 0.1117 | 0.1117 |
| `alias-deepseek--deepseek-flash-latest` | 3 | 0.0003 | 0.0006 |
| `alias-deepseek--deepseek-flash-latest-8k` | 86 | 0.0191 | 0.0435 |
| `alias-deepseek--deepseek-pro-latest` | 50 | 0.0133 | 0.0205 |
| `alias-openai--gpt-astra-latest` | 71 | 1.2100 | 1.2100 |
| `alias-openai--gpt-luna-latest` | 74 | 0.0154 | 0.0154 |
| `alias-openai--gpt-sol-latest` | 74 | 0.3199 | 0.3199 |
| `alias-openai--gpt-terra-latest` | 74 | 0.1512 | 0.1512 |
| `alias-unbiased--pareto-latest` | 83 | 0.1055 | 0.1055 |
| `alias-z-ai--glm-flash-latest` | 80 | 0.0082 | 0.0223 |
| `alias-z-ai--glm-latest` | 62 | 0.0120 | 0.0386 |
| `anthropic--claude-fable-5.2` | 56 | 2.1277 | 2.1277 |
| `anthropic--claude-sonnet-5.5` | 56 | 0.5339 | 0.5339 |
| `baidu--ernie-5.5-flash-preview-free` | 29 | 0.0000 | 0.0000 |
| `baidu--ernie-5.5-flash-preview-free-paced` | 4 | 0.0000 | 0.0000 |
| `baidu--ernie-light-dt-1.0-intl` | 87 | 0.2112 | 0.2112 |
| `deepseek--deepseek-v4-flash-vision-exp` | 80 | 0.0694 | 0.0694 |
| `deepseek--deepseek-v4.1-flash-1017` | 65 | 0.0056 | 0.0111 |
| `elorian--glimpse` | 53 | 0.0940 | 0.0940 |
| `fireworks--ember-1` | 74 | 0.4336 | 0.4336 |
| `google--gemini-4-carbon` | 3 | 0.0145 | 0.0145 |
| `google--gemini-4-carbon-8k` | 52 | 0.7489 | 0.7489 |
| `google--gemini-4-hydrogen` | 3 | 0.0109 | 0.0109 |
| `google--gemini-4-hydrogen-8k` | 56 | 0.6081 | 0.6081 |
| `ibm-granite--granite-4.2-8b` | 56 | 0.0087 | 0.0088 |
| `inclusionai--ling-3.0-flash-vl` | 50 | 0.0084 | 0.0084 |
| `inclusionai--ling-3.1-flash` | 80 | 0.0078 | 0.0078 |
| `inclusionai--ling-3.2-flash-free` | 49 | 0.0000 | 0.0000 |
| `kt--midm-k-3.0-pro` | 3 | 0.0019 | 0.0019 |
| `kt--midm-k-3.0-pro-8k` | 86 | 0.1051 | 0.1051 |
| `liquid--lfm-2.5-24b-a2b` | 3 | 0.0005 | 0.0005 |
| `liquid--lfm-2.5-24b-a2b-8k` | 83 | 0.0322 | 0.0322 |
| `liquid--lfm-3-1.7b` | 3 | 0.0007 | 0.0007 |
| `liquid--lfm-3-1.7b-8k` | 51 | 0.0364 | 0.0364 |
| `liquid--lfm-3-1.7b-free` | 1 | 0.0000 | 0.0000 |
| `meta--muse-ember` | 86 | 0.0155 | 0.0155 |
| `meta--muse-spark-1.2-contributor` | 1 | 0.0000 | 0.0000 |
| `meta--muse-spark-1.3-contributor` | 1 | 0.0000 | 0.0000 |
| `meta--muse-spark-open` | 77 | 0.1971 | 0.1971 |
| `minimax--minimax-m3.1-flash` | 65 | 0.0210 | 0.0204 |
| `moondream--moondream3-preview` | 53 | 0.0426 | 0.0426 |
| `moondream--moondream3.1-9b-a2b` | 50 | 0.0403 | 0.0403 |
| `motif-technologies--motif-3` | 86 | 0.0381 | 0.0381 |
| `nex-agi--nex-n2.5-mini` | 87 | 0.0045 | 0.0045 |
| `nex-agi--nex-n2.5-pro` | 51 | 0.0110 | 0.0110 |
| `nex-agi--nex-n2.6` | 86 | 0.0174 | 0.0174 |
| `nvidia--nemotron-3.5-super-vl` | 86 | 0.0287 | 0.0288 |
| `nvidia--nemotron-3.5-super-vl-free` | 3 | 0.0000 | 0.0000 |
| `nvidia--nemotron-3.5-super-vl-free-8k` | 89 | 0.0000 | 0.0000 |
| `openai--gpt-6-luna-pro` | 74 | 0.0385 | 0.0385 |
| `openai--gpt-6-sol` | 74 | 0.3080 | 0.3080 |
| `openai--gpt-6-sol-pro` | 74 | 0.7494 | 0.7494 |
| `openai--gpt-6.1-sol-pro` | 74 | 0.7164 | 0.7164 |
| `openai--gpt-6.1-terra-pro` | 74 | 0.3640 | 0.3640 |
| `openai--gpt-6.2-astra` | 74 | 1.2324 | 1.2324 |
| `openai--gpt-6.2-sol` | 71 | 0.3245 | 0.3245 |
| `openai--gpt-6.2-sol-pinned-openai` | 74 | 0.3029 | 0.3029 |
| `openai--gpt-6.2-sol-pro` | 74 | 0.7713 | 0.7713 |
| `particle-ai--particle-1` | 65 | 0.0092 | 0.0092 |
| `particle-ai--particle-1-free` | 59 | 0.0000 | 0.0000 |
| `perceptron--perceptron-mk1.5` | 3 | 0.0013 | 0.0013 |
| `perceptron--perceptron-mk1.5-8k` | 3 | 0.0042 | 0.0042 |
| `prism-ml--ternary-bonsai-2-27b` | 3 | 0.0007 | 0.0007 |
| `prism-ml--ternary-bonsai-2-27b-8k` | 70 | 0.0496 | 0.0496 |
| `prism-ml--ternary-bonsai-2-9b` | 3 | 0.0007 | 0.0007 |
| `prism-ml--ternary-bonsai-2-9b-8k` | 51 | 0.0380 | 0.0380 |
| `qwen--qwen3.8-flash` | 83 | 0.0328 | 0.0328 |
| `qwen--qwen3.8-max-0902` | 74 | 0.3509 | 0.3509 |
| `qwen--qwen3.8-max-prime` | 74 | 0.7046 | 0.7046 |
| `qwen--qwen3.8-omni-flash` | 53 | 0.0235 | 0.0235 |
| `qwen--qwen4-max` | 74 | 0.2289 | 0.2289 |
| `recursive--flint-v1.0-free` | 80 | 0.0000 | 0.0000 |
| `reflection--beam-1.0-501b-a23b` | 86 | 0.0503 | 0.0545 |
| `ricursiveai--ripple-65b-preview` | 86 | 0.0151 | 0.0302 |
| `sakana--fugu-max` | 1 | 0.0000 | 0.0000 |
| `sakana--fugu-ultra-v2` | 1 | 0.0000 | 0.0000 |
| `scaledown--extract` | 1 | 0.0000 | 0.0000 |
| `scaledown--summarize` | 3 | 0.0004 | 0.0004 |
| `scaledown--summarize-8k` | 3 | 0.0012 | 0.0012 |
| `stepfun--step-5-preview` | 74 | 0.1385 | 0.1385 |
| `tencent--hy4` | 86 | 0.0538 | 0.0538 |
| `tencent--hy4-flash` | 59 | 0.0049 | 0.0049 |
| `tencent--hy4-preview` | 86 | 0.1167 | 0.1215 |
| `thinkingmachines--inkling-2-small` | 50 | 0.0483 | 0.0481 |
| `thinkingmachines--inkling-2-small-free` | 1 | 0.0000 | 0.0000 |
| `unbiased--pareto-26.10` | 86 | 0.1098 | 0.1098 |
| `unbiased--pareto-26.10-preview` | 83 | 0.1051 | 0.1051 |
| `unbiased--pareto-26.9` | 74 | 0.3354 | 0.3354 |
| `upstage--solar-mini4` | 51 | 0.0067 | 0.0067 |
| `windows` | 4 | 0.0000 | 0.0000 |
| `xiaomi--mimo-v2.6-flash` | 86 | 0.0288 | 0.0288 |
| `xiaomi--mimo-v2.6-pro` | 86 | 0.0761 | 0.0704 |
| `xiaomi--mimo-v2.6-pro-ultraspeed` | 86 | 0.5495 | 0.5495 |
| `z-ai--glm-5.3-flashx` | 77 | 0.0562 | 0.0562 |
| `z-ai--glm-5.3-flashx-legal` | 86 | 0.0592 | 0.0592 |
| `z-ai--glm-5.3-prime` | 86 | 0.2923 | 0.2923 |

