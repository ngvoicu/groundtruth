# google--gemini-4-carbon-8k

- Endpoint: `https://openrouter.ai/api/v1` · format `responses` · model `google/gemini-4-carbon`
- Started 2026-11-18T11:07:48.024Z, finished 2026-11-18T11:16:03.051Z · status **failed** (quota or rate refusal, not retried: HTTP 504: {"error":{"message":"The operation was aborted","code":504,"metadata":{"provider_name":"Google","previous_errors":[{"code":429,"message":"Provider returned error","provider_name":"Google AI Studio","raw":"google/gemini-4-carbon is temporarily rate-limited upstream. Please retry shortly, or add your )
- Probe 0.3.4 · run salt `fxplvscc` · 3 replicas per age · prompt_cache_key per sample
- Request: `POST /responses` · body extra none · prefix ~8000 tokens · max output 16 · stream off · session_id none · warm at 0.5 of the prompt cached
- Headers: content-type `application/json`, authorization (value not recorded), x-api-key (value not recorded)
- Control: prime 0/7528 cached, re-send 5474/7528 → warm

**Lifetime: <2.5m – 5m**

| Age | Warm | Checks |
|---|---|---|
| 2.5m | 1 | 3 |
| 5m | 0 | 3 |

Request body (one sample):

```json
{
  "model": "google/gemini-4-carbon",
  "input": [
    {
      "role": "developer",
      "content": [
        {
          "type": "input_text",
          "text": "<prefix: about 8000 tokens of words filler, one per sample>"
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
  "prompt_cache_key": "groundtruth-fxplvscc-<sample>"
}
```
