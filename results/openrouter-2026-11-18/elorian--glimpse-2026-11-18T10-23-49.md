# elorian--glimpse

- Endpoint: `https://openrouter.ai/api/v1` · format `responses` · model `elorian/glimpse`
- Started 2026-11-18T10:23:49.631Z, finished 2026-11-18T10:31:28.280Z · status **stopped-early**
- Probe 0.3.4 · run salt `030a0q3w` · 3 replicas per age · prompt_cache_key per sample
- Request: `POST /responses` · body extra none · prefix ~2500 tokens · max output 16 · stream off · session_id none · warm at 0.5 of the prompt cached
- Headers: content-type `application/json`, authorization (value not recorded), x-api-key (value not recorded)
- Control: prime 0/2898 cached, re-send 1600/2898 → warm

**Lifetime: <2.5m – 5m**

| Age | Warm | Checks |
|---|---|---|
| 2.5m | 1 | 3 |
| 5m | 0 | 3 |
| 7.5m | 0 | 3 |

Request body (one sample):

```json
{
  "model": "elorian/glimpse",
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
  "prompt_cache_key": "groundtruth-030a0q3w-<sample>"
}
```
