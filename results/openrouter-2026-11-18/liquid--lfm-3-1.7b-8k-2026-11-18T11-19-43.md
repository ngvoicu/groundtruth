# liquid--lfm-3-1.7b-8k

- Endpoint: `https://openrouter.ai/api/v1` · format `responses` · model `liquid/lfm-3-1.7b`
- Started 2026-11-18T11:19:43.760Z, finished 2026-11-18T11:25:00.666Z · status **stopped-early**
- Probe 0.3.4 · run salt `w81b6prl` · 3 replicas per age · prompt_cache_key per sample
- Request: `POST /responses` · body extra none · prefix ~8000 tokens · max output 16 · stream off · session_id none · warm at 0.5 of the prompt cached
- Headers: content-type `application/json`, authorization (value not recorded), x-api-key (value not recorded)
- Control: prime 0/9033 cached, re-send 8960/9033 → warm

**Lifetime: <2.5m – 2.5m**

| Age | Warm | Checks |
|---|---|---|
| 2.5m | 0 | 3 |
| 5m | 0 | 3 |

Request body (one sample):

```json
{
  "model": "liquid/lfm-3-1.7b",
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
  "prompt_cache_key": "groundtruth-w81b6prl-<sample>"
}
```
