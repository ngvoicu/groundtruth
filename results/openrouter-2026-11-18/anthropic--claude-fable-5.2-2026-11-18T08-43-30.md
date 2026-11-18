# anthropic--claude-fable-5.2

- Endpoint: `https://openrouter.ai/api/v1` · format `responses` · model `anthropic/claude-fable-5.2`
- Started 2026-11-18T08:43:30.565Z, finished 2026-11-18T08:53:50.974Z · status **stopped-early**
- Probe 0.3.3 · run salt `01sg0hgq` · 3 replicas per age · prompt_cache_key per sample
- Request: `POST /responses` · body extra `{"cache_control":{"type":"ephemeral"}}` · prefix ~2500 tokens · max output 16 · stream off · session_id per-sample · warm at 0.5 of the prompt cached
- Headers: content-type `application/json`, authorization (value not recorded), x-api-key (value not recorded)
- Control: prime 0/4284 cached, re-send 4280/4284 → warm

**Lifetime: 5m – 7.5m**

| Age | Warm | Checks |
|---|---|---|
| 2.5m | 3 | 3 |
| 5m | 3 | 3 |
| 7.5m | 0 | 3 |
| 10m | 0 | 3 |

Request body (one sample):

```json
{
  "model": "anthropic/claude-fable-5.2",
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
  "prompt_cache_key": "groundtruth-01sg0hgq-<sample>",
  "session_id": "groundtruth-01sg0hgq-<sample>",
  "cache_control": {
    "type": "ephemeral"
  }
}
```
