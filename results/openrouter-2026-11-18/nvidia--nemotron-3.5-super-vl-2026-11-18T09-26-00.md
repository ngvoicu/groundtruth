# nvidia--nemotron-3.5-super-vl

- Endpoint: `https://openrouter.ai/api/v1` · format `responses` · model `nvidia/nemotron-3.5-super-vl`
- Started 2026-11-18T09:26:00.728Z, finished 2026-11-18T11:26:14.907Z · status **completed**
- Probe 0.3.4 · run salt `norq2yib` · 3 replicas per age · prompt_cache_key per sample
- Request: `POST /responses` · body extra none · prefix ~2500 tokens · max output 16 · stream off · session_id none · warm at 0.5 of the prompt cached
- Headers: content-type `application/json`, authorization (value not recorded), x-api-key (value not recorded)
- Control: prime 0/2836 cached, re-send 2816/2836 → warm

**Lifetime: 2.5m – 30m**

| Age | Warm | Checks |
|---|---|---|
| 2.5m | 3 | 3 |
| 5m | 2 | 3 |
| 7.5m | 1 | 3 |
| 10m | 2 | 3 |
| 15m | 3 | 3 |
| 20m | 1 | 3 |
| 25m | 1 | 3 |
| 30m | 0 | 3 |
| 40m | 2 | 3 |
| 50m | 2 | 3 |
| 1h | 1 | 3 |
| 75m | 1 | 3 |
| 90m | 2 | 3 |
| 2h | 2 | 3 |

Request body (one sample):

```json
{
  "model": "nvidia/nemotron-3.5-super-vl",
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
  "prompt_cache_key": "groundtruth-norq2yib-<sample>"
}
```
