# nex-agi--nex-n2.5-mini

- Endpoint: `https://openrouter.ai/api/v1` · format `responses` · model `nex-agi/nex-n2.5-mini`
- Started 2026-11-18T08:44:15.764Z, finished 2026-11-18T10:44:49.722Z · status **completed**
- Probe 0.3.3 · run salt `mnku1ua1` · 3 replicas per age · prompt_cache_key per sample
- Request: `POST /responses` · body extra none · prefix ~2500 tokens · max output 16 · stream off · session_id none · warm at 0.5 of the prompt cached
- Headers: content-type `application/json`, authorization (value not recorded), x-api-key (value not recorded)
- Control: prime 0/2880 cached, re-send 2816/2880 → warm

**Lifetime: 2.5m – 90m**

| Age | Warm | Checks |
|---|---|---|
| 2.5m | 3 | 3 |
| 5m | 1 | 3 |
| 7.5m | 3 | 3 |
| 10m | 2 | 3 |
| 15m | 3 | 3 |
| 20m | 3 | 3 |
| 25m | 2 | 3 |
| 30m | 2 | 3 |
| 40m | 1 | 3 |
| 50m | 2 | 3 |
| 1h | 2 | 3 |
| 75m | 2 | 3 |
| 90m | 0 | 3 |
| 2h | 1 | 3 |

Request body (one sample):

```json
{
  "model": "nex-agi/nex-n2.5-mini",
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
  "prompt_cache_key": "groundtruth-mnku1ua1-<sample>"
}
```
