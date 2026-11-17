# oa-daybreak-blue

- Endpoint: `https://api.openai.com/v1` · format `responses` · model `gpt-daybreak-blue-latest`
- Started 2026-11-17T12:22:29.075Z, finished 2026-11-17T12:22:29.267Z · status **failed** (HTTP 404: {
  "error": {
    "message": "The model `gpt-daybreak-blue-latest` does not exist or you do not have access to it.",
    "type": "invalid_request_error",
    "param": null,
    "code": "model_not_found"
  }
})
- Probe 0.3.0 · run salt `x3jwixbu` · 3 replicas per age · prompt_cache_key per sample
- Request: `POST /responses` · body extra none · prefix ~2500 tokens · max output 16 · stream off · session_id none · warm at 0.5 of the prompt cached
- Headers: content-type `application/json`, authorization (value not recorded), x-api-key (value not recorded)

**Lifetime: no checks**

| Age | Warm | Checks |
|---|---|---|

Request body (one sample):

```json
{
  "model": "gpt-daybreak-blue-latest",
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
  "prompt_cache_key": "groundtruth-x3jwixbu-<sample>"
}
```
