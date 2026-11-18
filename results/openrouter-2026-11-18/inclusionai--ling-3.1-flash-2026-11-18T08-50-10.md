# inclusionai--ling-3.1-flash

- Endpoint: `https://openrouter.ai/api/v1` · format `responses` · model `inclusionai/ling-3.1-flash`
- Started 2026-11-18T08:50:10.339Z, finished 2026-11-18T10:05:32.930Z · status **stopped-early**
- Probe 0.3.3 · run salt `ruu904qo` · 3 replicas per age · prompt_cache_key per sample
- Request: `POST /responses` · body extra none · prefix ~2500 tokens · max output 16 · stream off · session_id none · warm at 0.5 of the prompt cached
- Headers: content-type `application/json`, authorization (value not recorded), x-api-key (value not recorded)
- Control: prime 0/2776 cached, re-send 2752/2776 → warm

**Lifetime: 5m – 1h**

| Age | Warm | Checks |
|---|---|---|
| 2.5m | 3 | 3 |
| 5m | 3 | 3 |
| 7.5m | 2 | 3 |
| 10m | 3 | 3 |
| 15m | 2 | 3 |
| 20m | 2 | 3 |
| 25m | 1 | 3 |
| 30m | 3 | 3 |
| 40m | 2 | 3 |
| 50m | 2 | 3 |
| 1h | 0 | 3 |
| 75m | 0 | 3 |

Request body (one sample):

```json
{
  "model": "inclusionai/ling-3.1-flash",
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
  "prompt_cache_key": "groundtruth-ruu904qo-<sample>"
}
```
