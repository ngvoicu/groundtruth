# baidu--ernie-light-dt-1.0-intl

- Endpoint: `https://openrouter.ai/api/v1` · format `responses` · model `baidu/ernie-light-dt-1.0-intl`
- Started 2026-11-18T10:34:39.977Z, finished 2026-11-18T12:35:16.070Z · status **completed**
- Probe 0.3.4 · run salt `9o1mb4k5` · 3 replicas per age · prompt_cache_key per sample
- Request: `POST /responses` · body extra none · prefix ~2500 tokens · max output 16 · stream off · session_id none · warm at 0.5 of the prompt cached
- Headers: content-type `application/json`, authorization (value not recorded), x-api-key (value not recorded)
- Control: prime 0/2647 cached, re-send 2556/2647 → warm

**Lifetime: 2.5m – 30m**

| Age | Warm | Checks |
|---|---|---|
| 2.5m | 3 | 3 |
| 5m | 2 | 3 |
| 7.5m | 2 | 3 |
| 10m | 1 | 3 |
| 15m | 1 | 3 |
| 20m | 1 | 3 |
| 25m | 1 | 3 |
| 30m | 0 | 3 |
| 40m | 1 | 3 |
| 50m | 2 | 3 |
| 1h | 1 | 3 |
| 75m | 1 | 3 |
| 90m | 2 | 3 |
| 2h | 2 | 3 |

Request body (one sample):

```json
{
  "model": "baidu/ernie-light-dt-1.0-intl",
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
  "prompt_cache_key": "groundtruth-9o1mb4k5-<sample>"
}
```
