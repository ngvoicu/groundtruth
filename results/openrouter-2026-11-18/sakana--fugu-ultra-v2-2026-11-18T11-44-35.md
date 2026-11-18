# sakana--fugu-ultra-v2

- Endpoint: `https://openrouter.ai/api/v1` · format `responses` · model `sakana/fugu-ultra-v2`
- Started 2026-11-18T11:44:35.805Z, finished 2026-11-18T11:44:36.314Z · status **failed** (HTTP 403: {"error":{"message":"sakana/fugu-ultra-v2 is not available in your region: Sakana AI blocks requests originating from your location.","code":403,"metadata":{"raw":"sakana/fugu-ultra-v2 is not available in your region: Sakana AI blocks requests originating from your location.","provider_name":"Sakana)
- Probe 0.3.4 · run salt `dwfhcsyu` · 3 replicas per age · prompt_cache_key per sample
- Request: `POST /responses` · body extra none · prefix ~2500 tokens · max output 16 · stream off · session_id none · warm at 0.5 of the prompt cached
- Headers: content-type `application/json`, authorization (value not recorded), x-api-key (value not recorded)

**Lifetime: no checks**

| Age | Warm | Checks |
|---|---|---|

Request body (one sample):

```json
{
  "model": "sakana/fugu-ultra-v2",
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
  "prompt_cache_key": "groundtruth-dwfhcsyu-<sample>"
}
```
