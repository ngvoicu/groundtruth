# nex-agi--nex-n2.5-pro

- Endpoint: `https://openrouter.ai/api/v1` · format `responses` · model `nex-agi/nex-n2.5-pro`
- Started 2026-11-18T08:57:51.440Z, finished 2026-11-18T09:03:32.977Z · status **stopped-early**
- Probe 0.3.3 · run salt `i1svpjo7` · 3 replicas per age · prompt_cache_key per sample
- Request: `POST /responses` · body extra none · prefix ~2500 tokens · max output 16 · stream off · session_id none · warm at 0.5 of the prompt cached
- Headers: content-type `application/json`, authorization (value not recorded), x-api-key (value not recorded)
- Control: prime 0/2920 cached, re-send 2880/2920 → warm

**Lifetime: <2.5m – 2.5m**

| Age | Warm | Checks |
|---|---|---|
| 2.5m | 0 | 3 |
| 5m | 0 | 3 |

Request body (one sample):

```json
{
  "model": "nex-agi/nex-n2.5-pro",
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
  "prompt_cache_key": "groundtruth-i1svpjo7-<sample>"
}
```
