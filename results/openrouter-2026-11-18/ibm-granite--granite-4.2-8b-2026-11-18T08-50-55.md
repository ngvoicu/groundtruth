# ibm-granite--granite-4.2-8b

- Endpoint: `https://openrouter.ai/api/v1` · format `responses` · model `ibm-granite/granite-4.2-8b`
- Started 2026-11-18T08:50:55.521Z, finished 2026-11-18T09:01:03.880Z · status **stopped-early**
- Probe 0.3.3 · run salt `rbt3gz22` · 3 replicas per age · prompt_cache_key per sample
- Request: `POST /responses` · body extra none · prefix ~2500 tokens · max output 16 · stream off · session_id none · warm at 0.5 of the prompt cached
- Headers: content-type `application/json`, authorization (value not recorded), x-api-key (value not recorded)
- Control: prime 0/2819 cached, re-send 2816/2819 → warm

**Lifetime: 2.5m – 7.5m**

| Age | Warm | Checks |
|---|---|---|
| 2.5m | 3 | 3 |
| 5m | 2 | 3 |
| 7.5m | 0 | 3 |
| 10m | 0 | 3 |

Request body (one sample):

```json
{
  "model": "ibm-granite/granite-4.2-8b",
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
  "prompt_cache_key": "groundtruth-rbt3gz22-<sample>"
}
```
