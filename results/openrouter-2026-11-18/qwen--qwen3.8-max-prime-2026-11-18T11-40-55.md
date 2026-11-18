# qwen--qwen3.8-max-prime

- Endpoint: `https://openrouter.ai/api/v1` · format `responses` · model `qwen/qwen3.8-max-prime`
- Started 2026-11-18T11:40:55.585Z, finished 2026-11-18T12:31:11.472Z · status **stopped-early**
- Probe 0.3.4 · run salt `tkpt16e7` · 3 replicas per age · prompt_cache_key per sample
- Request: `POST /responses` · body extra none · prefix ~2500 tokens · max output 16 · stream off · session_id none · warm at 0.5 of the prompt cached
- Headers: content-type `application/json`, authorization (value not recorded), x-api-key (value not recorded)
- Control: prime 0/2944 cached, re-send 2048/2944 → warm

**Lifetime: 30m – 40m**

| Age | Warm | Checks |
|---|---|---|
| 2.5m | 3 | 3 |
| 5m | 3 | 3 |
| 7.5m | 3 | 3 |
| 10m | 3 | 3 |
| 15m | 3 | 3 |
| 20m | 3 | 3 |
| 25m | 3 | 3 |
| 30m | 3 | 3 |
| 40m | 0 | 3 |
| 50m | 0 | 3 |

Request body (one sample):

```json
{
  "model": "qwen/qwen3.8-max-prime",
  "input": [
    {
      "role": "developer",
      "content": [
        {
          "type": "input_text",
          "text": "<prefix: about 2500 tokens of words filler, one per sample>"
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
  "prompt_cache_key": "groundtruth-tkpt16e7-<sample>"
}
```
