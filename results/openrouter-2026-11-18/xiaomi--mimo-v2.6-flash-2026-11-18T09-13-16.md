# xiaomi--mimo-v2.6-flash

- Endpoint: `https://openrouter.ai/api/v1` · format `responses` · model `xiaomi/mimo-v2.6-flash`
- Started 2026-11-18T09:13:16.284Z, finished 2026-11-18T11:13:47.868Z · status **completed**
- Probe 0.3.4 · run salt `pzks4jgw` · 3 replicas per age · prompt_cache_key per sample
- Request: `POST /responses` · body extra none · prefix ~2500 tokens · max output 16 · stream off · session_id none · warm at 0.5 of the prompt cached
- Headers: content-type `application/json`, authorization (value not recorded), x-api-key (value not recorded)
- Control: prime 0/2808 cached, re-send 2688/2808 → warm

**Lifetime: <2.5m – 7.5m**

| Age | Warm | Checks |
|---|---|---|
| 2.5m | 2 | 3 |
| 5m | 1 | 3 |
| 7.5m | 0 | 3 |
| 10m | 1 | 3 |
| 15m | 1 | 3 |
| 20m | 2 | 3 |
| 25m | 1 | 3 |
| 30m | 1 | 3 |
| 40m | 0 | 3 |
| 50m | 1 | 3 |
| 1h | 1 | 3 |
| 75m | 0 | 3 |
| 90m | 1 | 3 |
| 2h | 1 | 3 |

Request body (one sample):

```json
{
  "model": "xiaomi/mimo-v2.6-flash",
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
  "prompt_cache_key": "groundtruth-pzks4jgw-<sample>"
}
```
