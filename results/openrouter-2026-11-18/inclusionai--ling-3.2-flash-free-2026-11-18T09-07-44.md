# inclusionai--ling-3.2-flash-free

- Endpoint: `https://openrouter.ai/api/v1` · format `responses` · model `inclusionai/ling-3.2-flash:free`
- Started 2026-11-18T09:07:44.216Z, finished 2026-11-18T09:13:11.687Z · status **failed** (quota or rate refusal, not retried: HTTP 429: {"error":{"message":"Provider returned error","code":429,"metadata":{"raw":"inclusionai/ling-3.2-flash:free is temporarily rate-limited upstream. Please retry shortly, or add your own provider key to use your own limits: https://openrouter.ai/workspaces/default/byok","provider_name":"Ant Digital","i)
- Probe 0.3.4 · run salt `8wacitb5` · 3 replicas per age · prompt_cache_key per sample
- Request: `POST /responses` · body extra none · prefix ~2500 tokens · max output 16 · stream off · session_id none · warm at 0.5 of the prompt cached
- Headers: content-type `application/json`, authorization (value not recorded), x-api-key (value not recorded)
- Control: prime 0/2744 cached, re-send 2688/2744 → warm

**Lifetime: <5m – 5m**

| Age | Warm | Checks |
|---|---|---|
| 5m | 0 | 1 |

Request body (one sample):

```json
{
  "model": "inclusionai/ling-3.2-flash:free",
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
  "prompt_cache_key": "groundtruth-8wacitb5-<sample>"
}
```
