# deepseek--deepseek-v4.1-flash-1017

- Endpoint: `https://openrouter.ai/api/v1` · format `responses` · model `deepseek/deepseek-v4.1-flash-1017`
- Started 2026-11-18T08:44:45.883Z, finished 2026-11-18T09:09:54.078Z · status **stopped-early**
- Probe 0.3.3 · run salt `9bq1ftye` · 3 replicas per age · prompt_cache_key per sample
- Request: `POST /responses` · body extra none · prefix ~2500 tokens · max output 16 · stream off · session_id none · warm at 0.5 of the prompt cached
- Headers: content-type `application/json`, authorization (value not recorded), x-api-key (value not recorded)
- Control: prime 0/2548 cached, re-send 2432/2548 → warm

**Lifetime: 2.5m – 20m**

| Age | Warm | Checks |
|---|---|---|
| 2.5m | 3 | 3 |
| 5m | 2 | 3 |
| 7.5m | 2 | 3 |
| 10m | 2 | 3 |
| 15m | 2 | 3 |
| 20m | 0 | 3 |
| 25m | 0 | 3 |

Request body (one sample):

```json
{
  "model": "deepseek/deepseek-v4.1-flash-1017",
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
  "prompt_cache_key": "groundtruth-9bq1ftye-<sample>"
}
```
