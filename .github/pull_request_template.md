## What was measured

Route, client, model, options, and the day it was sent:

## Checklist (see CONTRIBUTING.md)

- [ ] The raw result files are under `results/<folder>/`, with a short README: what, how, which day, what came out.
- [ ] The run is in `observed/manifest.json`: route, client, model and options, nothing that is a result.
- [ ] `observed.json` is rebuilt with `python3 scripts/build_observed.py`.
- [ ] The pre-commit check is installed and passed: no credential, e-mail address, home-folder path or session file.
- [ ] The control hit, and every age has the usual samples (three, from 2.5 minutes), or the README says why not.
- [ ] Nothing is left out silently: a run left out is in the folder and in `excluded`, with its reason.
- [ ] For a limit: an accepted size and a refused one from the same walk, a window the provider names, or a read check.
