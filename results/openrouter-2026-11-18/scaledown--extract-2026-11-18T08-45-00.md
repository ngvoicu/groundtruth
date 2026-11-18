# scaledown--extract

- Endpoint: `https://openrouter.ai/api/v1` · format `responses` · model `scaledown/extract`
- Started 2026-11-18T08:45:00.948Z, finished 2026-11-18T08:45:01.121Z · status **failed** (HTTP 400: {"error":{"message":"extract requires a response_format of type \"json_schema\" whose schema properties describe the entities to extract, or provider.options.scaledown.entities mapping each entity name to its definition. If entities were sent, check that the key is spelled \"scaledown\" and that thi)
- Probe 0.3.3 · run salt `84wqms0c` · 3 replicas per age · prompt_cache_key per sample
- Request: `POST /responses` · body extra none · prefix ~2500 tokens · max output 16 · stream off · session_id none · warm at 0.5 of the prompt cached
- Headers: content-type `application/json`, authorization (value not recorded), x-api-key (value not recorded)

**Lifetime: no checks**

| Age | Warm | Checks |
|---|---|---|

Request body (one sample):

```json
{
  "model": "scaledown/extract",
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
  "prompt_cache_key": "groundtruth-84wqms0c-<sample>"
}
```
