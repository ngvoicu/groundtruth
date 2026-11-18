# alias-openai--gpt-astra-latest

- Endpoint: `https://openrouter.ai/api/v1` · format `responses` · model `~openai/gpt-astra-latest`
- Started 2026-11-18T13:54:06.696Z, finished 2026-11-18T14:34:29.993Z · status **stopped-early**
- Probe 0.3.4 · run salt `afue3lkp` · 3 replicas per age · prompt_cache_key per sample
- Request: `POST /responses` · body extra none · prefix ~2500 tokens · max output 16 · stream off · session_id none · warm at 0.5 of the prompt cached
- Headers: content-type `application/json`, authorization (value not recorded), x-api-key (value not recorded)
- Control: prime 0/2418 cached, re-send 2418/2418 → warm

**Lifetime: 25m – 30m**

| Age | Warm | Checks |
|---|---|---|
| 2.5m | 3 | 3 |
| 5m | 3 | 3 |
| 7.5m | 3 | 3 |
| 10m | 3 | 3 |
| 15m | 3 | 3 |
| 20m | 3 | 3 |
| 25m | 3 | 3 |
| 30m | 0 | 3 |
| 40m | 0 | 3 |

Request body (one sample):

```json
{
  "model": "~openai/gpt-astra-latest",
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
  "prompt_cache_key": "groundtruth-afue3lkp-<sample>"
}
```
