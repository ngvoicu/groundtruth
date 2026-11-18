# baidu--ernie-5.5-flash-preview-free-paced

- Endpoint: `https://openrouter.ai/api/v1` · format `responses` · model `baidu/ernie-5.5-flash-preview:free`
- Started 2026-11-18T13:35:37.597Z, finished 2026-11-18T13:35:50.043Z · status **failed** (quota or rate refusal, not retried: HTTP 429: {"error":{"message":"Provider returned error","code":429,"metadata":{"raw":"baidu/ernie-5.5-flash-preview:free is temporarily rate-limited upstream. Please retry shortly, or add your own provider key to use your own limits: https://openrouter.ai/workspaces/default/byok","provider_name":"Baidu","is_b)
- Probe 0.3.4 · run salt `miinc74w` · 3 replicas per age · prompt_cache_key per sample
- Request: `POST /responses` · body extra none · prefix ~2500 tokens · max output 16 · stream off · session_id none · warm at 0.5 of the prompt cached
- Headers: content-type `application/json`, authorization (value not recorded), x-api-key (value not recorded)
- Control: prime 0/2413 cached, re-send 2304/2413 → warm

**Lifetime: no checks**

| Age | Warm | Checks |
|---|---|---|

Request body (one sample):

```json
{
  "model": "baidu/ernie-5.5-flash-preview:free",
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
  "prompt_cache_key": "groundtruth-miinc74w-<sample>"
}
```
