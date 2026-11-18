# liquid--lfm-2.5-24b-a2b-8k

- Endpoint: `https://openrouter.ai/api/v1` · format `responses` · model `liquid/lfm-2.5-24b-a2b`
- Started 2026-11-18T11:27:45.821Z, finished 2026-11-18T12:57:58.307Z · status **stopped-early**
- Probe 0.3.4 · run salt `rout70lk` · 3 replicas per age · prompt_cache_key per sample
- Request: `POST /responses` · body extra none · prefix ~8000 tokens · max output 16 · stream off · session_id none · warm at 0.5 of the prompt cached
- Headers: content-type `application/json`, authorization (value not recorded), x-api-key (value not recorded)
- Control: prime 0/9015 cached, re-send 8192/9015 → warm

**Lifetime: 1h – 75m**

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
| 75m | 0 | 3 |
| 90m | 0 | 3 |

Request body (one sample):

```json
{
  "model": "liquid/lfm-2.5-24b-a2b",
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
  "prompt_cache_key": "groundtruth-rout70lk-<sample>"
}
```
