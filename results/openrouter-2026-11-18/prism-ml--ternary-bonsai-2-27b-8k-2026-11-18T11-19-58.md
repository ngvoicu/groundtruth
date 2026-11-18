# prism-ml--ternary-bonsai-2-27b-8k

- Endpoint: `https://openrouter.ai/api/v1` · format `responses` · model `prism-ml/ternary-bonsai-2-27b`
- Started 2026-11-18T11:19:58.835Z, finished 2026-11-18T11:39:34.991Z · status **stopped-early**
- Probe 0.3.4 · run salt `0ho6o3qu` · 3 replicas per age · prompt_cache_key per sample
- Request: `POST /responses` · body extra none · prefix ~8000 tokens · max output 16 · stream off · session_id none · warm at 0.5 of the prompt cached
- Headers: content-type `application/json`, authorization (value not recorded), x-api-key (value not recorded)
- Control: prime 0/9265 cached, re-send 8192/9265 → warm

**Lifetime: <2.5m – 2.5m**

| Age | Warm | Checks |
|---|---|---|
| 2.5m | 0 | 1 |
| 5m | 0 | 3 |
| 7.5m | 0 | 3 |
| 10m | 0 | 3 |
| 15m | 0 | 3 |

Left out, ran late: 2.5m at 3.1m cold, 2.5m at 3.4m cold.

Request body (one sample):

```json
{
  "model": "prism-ml/ternary-bonsai-2-27b",
  "input": [
    {
      "role": "developer",
      "content": [
        {
          "type": "input_text",
          "text": "<prefix: about 8000 tokens of words filler, one per sample>"
        }
      ]
    },
    {
      "role": "user",
      "content": [
        {
          "type": "input_text",
          "text": "Reply with the single word OK."
        }
      ]
    }
  ],
  "max_output_tokens": 16,
  "store": false,
  "stream": false,
  "prompt_cache_key": "groundtruth-0ho6o3qu-<sample>"
}
```
