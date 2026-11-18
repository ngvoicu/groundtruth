# alias-z-ai--glm-latest

- Endpoint: `https://openrouter.ai/api/v1` · format `responses` · model `~z-ai/glm-latest`
- Started 2026-11-18T11:52:20.909Z, finished 2026-11-18T12:12:33.117Z · status **stopped-early**
- Probe 0.3.4 · run salt `bo1ynz9n` · 3 replicas per age · prompt_cache_key per sample
- Request: `POST /responses` · body extra none · prefix ~2500 tokens · max output 16 · stream off · session_id none · warm at 0.5 of the prompt cached
- Headers: content-type `application/json`, authorization (value not recorded), x-api-key (value not recorded)
- Control: prime 0/2632 cached, re-send 2624/2632 → warm

**Lifetime: <2.5m – 15m**

| Age | Warm | Checks |
|---|---|---|
| 2.5m | 2 | 3 |
| 5m | 3 | 3 |
| 7.5m | 2 | 3 |
| 10m | 1 | 3 |
| 15m | 0 | 3 |
| 20m | 0 | 3 |

Request body (one sample):

```json
{
  "model": "~z-ai/glm-latest",
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
  "prompt_cache_key": "groundtruth-bo1ynz9n-<sample>"
}
```
