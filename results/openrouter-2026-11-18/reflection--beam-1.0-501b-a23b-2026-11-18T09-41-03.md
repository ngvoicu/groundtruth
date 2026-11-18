# reflection--beam-1.0-501b-a23b

- Endpoint: `https://openrouter.ai/api/v1` · format `responses` · model `reflection/beam-1.0-501b-a23b`
- Started 2026-11-18T09:41:03.830Z, finished 2026-11-18T11:41:14.882Z · status **completed**
- Probe 0.3.4 · run salt `s3fv959w` · 3 replicas per age · prompt_cache_key per sample
- Request: `POST /responses` · body extra none · prefix ~2500 tokens · max output 16 · stream off · session_id none · warm at 0.5 of the prompt cached
- Headers: content-type `application/json`, authorization (value not recorded), x-api-key (value not recorded)
- Control: prime 0/2876 cached, re-send 2816/2876 → warm

**Lifetime: ≥ 2h (never fully cold; warm through 5m)**

| Age | Warm | Checks |
|---|---|---|
| 2.5m | 3 | 3 |
| 5m | 3 | 3 |
| 7.5m | 2 | 3 |
| 10m | 2 | 3 |
| 15m | 2 | 3 |
| 20m | 2 | 3 |
| 25m | 2 | 3 |
| 30m | 3 | 3 |
| 40m | 3 | 3 |
| 50m | 2 | 3 |
| 1h | 3 | 3 |
| 75m | 2 | 3 |
| 90m | 2 | 3 |
| 2h | 1 | 3 |

Request body (one sample):

```json
{
  "model": "reflection/beam-1.0-501b-a23b",
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
  "prompt_cache_key": "groundtruth-s3fv959w-<sample>"
}
```
