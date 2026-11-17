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
