import assert from "node:assert/strict";
import { test } from "node:test";
import { type Deps, lateAfterMs, type RunOptions, runProbe } from "../src/run.ts";
import { bracket, renderMarkdown, summarize } from "../src/report.ts";

// A fake upstream with an idle-timeout cache, driven by a fake clock (no wall-clock sleeps).
function fakeUpstream(ttlMs: number, opts: { refreshOnHit?: boolean; caches?: boolean; failFirst?: number } = {}) {
  let clock = 1_000_000;
  const entries = new Map<string, number>();
  let failures = opts.failFirst ?? 0;
  let calls = 0;
  const deps: Deps = {
    now: () => clock,
    sleep: async (ms) => { clock += ms; },
    log: () => {},
    send: async (_url, _headers, body) => {
      calls++;
      if (failures > 0) { failures--; return { status: 503, text: "busy" }; }
      const prefix = (JSON.parse(body).input[0].content[0].text as string);
      const prompt = 2600;
      const last = entries.get(prefix);
      const hit = opts.caches !== false && last !== undefined && clock - last < ttlMs;
      if (opts.caches !== false && (!hit || opts.refreshOnHit !== false)) entries.set(prefix, clock);
      clock += 1_000; // each request takes a second
      return { status: 200, text: JSON.stringify({ usage: { input_tokens: prompt, input_tokens_details: { cached_tokens: hit ? 2560 : 0 } } }) };
    },
  };
  return { deps, calls: () => calls };
}

const opts = (ages: number[], replicas = 3): RunOptions => ({
  baseUrl: "http://x/v1", format: "responses", model: "m", headers: {}, ages, replicas, maxOutput: 16,
  stream: false, prefixTokens: 50, runSalt: "t", concurrency: 2, label: "fake",
});

const MIN = 60_000;

test("measures a 10-minute idle cache", async () => {
  const { deps } = fakeUpstream(10 * MIN);
  const r = await runProbe(opts([5 * MIN, 7.5 * MIN, 15 * MIN, 20 * MIN, 30 * MIN]), deps);
  assert.equal(r.control?.warm, true);
  const s = summarize(r);
  assert.equal(s.lastAllWarmMs, 7.5 * MIN);
  assert.equal(s.firstMissMs, 15 * MIN);
  assert.equal(s.allColdMs, 15 * MIN);
  assert.equal(r.status, "stopped-early", "two cold ages (15m, 20m) stop the run before 30m");
  assert.equal(r.checks.filter((c) => c.targetAgeMs === 30 * MIN).length, 0);
  assert.match(bracket(s), /7.5m – 15m/);
  assert.match(renderMarkdown(r), /\| 15m \| 0 \| 3 \|/);
});

test("each sample is checked exactly once", async () => {
  const { deps } = fakeUpstream(60 * MIN);
  const r = await runProbe(opts([5 * MIN, 10 * MIN], 2), deps);
  assert.equal(r.status, "completed");
  assert.equal(r.checks.length, 4);
  assert.equal(new Set(r.checks.map((c) => c.sampleId)).size, 4);
  for (const c of r.checks) assert.ok(c.actualAgeMs >= c.targetAgeMs);
});

test("no observable cache stops after the control round", async () => {
  const { deps, calls } = fakeUpstream(10 * MIN, { caches: false });
  const r = await runProbe(opts([5 * MIN]), deps);
  assert.equal(r.status, "no-observable-cache");
  assert.equal(calls(), 3, "prime + two re-sends");
});

test("transient errors are retried", async () => {
  const { deps } = fakeUpstream(60 * MIN, { failFirst: 2 });
  const r = await runProbe(opts([5 * MIN], 1), deps);
  assert.equal(r.status, "completed");
});

test("hard errors fail the run with a message", async () => {
  const { deps } = fakeUpstream(60 * MIN);
  deps.send = async () => ({ status: 401, text: "bad key" });
  const r = await runProbe(opts([5 * MIN], 1), deps);
  assert.equal(r.status, "failed");
  assert.match(r.error ?? "", /HTTP 401/);
});

test("with stopOnRefusal a 429 is not retried and ends the run, during priming and at a check", async () => {
  for (const failAt of [4, 8]) {
    const { deps } = fakeUpstream(60 * MIN);
    const send = deps.send;
    let n = 0;
    deps.send = async (u, h, b) => {
      n++;
      if (n === failAt) return { status: 429, text: "usage limit reached" };
      return send(u, h, b);
    };
    const r = await runProbe({ ...opts([5 * MIN, 10 * MIN], 2), stopOnRefusal: true }, deps);
    assert.equal(r.status, "failed");
    assert.match(r.error ?? "", /quota or rate refusal, not retried: HTTP 429/);
    assert.equal(n, failAt, "no request after the refusal");
  }
  // A 400 that names a quota stops too; one that doesn't is an ordinary error.
  const { deps } = fakeUpstream(60 * MIN);
  deps.send = async () => ({ status: 400, text: "Your weekly usage quota has been exhausted" });
  const r = await runProbe({ ...opts([5 * MIN], 1), stopOnRefusal: true }, deps);
  assert.match(r.error ?? "", /not retried/);
});

test("with stopOnRefusal a 402 (no credit, or a key's limit) ends the run too", async () => {
  const { deps } = fakeUpstream(60 * MIN);
  let n = 0;
  deps.send = async () => {
    n++;
    return { status: 402, text: JSON.stringify({ error: { code: 402, message: "Key limit exceeded" } }) };
  };
  const r = await runProbe({ ...opts([5 * MIN], 1), stopOnRefusal: true }, deps);
  assert.match(r.error ?? "", /not retried: HTTP 402/);
  assert.equal(n, 1);
});

test("primePauseMs waits after each priming request", async () => {
  const { deps } = fakeUpstream(60 * MIN);
  const sleeps: number[] = [];
  const sleep = deps.sleep;
  deps.sleep = async (ms) => { sleeps.push(ms); await sleep(ms); };
  const r = await runProbe({ ...opts([5 * MIN], 2), concurrency: 1, primePauseMs: 1234 }, deps);
  assert.equal(r.status, "completed");
  // during priming (before the first wait for a check age); the checks are then spaced by the same 1,234 ms
  const priming = sleeps.slice(0, sleeps.findIndex((ms) => ms > MIN));
  assert.deepEqual(priming.filter((ms) => ms === 1234), [1234, 1234]);
});

test("the run file sums what every answered request used", async () => {
  const { deps } = fakeUpstream(60 * MIN);
  const r = await runProbe(opts([5 * MIN], 2), deps);
  // control prime + one re-send, 2 primes, 2 checks
  assert.equal(r.spent?.requests, 6);
  assert.equal(r.spent?.promptTokens, 6 * 2600);
  assert.equal(r.spent?.cachedTokens, 3 * 2560);
  assert.equal(r.spent?.requestsWithoutOutput, 6, "the fake reports no output count");
});

test("a check that keeps failing is recorded as an error and the run continues", async () => {
  const { deps } = fakeUpstream(60 * MIN);
  const send = deps.send;
  let n = 0;
  deps.send = async (u, h, b) => {
    n++;
    // control (prime + warm re-send) and 2 primes succeed; the first check then fails on every attempt (1 + 7 retries)
    if (n >= 5 && n <= 12) return { status: 503, text: "down" };
    return send(u, h, b);
  };
  const r = await runProbe(opts([5 * MIN, 10 * MIN], 1), deps);
  assert.equal(r.status, "completed");
  assert.equal(r.checks.length, 2);
  assert.ok(r.checks[0].error);
  assert.equal(r.checks[1].warm, true);
  assert.equal(summarize(r).rows.length, 1, "errored checks are excluded from the survival table");
});

test("warm fraction is configurable", async () => {
  const { deps } = fakeUpstream(60 * MIN);
  const send = deps.send;
  // a provider that caches only ~40% of the prompt (e.g. block-aligned implicit caching)
  deps.send = async (u, h, b) => {
    const res = await send(u, h, b);
    return { status: res.status, text: res.text.replace('"cached_tokens":2560', '"cached_tokens":1040') };
  };
  const strict = await runProbe(opts([5 * MIN], 1), deps);
  assert.equal(strict.status, "no-observable-cache");
  const loose = await runProbe({ ...opts([5 * MIN], 1), runSalt: "t2", warmFraction: 0.3 }, deps);
  assert.equal(loose.status, "completed");
});

test("slow priming doesn't push checks past their age (R1, 2026-11-04)", async () => {
  // A 5-minute cache. Priming the 12 samples takes 40 s each (R1 lost minutes to retries), so the 2.5-minute samples,
  // primed first, would be checked at ~8 minutes and look cold.
  const { deps } = fakeUpstream(5 * MIN);
  const send = deps.send;
  let n = 0;
  const lines: string[] = [];
  deps.log = (l) => lines.push(l);
  deps.send = async (url, headers, body) => {
    const r = await send(url, headers, body);
    if (++n > 2 && n <= 14) await deps.sleep(40_000);
    return r;
  };
  const r = await runProbe(opts([2.5 * MIN, 5 * MIN, 7.5 * MIN, 10 * MIN]), deps);
  assert.ok(lines.some((l) => /overdue, priming again/.test(l)), "overdue samples are primed again");
  for (const c of r.checks) assert.ok(c.actualAgeMs - c.targetAgeMs <= lateAfterMs(c.targetAgeMs), `${c.sampleId} on time`);
  const s = summarize(r);
  assert.equal(s.lastAllWarmMs, 2.5 * MIN);
  assert.equal(s.allColdMs, 5 * MIN);
});

test("a check that still runs late is left out of the result", async () => {
  // Every request after the control round takes 4 minutes, re-primes included: after two re-primes the check
  // runs late and doesn't count.
  const { deps } = fakeUpstream(60 * MIN);
  const send = deps.send;
  let n = 0;
  deps.send = async (url, headers, body) => {
    n++;
    const r = await send(url, headers, body);
    if (n > 2) await deps.sleep(4 * MIN);
    return r;
  };
  const r = await runProbe(opts([1 * MIN], 1), deps);
  assert.equal(r.checks.length, 1);
  assert.equal(r.checks[0].late, true);
  assert.equal(summarize(r).rows.length, 0);
  assert.match(renderMarkdown(r), /Left out, ran late: 1m at /);
});

test("the run file records what was sent, never a key", async () => {
  // Two runs that differ only in a caching setting must differ in the file, not only in their label
  // (results/openai-direct-2026-11-15: the 12-hour setting had to be taken from the owner's notes).
  const { deps } = fakeUpstream(60 * MIN);
  const key = "fake-key-for-this-test";
  const sent: string[] = [];
  const send = deps.send;
  deps.send = async (u, h, b) => {
    sent.push(b);
    return send(u, h, b);
  };
  const bodyExtra = { prompt_cache_options: { ttl: "12h" } };
  const r = await runProbe({
    ...opts([5 * MIN], 1),
    bodyExtra,
    filler: "list",
    headers: { authorization: `Bearer ${key}`, "x-api-key": key, "X-Custom-Token": key, "anthropic-beta": "extended-cache-ttl-2025-04-11" },
  }, deps);
  const q = r.request;
  assert.ok(q, "every new run file has a request record");
  assert.deepEqual(q.bodyExtra, bodyExtra);
  assert.equal(q.path, "/responses");
  assert.equal(q.cacheKey, "per-sample");
  assert.equal(q.prefixTokens, 50);
  assert.equal(r.filler, "list");
  // The recorded body is the body sent, with the prefix and the per-sample key as placeholders.
  const real = JSON.parse(sent[0]);
  assert.deepEqual(Object.keys(q.body).sort(), Object.keys(real).sort());
  assert.deepEqual(q.body.prompt_cache_options, { ttl: "12h" });
  assert.equal(q.body.prompt_cache_key, "groundtruth-t-<sample>");
  // Headers: named; a value only where it can't carry a credential.
  assert.equal(q.headers["anthropic-beta"], "extended-cache-ttl-2025-04-11");
  assert.equal(q.headers.authorization, "(not recorded)");
  assert.equal(q.headers["X-Custom-Token"], "(not recorded)");
  const file = JSON.stringify(r) + renderMarkdown(r);
  assert.ok(!file.includes(key), "the key is in neither the run file nor the summary");
  const md = renderMarkdown(r);
  assert.match(md, /body extra `\{"prompt_cache_options":\{"ttl":"12h"\}\}`/);
  assert.match(md, /filler `list`/);
  assert.match(md, /authorization \(value not recorded\)/);

  const plain = await runProbe({ ...opts([5 * MIN], 1), runSalt: "t3" }, deps);
  assert.equal(plain.request?.bodyExtra, null);
  assert.equal(plain.filler, undefined, "the default filler is not named");
  assert.match(renderMarkdown(plain), /body extra none/);
});

test("an old run file without a request record still renders", () => {
  const old = { probeVersion: "0.2.0", label: "old", baseUrl: "http://x/v1", format: "responses" as const, model: "m", runSalt: "s", replicas: 1, cacheKey: true, plannedAges: [], startedAt: "2026-11-15T00:00:00Z", status: "completed" as const, checks: [] };
  assert.doesNotMatch(renderMarkdown(old), /Request/);
});
