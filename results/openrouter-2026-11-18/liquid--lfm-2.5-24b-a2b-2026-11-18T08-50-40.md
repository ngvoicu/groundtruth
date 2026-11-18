# liquid--lfm-2.5-24b-a2b

- Endpoint: `https://openrouter.ai/api/v1` · format `responses` · model `liquid/lfm-2.5-24b-a2b`
- Started 2026-11-18T08:50:40.462Z, finished 2026-11-18T08:50:54.626Z · status **no-observable-cache** (an immediate re-send was not served from cache)
- Probe 0.3.3 · run salt `0p3557iv` · 3 replicas per age · prompt_cache_key per sample
- Request: `POST /responses` · body extra none · prefix ~2500 tokens · max output 16 · stream off · session_id none · warm at 0.5 of the prompt cached
- Headers: content-type `application/json`, authorization (value not recorded), x-api-key (value not recorded)
- Control: prime 0/2869 cached, re-send 0/2869 → cold

**Lifetime: no checks**

| Age | Warm | Checks |
|---|---|---|

Request body (one sample):

```json
{
  "model": "liquid/lfm-2.5-24b-a2b",
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
  "prompt_cache_key": "groundtruth-0p3557iv-<sample>"
}
```
