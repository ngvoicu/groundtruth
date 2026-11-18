# liquid--lfm-3-1.7b-free

- Endpoint: `https://openrouter.ai/api/v1` · format `responses` · model `liquid/lfm-3-1.7b:free`
- Started 2026-11-18T09:25:45.611Z, finished 2026-11-18T09:25:45.860Z · status **failed** (quota or rate refusal, not retried: HTTP 429: {"error":{"message":"Provider returned error","code":429,"metadata":{"raw":"liquid/lfm-3-1.7b:free is temporarily rate-limited upstream. Please retry shortly, or add your own provider key to use your own limits: https://openrouter.ai/workspaces/default/byok","provider_name":"Liquid","is_byok":false,)
- Probe 0.3.4 · run salt `90ldfeiy` · 3 replicas per age · prompt_cache_key per sample
- Request: `POST /responses` · body extra none · prefix ~2500 tokens · max output 16 · stream off · session_id none · warm at 0.5 of the prompt cached
- Headers: content-type `application/json`, authorization (value not recorded), x-api-key (value not recorded)

**Lifetime: no checks**

| Age | Warm | Checks |
|---|---|---|

Request body (one sample):

```json
{
  "model": "liquid/lfm-3-1.7b:free",
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
  "prompt_cache_key": "groundtruth-90ldfeiy-<sample>"
}
```
