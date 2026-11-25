# Values not measured: above the caps

The owner's caps for the API keys stand: **$10 a week**, **$2 a cache run**; a window check may pass $2 but must fit
the week (docs/weekly-night.md, "The caps"). A value whose worst case is above them is decided here once, instead of
being asked about every Monday.

The weekly night's plan (harness/plan.py) reads this table. A value in it whose worst case is still above the caps is
named in the plan as "not measured: above the caps (decided <date>)", is not sent and raises no ask. When its worst
case falls under the caps (a price drops), its row no longer applies: the value is planned again, and the plan lists
the row as one that can go. A new value above the caps raises its ask once; the ask gives the row to add here.

A row: the value as `--value` takes it (`<route>:<model>:<quantity>`, quantity `cache` or `window`), the day it was
decided, who decided, why. Any other row in the table stops the night before it starts (an ask says which line).

| Value | Decided | By | Reason |
|---|---|---|---|
| `openai-api:gpt-6-cyber:window` | 2026-11-25 | the owner's caps | worst case $23.12, more than the week's $10 |
| `openai-api:gpt-6-cyber:cache` | 2026-11-25 | the owner's caps | worst case $5.50, above the $2 a run |
| `openrouter:openai/gpt-6.2-astra:cache` | 2026-11-25 | the owner's caps | worst case $2.72, above the $2 a run |
| `openrouter:openai/gpt-6.2-astra-pro:cache` | 2026-11-25 | the owner's caps | worst case $2.72, above the $2 a run |
