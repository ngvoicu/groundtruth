// --usage-log: one line per reply with the usage the provider reported, for a cost ledger. Never a header (the key is
// in the headers), never the prompt or the answer: only the model, the status, the usage object as returned, the stop
// reason, and for a refused request the error's type and code and its message with anything key-shaped masked.

/** Masks anything shaped like a key in an error message (OpenAI names part of a wrong key in its 401). */
export function maskKeys(text: string): string {
  return text.replace(/\b(sk|rk|pk)-[\w*.-]{4,}/g, "$1-(masked)").replace(/\b[A-Za-z0-9_-]{32,}\b/g, "(masked)");
}

function obj(value: unknown): Record<string, unknown> | undefined {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : undefined;
}

/** The ledger line for one request: `body` as sent (JSON text), `status` and `text` as answered. */
export function usageLogLine(label: string, body: string, status: number, text: string, at: Date): Record<string, unknown> {
  let model: unknown;
  try {
    model = obj(JSON.parse(body))?.model;
  } catch {
    model = undefined;
  }
  const line: Record<string, unknown> = { at: at.toISOString(), label, model, status };
  let reply: Record<string, unknown> | undefined;
  try {
    reply = obj(JSON.parse(text));
  } catch {
    reply = undefined;
  }
  if (!reply) {
    if (status < 200 || status >= 300) line.error = { message: maskKeys(text.slice(0, 300)) };
    else line.note = "reply is not JSON";
    return line;
  }
  const usage = obj(reply.usage) ?? obj(obj(reply.response)?.usage);
  if (usage) line.usage = usage;
  if (reply.model !== undefined) line.reply_model = reply.model;
  for (const key of ["stop_reason", "status"]) if (typeof reply[key] === "string") line[`reply_${key}`] = reply[key];
  const incomplete = obj(reply.incomplete_details);
  if (incomplete) line.reply_incomplete = incomplete;
  const stopDetails = obj(reply.stop_details);
  if (stopDetails) line.reply_stop_details = stopDetails;
  const error = obj(reply.error);
  if (error) {
    line.error = {
      type: error.type,
      code: error.code,
      message: typeof error.message === "string" ? maskKeys(error.message.slice(0, 300)) : undefined,
    };
  }
  return line;
}
