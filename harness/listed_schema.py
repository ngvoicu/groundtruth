#!/usr/bin/env python3
"""The schema of listed.json (schema 1): what discovery (harness/discover.py) writes and providers.dev reads.

    python3 harness/listed_schema.py listed.json      # exit 0 when the file is valid or absent, 1 with the reasons

providers.dev's own schema is `ListedFile` in its `src/core/schema.ts` (API 1.5.x); this one is the same, never looser,
and stricter where it costs nothing:

- a key the schema does not name is refused, at every level (the file, a provider's part, a model, its reasoning);
- no string anywhere may look like an e-mail address, a credential or a file name: an account never gets in;
- a model id is lower-case letters, digits and . _ : / -, at most 64 characters, once per provider;
- a provider id is the catalog's shape; its part has a date, the client that read the list, and at least one model;
- the fields providers.dev accepts and never reads (owner, released, aliases, variants, description, disable_with)
  are accepted only as short plain values. Discovery writes none of them.

CI runs it on the committed file; the pre-commit hook on the staged one; discover.py before it writes.
"""
import json
import os
import re
import sys

SCHEMA = 1
REPOSITORY = "https://github.com/ngvoicu/groundtruth"
# providers.dev's patterns (src/core/schema.ts): PROVIDER_ID, LISTED_MODEL_ID, the client, isoDate.
PROVIDER_ID = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
MODEL_ID = re.compile(r"^[a-z0-9][a-z0-9._:/-]{0,63}$")
CLIENT = re.compile(r"^[a-z0-9][a-z0-9+._-]{0,63}$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# A plain display name (providers.dev's `displayName`): letters, digits, spaces and . , - _ / + ( ), at most 80.
NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 .,_/+()-]{0,79}$")
# A lower-case word: a modality (or a media type), a reasoning level.
WORD = re.compile(r"^[a-z0-9][a-z0-9._/+-]{0,63}$")
# providers.dev's EMAIL_SHAPED and TOKEN_SHAPED, applied here to every string of the file.
EMAIL_SHAPED = re.compile(r"[^\s@]+@[^\s@]+\.[a-z]{2,}", re.I)
TOKEN_SHAPED = re.compile(r"(^|[^a-z0-9])(sk-|gh[opusr]_|github_pat_|xox[a-z]-|aiza|ya29\.|eyj[a-z0-9_-]{8})|[a-z0-9]{24}",
                          re.I)
FILE_NAME = re.compile(r"\.(json|ya?ml|txt|env|key|pem)$", re.I)

FILE_KEYS = {"schema", "repository", "providers"}
PART_KEYS = {"date", "client", "models"}
COUNTS = ("context_window", "max_input", "max_output")
WORD_LISTS = ("input_modalities", "output_modalities", "plans")
FLAGS = ("web_search", "hidden")
# Accepted by providers.dev and never read; discovery writes none of them, so they are held to short plain values.
IGNORED_TEXT = ("owner", "released", "description")
IGNORED_IDS = ("aliases", "variants")
MODEL_KEYS = {"id", "name", "reasoning", *COUNTS, *WORD_LISTS, *FLAGS, *IGNORED_TEXT, *IGNORED_IDS}
REASONING_KEYS = {"supported", "levels", "budget_min", "budget_max", "can_disable", "dynamic", "disable_with"}


def is_count(value, minimum=1):
    return isinstance(value, int) and not isinstance(value, bool) and value >= minimum


def unsafe(text):
    """Why a string may not be in the file, or None."""
    if EMAIL_SHAPED.search(text):
        return "looks like an e-mail address"
    if TOKEN_SHAPED.search(text):
        return "looks like a credential"
    if FILE_NAME.search(text):
        return "looks like a file name"
    return None


def model_id_problem(value):
    if not isinstance(value, str) or not MODEL_ID.match(value):
        return "not a model id"
    return unsafe(value)


def name_problem(value):
    if not isinstance(value, str) or not NAME.match(value):
        return "not a plain display name"
    return unsafe(value)


def word_problem(value):
    if not isinstance(value, str) or not WORD.match(value):
        return "not a lower-case word"
    return unsafe(value)


def _words(errors, where, value, limit=64):
    if not isinstance(value, list) or len(value) > limit:
        errors.append(f"{where}: not a list of at most {limit} words")
        return
    for i, item in enumerate(value):
        problem = word_problem(item)
        if problem:
            errors.append(f"{where}[{i}]: {problem}")


def _model(errors, where, model):
    if not isinstance(model, dict):
        errors.append(f"{where}: not an object")
        return
    for key in sorted(set(model) - MODEL_KEYS):
        errors.append(f"{where}: field {key!r} is not in the schema")
    if "id" not in model:
        errors.append(f"{where}: no id")
    else:
        problem = model_id_problem(model["id"])
        if problem:
            errors.append(f"{where}.id: {problem}")
    if "name" in model:
        problem = name_problem(model["name"])
        if problem:
            errors.append(f"{where}.name: {problem}")
    for key in COUNTS:
        if key in model and not is_count(model[key]):
            errors.append(f"{where}.{key}: not a positive whole number")
    for key in WORD_LISTS:
        if key in model:
            _words(errors, f"{where}.{key}", model[key])
    for key in FLAGS:
        if key in model and not isinstance(model[key], bool):
            errors.append(f"{where}.{key}: not true or false")
    for key in IGNORED_TEXT:
        if key in model:
            value = model[key]
            if not isinstance(value, str) or len(value) > 200 or not value.strip():
                errors.append(f"{where}.{key}: not a short text")
            elif unsafe(value):
                errors.append(f"{where}.{key}: {unsafe(value)}")
    for key in IGNORED_IDS:
        if key in model:
            value = model[key]
            if not isinstance(value, list) or len(value) > 32:
                errors.append(f"{where}.{key}: not a list of at most 32 model ids")
                continue
            for i, item in enumerate(value):
                problem = model_id_problem(item)
                if problem:
                    errors.append(f"{where}.{key}[{i}]: {problem}")
    if "reasoning" in model:
        reasoning = model["reasoning"]
        if not isinstance(reasoning, dict):
            errors.append(f"{where}.reasoning: not an object")
            return
        for key in sorted(set(reasoning) - REASONING_KEYS):
            errors.append(f"{where}.reasoning: field {key!r} is not in the schema")
        if "levels" in reasoning:
            _words(errors, f"{where}.reasoning.levels", reasoning["levels"], limit=16)
        for key in ("budget_min", "budget_max"):
            if key in reasoning and not is_count(reasoning[key], minimum=0):
                errors.append(f"{where}.reasoning.{key}: not a whole number")
        for key in ("supported", "can_disable", "dynamic"):
            if key in reasoning and not isinstance(reasoning[key], bool):
                errors.append(f"{where}.reasoning.{key}: not true or false")
        if "disable_with" in reasoning:
            problem = word_problem(reasoning["disable_with"])
            if problem:
                errors.append(f"{where}.reasoning.disable_with: {problem}")


def validate(doc):
    """Every reason the document is not a valid listed.json; [] when it is."""
    errors = []
    if not isinstance(doc, dict):
        return ["the file is not a JSON object"]
    for key in sorted(set(doc) - FILE_KEYS):
        errors.append(f"field {key!r} is not in the schema")
    if doc.get("schema") != SCHEMA or isinstance(doc.get("schema"), bool):
        errors.append(f"schema: not {SCHEMA}")
    if "repository" in doc and doc["repository"] != REPOSITORY:
        errors.append(f"repository: not {REPOSITORY}")
    providers = doc.get("providers")
    if not isinstance(providers, dict):
        errors.append("providers: not an object")
        return errors
    for provider, part in providers.items():
        where = f"providers.{provider}"
        if not PROVIDER_ID.match(provider) or unsafe(provider):
            errors.append(f"{where}: not a provider id")
        if not isinstance(part, dict):
            errors.append(f"{where}: not an object")
            continue
        for key in sorted(set(part) - PART_KEYS):
            errors.append(f"{where}: field {key!r} is not in the schema")
        if not isinstance(part.get("date"), str) or not DATE.match(part["date"]):
            errors.append(f"{where}.date: not a date like 2026-11-24")
        client = part.get("client")
        if not isinstance(client, str) or not CLIENT.match(client) or unsafe(client):
            errors.append(f"{where}.client: not a client id")
        models = part.get("models")
        if not isinstance(models, list) or not models:
            errors.append(f"{where}.models: not a list with at least one model")
            continue
        seen = set()
        for i, model in enumerate(models):
            _model(errors, f"{where}.models[{i}]", model)
            mid = model.get("id") if isinstance(model, dict) else None
            if isinstance(mid, str):
                if mid in seen:
                    errors.append(f"{where}.models[{i}]: {mid} is listed twice")
                seen.add(mid)
    return errors


def main(argv):
    if len(argv) != 2:
        sys.exit(__doc__)
    path = argv[1]
    if not os.path.exists(path):
        print(f"{path}: absent (no discovery yet): nothing to check")
        return 0
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, ValueError) as err:
        print(f"{path}: not JSON ({type(err).__name__})")
        return 1
    errors = validate(doc)
    for line in errors[:50]:
        print(f"{path}: {line}")
    if len(errors) > 50:
        print(f"{path}: … and {len(errors) - 50} more")
    if errors:
        return 1
    models = sum(len(p["models"]) for p in doc["providers"].values())
    print(f"{path}: valid (schema {SCHEMA}, {len(doc['providers'])} providers, {models} models)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
