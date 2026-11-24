"""A fake `gh api --include` for discovery's tests: GitHub's contents API on a folder, every call recorded. Nothing
leaves the machine. The folder is $FAKE_GH:

    calls.jsonl       every call: {"argv": [...], "stdin": text or null}
    main/listed.json  the file on "main" (absent: 404)
    commits.jsonl     every accepted PUT: message, branch, author, committer, sha it replaced
    put-statuses      one status per line, used (and removed) by the next PUTs instead of handling them (e.g. 409)
    before-put        when present, becomes main/listed.json just before the next PUT (someone else wrote meanwhile)
    get-status        a status every GET answers with (e.g. 500)
    large             when present, the contents GET gives no content (a file over 1 MB): the blob must be read

Also `osascript` (FAKE_AS=osascript): records its argv in osascript.jsonl.
"""
import base64
import hashlib
import json
import os
import sys

root = os.environ["FAKE_GH"]
FILE = os.path.join(root, "main", "listed.json")


def record(name, value):
    with open(os.path.join(root, name), "a") as f:
        f.write(json.dumps(value) + "\n")


def sha_of(data):
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def answer(status, body):
    reason = {200: "OK", 201: "Created", 404: "Not Found", 409: "Conflict", 422: "Unprocessable Entity",
              500: "Internal Server Error"}.get(status, "Status")
    sys.stdout.write(f"HTTP/2.0 {status} {reason}\r\nContent-Type: application/json; charset=utf-8\r\n"
                     f"X-Fake: 1\r\n\r\n{json.dumps(body)}")
    if status >= 300:
        sys.stderr.write(f"gh: {reason} (HTTP {status})\n")
        sys.exit(1)
    sys.exit(0)


def current():
    try:
        with open(FILE, "rb") as f:
            return f.read()
    except FileNotFoundError:
        return None


def main():
    if os.environ.get("FAKE_AS") == "osascript":
        record("osascript.jsonl", sys.argv[1:])
        return
    argv = sys.argv[1:]
    stdin = sys.stdin.read() if "--input" in argv else None
    record("calls.jsonl", {"argv": argv, "stdin": stdin})
    assert argv[:2] == ["api", "--include"], argv
    method = argv[argv.index("--method") + 1]
    path = next(a for a in argv[2:] if a.startswith("repos/"))
    if method == "GET":
        forced = os.path.join(root, "get-status")
        if os.path.exists(forced):
            answer(int(open(forced).read().strip()), {"message": "forced"})
        data = current()
        if path.startswith("repos/ngvoicu/groundtruth/git/blobs/"):
            if data is None or path.rsplit("/", 1)[1] != sha_of(data):
                answer(404, {"message": "Not Found"})
            answer(200, {"sha": sha_of(data), "content": base64.b64encode(data).decode(), "encoding": "base64"})
        assert path == "repos/ngvoicu/groundtruth/contents/listed.json?ref=main", path
        if data is None:
            answer(404, {"message": "Not Found"})
        if os.path.exists(os.path.join(root, "large")):
            answer(200, {"sha": sha_of(data), "content": "", "encoding": "none", "size": len(data)})
        answer(200, {"sha": sha_of(data), "content": base64.encodebytes(data).decode(), "encoding": "base64"})
    assert method == "PUT" and path == "repos/ngvoicu/groundtruth/contents/listed.json", argv
    body = json.loads(stdin)
    statuses = os.path.join(root, "put-statuses")
    if os.path.exists(statuses):
        lines = open(statuses).read().split()
        if lines:
            with open(statuses, "w") as f:
                f.write("\n".join(lines[1:]))
            answer(int(lines[0]), {"message": "forced"})
    meanwhile = os.path.join(root, "before-put")
    if os.path.exists(meanwhile):
        os.makedirs(os.path.dirname(FILE), exist_ok=True)
        os.replace(meanwhile, FILE)
    data = current()
    if data is not None and body.get("sha") != sha_of(data):
        answer(409, {"message": "listed.json does not match " + str(body.get("sha"))})
    if data is None and body.get("sha"):
        answer(422, {"message": "sha given for a file that does not exist"})
    new = base64.b64decode(body["content"])
    os.makedirs(os.path.dirname(FILE), exist_ok=True)
    with open(FILE, "wb") as f:
        f.write(new)
    record("commits.jsonl", {k: body.get(k) for k in ("message", "branch", "author", "committer", "sha")})
    answer(201 if data is None else 200, {"content": {"sha": sha_of(new)}, "commit": {"sha": "c0ffee" + sha_of(new)[:34]}})


if __name__ == "__main__":
    main()
