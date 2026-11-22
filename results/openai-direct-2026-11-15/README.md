# GPT-6.1 Sol on the OpenAI API, default and 12-hour cache, 2026-11-15

The owner's run. Plain probe (`src/cli.ts`, 0.2.0) straight to `https://api.openai.com/v1` with an OpenAI API key, no
proxy. Responses format, a per-sample `prompt_cache_key`, about 2,400-token prompts, 3 samples per age, schedule `long`
(2.5 minutes to 12 hours) plus 24 hours. Both runs started in the same minute (2026-11-15 18:23:51 UTC).

| Run | Request | Control | Warm at each age | Lifetime |
|---|---|---|---|---|
| `openai-sol-default` | no lifetime asked | warm | 3/3 from 2.5 to 30 min; 0/3 at 40 and 50 min (stopped after two cold ages) | **30 – 40 min** |
| `openai-sol-12h` | `prompt_cache_options.ttl: "12h"` | warm | 3/3 at every age from 2.5 min to 12 h; 0/3 at 24 h | **12 h – 24 h** |

**What the 12-hour run sent is not in its result file.** The probe does not record the request body (an extra field
given with `--body-extra` included), and neither the result files nor the logs show the command line. The setting
`prompt_cache_options.ttl: "12h"` is known from the owner's own note on this run (written when it was made, with a
trial that showed OpenAI's usage reporting the write under its 12-hour tier) and from the run's label. The result
agrees with it: the default run, started in the same minute, was cold at 40 minutes; this one was warm through
12 hours. OpenAI documents `prompt_cache_options.ttl` (`30m` by default, or `12h`) for the Responses API of GPT-5.6
and later.

The default run matches OpenAI's documented 30 minutes and the GPT-6 runs on an API key through Provimux
(`../gpt6-2026-11-11`, G5 – G7: warm at 30 min, cold at 40). With the 12-hour setting the cache held every check to
12 hours and was gone at 24.
