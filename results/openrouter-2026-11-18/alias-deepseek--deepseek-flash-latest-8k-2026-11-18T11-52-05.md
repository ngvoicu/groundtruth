# alias-deepseek--deepseek-flash-latest-8k

- Endpoint: `https://openrouter.ai/api/v1` · format `responses` · model `~deepseek/deepseek-flash-latest`
- Started 2026-11-18T11:52:05.848Z, finished 2026-11-18T13:52:18.612Z · status **completed**
- Probe 0.3.4 · run salt `egfw27xv` · 3 replicas per age · prompt_cache_key per sample
- Request: `POST /responses` · body extra none · prefix ~8000 tokens · max output 16 · stream off · session_id none · warm at 0.5 of the prompt cached
- Headers: content-type `application/json`, authorization (value not recorded), x-api-key (value not recorded)
- Control: prime 0/7972 cached, re-send 7936/7972 → warm

**Lifetime: ≥ 2h (never fully cold; warm through 2.5m)**

| Age | Warm | Checks |
|---|---|---|
| 2.5m | 3 | 3 |
| 5m | 2 | 3 |
| 7.5m | 3 | 3 |
| 10m | 2 | 3 |
| 15m | 3 | 3 |
| 20m | 2 | 3 |
| 25m | 2 | 3 |
| 30m | 3 | 3 |
| 40m | 2 | 3 |
| 50m | 2 | 3 |
| 1h | 1 | 3 |
| 75m | 1 | 3 |
| 90m | 2 | 3 |
| 2h | 1 | 3 |

Request body (one sample):

```json
{
  "model": "~deepseek/deepseek-flash-latest",
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
  "prompt_cache_key": "groundtruth-egfw27xv-<sample>"
}
```
