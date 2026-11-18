# alias-z-ai--glm-flash-latest

- Endpoint: `https://openrouter.ai/api/v1` · format `responses` · model `~z-ai/glm-flash-latest`
- Started 2026-11-18T11:48:38.649Z, finished 2026-11-18T13:03:53.846Z · status **stopped-early**
- Probe 0.3.4 · run salt `zoo9s4ka` · 3 replicas per age · prompt_cache_key per sample
- Request: `POST /responses` · body extra none · prefix ~2500 tokens · max output 16 · stream off · session_id none · warm at 0.5 of the prompt cached
- Headers: content-type `application/json`, authorization (value not recorded), x-api-key (value not recorded)
- Control: prime 0/2663 cached, re-send 2560/2663 → warm

**Lifetime: <2.5m – 20m**

| Age | Warm | Checks |
|---|---|---|
| 2.5m | 2 | 3 |
| 5m | 2 | 3 |
| 7.5m | 3 | 3 |
| 10m | 2 | 3 |
| 15m | 1 | 3 |
| 20m | 0 | 3 |
| 25m | 1 | 3 |
| 30m | 1 | 3 |
| 40m | 1 | 3 |
| 50m | 1 | 3 |
| 1h | 0 | 3 |
| 75m | 0 | 3 |

Request body (one sample):

```json
{
  "model": "~z-ai/glm-flash-latest",
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
  "prompt_cache_key": "groundtruth-zoo9s4ka-<sample>"
}
```
