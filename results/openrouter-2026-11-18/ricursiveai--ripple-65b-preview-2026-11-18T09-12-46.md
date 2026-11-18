# ricursiveai--ripple-65b-preview

- Endpoint: `https://openrouter.ai/api/v1` · format `responses` · model `ricursiveai/ripple-65b-preview`
- Started 2026-11-18T09:12:46.146Z, finished 2026-11-18T11:13:05.032Z · status **completed**
- Probe 0.3.4 · run salt `qbkdqywm` · 3 replicas per age · prompt_cache_key per sample
- Request: `POST /responses` · body extra none · prefix ~2500 tokens · max output 16 · stream off · session_id none · warm at 0.5 of the prompt cached
- Headers: content-type `application/json`, authorization (value not recorded), x-api-key (value not recorded)
- Control: prime 0/2673 cached, re-send 2624/2673 → warm

**Lifetime: 90m – 2h**

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
| 2h | 0 | 3 |

Request body (one sample):

```json
{
  "model": "ricursiveai/ripple-65b-preview",
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
  "prompt_cache_key": "groundtruth-qbkdqywm-<sample>"
}
```
