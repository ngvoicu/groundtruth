import assert from "node:assert/strict";
import { test } from "node:test";
import { maskKeys, usageLogLine } from "../src/usagelog.ts";

const at = new Date("2026-11-17T15:00:00Z");
const body = JSON.stringify({ model: "m", input: [{ role: "developer", content: "the prefix" }] });

test("usage log: the usage as reported, no prompt and no answer", () => {
  const usage = { input_tokens: 4460, cache_creation_input_tokens: 4450, cache_read_input_tokens: 0, output_tokens: 3 };
  const line = usageLogLine("L", body, 200, JSON.stringify({ model: "m-2026", stop_reason: "end_turn", content: [{ text: "OK" }], usage }), at);
  assert.deepEqual(line, { at: at.toISOString(), label: "L", model: "m", status: 200, usage, reply_model: "m-2026", reply_stop_reason: "end_turn" });
  assert.ok(!JSON.stringify(line).includes("prefix"));
});

test("usage log: an error keeps its type and code, a key in its message is masked", () => {
  const text = JSON.stringify({ error: { type: "invalid_request_error", code: "invalid_api_key", message: "Incorrect API key provided: sk-proj-abc********wxyz." } });
  const line = usageLogLine("L", body, 401, text, at);
  assert.deepEqual(line.error, { type: "invalid_request_error", code: "invalid_api_key", message: "Incorrect API key provided: sk-(masked)" });
  assert.equal(maskKeys("x sk-ant-a1_b2-c3 y"), "x sk-(masked) y");
});

test("usage log: the upstream an aggregator names, the reply id and the sample's cache key", () => {
  const sent = JSON.stringify({ model: "m", input: "the prefix", prompt_cache_key: "groundtruth-abc-2.5m-r1" });
  const usage = { input_tokens: 2500, input_tokens_details: { cached_tokens: 2400 }, output_tokens: 2, cost: 0.0001 };
  const line = usageLogLine("L", sent, 200, JSON.stringify({ id: "gen-1", model: "m", provider: "Upstream", usage }), at);
  assert.deepEqual(line, { at: at.toISOString(), label: "L", model: "m", sample: "groundtruth-abc-2.5m-r1", status: 200, usage, reply_model: "m", reply_provider: "Upstream", reply_id: "gen-1" });
  const bySession = usageLogLine("L", JSON.stringify({ model: "m", session_id: "groundtruth-abc-control" }), 200, "{}", at);
  assert.equal(bySession.sample, "groundtruth-abc-control");
});
