# particle-ai--particle-1

- Endpoint: `https://openrouter.ai/api/v1` · format `responses` · model `particle-ai/particle-1`
- Started 2026-11-18T08:57:36.376Z, finished 2026-11-18T09:22:45.922Z · status **stopped-early**
- Probe 0.3.3 · run salt `b83lm2sb` · 3 replicas per age · prompt_cache_key per sample
- Request: `POST /responses` · body extra none · prefix ~2500 tokens · max output 16 · stream off · session_id none · warm at 0.5 of the prompt cached
- Headers: content-type `application/json`, authorization (value not recorded), x-api-key (value not recorded)
- Control: prime 0/2590 cached, re-send 2560/2590 → warm

**Lifetime: <2.5m – 5m**

| Age | Warm | Checks |
|---|---|---|
| 2.5m | 2 | 3 |
| 5m | 0 | 3 |
| 7.5m | 3 | 3 |
| 10m | 1 | 3 |
| 15m | 1 | 3 |
| 20m | 0 | 3 |
| 25m | 0 | 3 |

Request body (one sample):

```json
{
  "model": "particle-ai/particle-1",
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
  "prompt_cache_key": "groundtruth-b83lm2sb-<sample>"
}
```
