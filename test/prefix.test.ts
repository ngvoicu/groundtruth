import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { test } from "node:test";
import { CHARS_PER_TOKEN, makePrefix } from "../src/prefix.ts";

test("prefix is deterministic per salt and sample", () => {
  assert.equal(makePrefix("s1", "a"), makePrefix("s1", "a"));
});

test("different samples and different salts never share a start", () => {
  const a = makePrefix("s1", "5m-r1");
  const b = makePrefix("s1", "5m-r2");
  const c = makePrefix("s2", "5m-r1");
  assert.notEqual(a.slice(0, 60), b.slice(0, 60));
  assert.notEqual(a.slice(0, 60), c.slice(0, 60));
  assert.ok(a.startsWith("Cache probe run s1, sample 5m-r1."));
});

test("prefix reaches the requested size", () => {
  const p = makePrefix("s", "x", 2500);
  assert.ok(p.length >= 2500 * CHARS_PER_TOKEN);
  assert.ok(p.length < 2500 * CHARS_PER_TOKEN + 200);
});

test("the default filler is unchanged: earlier runs stay comparable", () => {
  const sha = (text: string) => createHash("sha256").update(text).digest("hex");
  assert.equal(sha(makePrefix("s1", "a", 2500)), "6bf224705bb4ee9ff4ef3da26426e8e9c681af56ee49786ddceb1e8a7ad09b89");
  assert.equal(sha(makePrefix("x", "control", 40)), "2be93daec36a5d495f0bc9c426eced80423c5e350e61684ce9d3959f1a214e2a");
  assert.equal(makePrefix("s1", "a", 2500, "words"), makePrefix("s1", "a", 2500));
});

test("the list filler is deterministic, unique per sample, plain sentences, and reaches the size", () => {
  const p = makePrefix("s1", "5m-r1", 2500, "list");
  assert.equal(p, makePrefix("s1", "5m-r1", 2500, "list"));
  assert.notEqual(p, makePrefix("s1", "5m-r1", 2500));
  assert.ok(p.startsWith("Cache probe run s1, sample 5m-r1."));
  assert.notEqual(p.slice(0, 60), makePrefix("s1", "5m-r2", 2500, "list").slice(0, 60));
  assert.match(p, /\n1\. The [a-z ]+ on [A-Za-z ]+ opens at \d+ and closes at \d+ on weekdays\.\n/);
  assert.ok(p.length >= 2500 * CHARS_PER_TOKEN);
  assert.ok(p.length < 2500 * CHARS_PER_TOKEN + 200);
});
