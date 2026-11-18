# meta--muse-spark-1.3-contributor

- Endpoint: `https://openrouter.ai/api/v1` · format `responses` · model `meta/muse-spark-1.3-contributor`
- Started 2026-11-18T09:12:31.071Z, finished 2026-11-18T09:12:31.171Z · status **failed** (HTTP 404: {"error":{"message":"0 endpoints out of 1 requested are available matching your guardrail restrictions and data policy. We removed them for the following reasons (an endpoint may have matched multiple reasons):\nPaid model training violation (account settings): 1 endpoint excluded; configurable at h)
- Probe 0.3.4 · run salt `8frqg5d6` · 3 replicas per age · prompt_cache_key per sample
- Request: `POST /responses` · body extra none · prefix ~2500 tokens · max output 16 · stream off · session_id none · warm at 0.5 of the prompt cached
- Headers: content-type `application/json`, authorization (value not recorded), x-api-key (value not recorded)

**Lifetime: no checks**

| Age | Warm | Checks |
|---|---|---|

Request body (one sample):

```json
{
  "model": "meta/muse-spark-1.3-contributor",
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
  "prompt_cache_key": "groundtruth-8frqg5d6-<sample>"
}
```
