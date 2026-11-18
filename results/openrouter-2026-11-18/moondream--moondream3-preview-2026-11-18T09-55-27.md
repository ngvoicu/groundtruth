# moondream--moondream3-preview

- Endpoint: `https://openrouter.ai/api/v1` · format `responses` · model `moondream/moondream3-preview`
- Started 2026-11-18T09:55:27.690Z, finished 2026-11-18T10:03:03.931Z · status **stopped-early**
- Probe 0.3.4 · run salt `p9ez479w` · 3 replicas per age · prompt_cache_key per sample
- Request: `POST /responses` · body extra none · prefix ~2500 tokens · max output 16 · stream off · session_id none · warm at 0.5 of the prompt cached
- Headers: content-type `application/json`, authorization (value not recorded), x-api-key (value not recorded)
- Control: prime 4/2669 cached, re-send 2668/2669 → warm

**Lifetime: 2.5m – 5m**

| Age | Warm | Checks |
|---|---|---|
| 2.5m | 3 | 3 |
| 5m | 0 | 3 |
| 7.5m | 0 | 3 |

Request body (one sample):

```json
{
  "model": "moondream/moondream3-preview",
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
  "prompt_cache_key": "groundtruth-p9ez479w-<sample>"
}
```
