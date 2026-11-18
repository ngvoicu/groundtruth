# thinkingmachines--inkling-2-small-free

- Endpoint: `https://openrouter.ai/api/v1` · format `responses` · model `thinkingmachines/inkling-2-small:free`
- Started 2026-11-18T13:32:19.757Z, finished 2026-11-18T13:32:19.868Z · status **failed** (HTTP 403: {"error":{"message":"This model is not available in your region.","code":403,"metadata":{"routing_funnel":[{"step":"Initial Endpoints","endpoint_count":1}],"failed_routing_step":"Gate Thinking Machines Endpoints with Geo Restrictions"}}})
- Probe 0.3.4 · run salt `czgtv2jt` · 3 replicas per age · prompt_cache_key per sample
- Request: `POST /responses` · body extra none · prefix ~2500 tokens · max output 16 · stream off · session_id none · warm at 0.5 of the prompt cached
- Headers: content-type `application/json`, authorization (value not recorded), x-api-key (value not recorded)

**Lifetime: no checks**

| Age | Warm | Checks |
|---|---|---|

Request body (one sample):

```json
{
  "model": "thinkingmachines/inkling-2-small:free",
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
  "prompt_cache_key": "groundtruth-czgtv2jt-<sample>"
}
```
