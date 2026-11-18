# google--gemini-4-hydrogen-8k

- Endpoint: `https://openrouter.ai/api/v1` · format `responses` · model `google/gemini-4-hydrogen`
- Started 2026-11-18T11:14:47.334Z, finished 2026-11-18T11:25:07.574Z · status **stopped-early**
- Probe 0.3.4 · run salt `hs3v2tod` · 3 replicas per age · prompt_cache_key per sample
- Request: `POST /responses` · body extra none · prefix ~8000 tokens · max output 16 · stream off · session_id none · warm at 0.5 of the prompt cached
- Headers: content-type `application/json`, authorization (value not recorded), x-api-key (value not recorded)
- Control: prime 0/7515 cached, re-send 5461/7515 → warm

**Lifetime: <2.5m – 7.5m**

| Age | Warm | Checks |
|---|---|---|
| 2.5m | 2 | 3 |
| 5m | 1 | 3 |
| 7.5m | 0 | 3 |
| 10m | 0 | 3 |

Request body (one sample):

```json
{
  "model": "google/gemini-4-hydrogen",
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
  "prompt_cache_key": "groundtruth-hs3v2tod-<sample>"
}
```
