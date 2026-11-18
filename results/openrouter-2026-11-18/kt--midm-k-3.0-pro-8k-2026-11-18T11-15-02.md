# kt--midm-k-3.0-pro-8k

- Endpoint: `https://openrouter.ai/api/v1` · format `responses` · model `kt/midm-k-3.0-pro`
- Started 2026-11-18T11:15:02.417Z, finished 2026-11-18T13:15:22.063Z · status **completed**
- Probe 0.3.4 · run salt `ivhjome2` · 3 replicas per age · prompt_cache_key per sample
- Request: `POST /responses` · body extra none · prefix ~8000 tokens · max output 16 · stream off · session_id none · warm at 0.5 of the prompt cached
- Headers: content-type `application/json`, authorization (value not recorded), x-api-key (value not recorded)
- Control: prime 0/9547 cached, re-send 8768/9547 → warm

**Lifetime: ≥ 2h (never fully cold; warm through 2h)**

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
| 40m | 3 | 3 |
| 50m | 3 | 3 |
| 1h | 3 | 3 |
| 75m | 3 | 3 |
| 90m | 3 | 3 |
| 2h | 3 | 3 |

Request body (one sample):

```json
{
  "model": "kt/midm-k-3.0-pro",
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
  "prompt_cache_key": "groundtruth-ivhjome2-<sample>"
}
```
