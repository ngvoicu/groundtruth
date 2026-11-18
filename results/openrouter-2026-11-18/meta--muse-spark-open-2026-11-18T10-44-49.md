# meta--muse-spark-open

- Endpoint: `https://openrouter.ai/api/v1` · format `responses` · model `meta/muse-spark-open`
- Started 2026-11-18T10:44:49.711Z, finished 2026-11-18T11:44:59.721Z · status **stopped-early**
- Probe 0.3.4 · run salt `3sdkxqaj` · 3 replicas per age · prompt_cache_key per sample
- Request: `POST /responses` · body extra none · prefix ~2500 tokens · max output 16 · stream off · session_id none · warm at 0.5 of the prompt cached
- Headers: content-type `application/json`, authorization (value not recorded), x-api-key (value not recorded)
- Control: prime 16/2745 cached, re-send 2720/2745 → warm

**Lifetime: 7.5m – 50m**

| Age | Warm | Checks |
|---|---|---|
| 2.5m | 3 | 3 |
| 5m | 3 | 3 |
| 7.5m | 3 | 3 |
| 10m | 2 | 3 |
| 15m | 3 | 3 |
| 20m | 3 | 3 |
| 25m | 3 | 3 |
| 30m | 2 | 3 |
| 40m | 1 | 3 |
| 50m | 0 | 3 |
| 1h | 0 | 3 |

Request body (one sample):

```json
{
  "model": "meta/muse-spark-open",
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
  "prompt_cache_key": "groundtruth-3sdkxqaj-<sample>"
}
```
