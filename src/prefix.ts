// Prompt prefixes for cache probing.
//
// Every sample needs its own prefix: a cache entry's timer resets on each hit, so a prefix is primed once and
// checked once. The run salt goes first, so prefixes from earlier runs (or a smoke test a few minutes ago)
// can never match. Text is deterministic per (salt, sample) so a run can be reproduced.

const WORDS = (
  "amber anchor arch atlas badge basil beacon birch bison bloom brook cabin canal cedar chalk chord cider " +
  "cinder clover cobalt comet coral crane crest dawn delta dune ember fable fern fjord flint forge frost " +
  "garnet glade granite grove harbor hazel heron horizon indigo iris ivory jade juniper kelp kestrel lagoon " +
  "lantern larch ledger lilac linen lotus lumen maple marble meadow mesa mint moss nectar nimbus oak ochre " +
  "olive onyx opal orchid otter pebble pepper pine plume prairie quartz quill raven reed ridge river saffron " +
  "sage sable shale sienna slate sorrel spruce summit tamarind thistle tide timber topaz tundra umber velvet " +
  "vesper violet willow yarrow zephyr zinc"
).split(" ");

/**
 * The filler after the header. `words` (the default, used by every run before 16 November 2026): sentences of random
 * words from WORDS. `list`: plain numbered sentences about shop opening hours, for a model that refuses the random
 * words (Anthropic refused them on Claude Haiku 5.5 through a Claude login, category "bio"). The filler does not
 * change how a prompt is cached; it only has to be text the model answers.
 */
export const FILLERS = ["words", "list"] as const;
export type Filler = (typeof FILLERS)[number];

const STREETS = ["Main Street", "Mill Lane", "Oak Avenue", "Station Road", "Park Row", "Bridge Street", "Church Lane", "High Street"];
const SHOPS = ["bakery", "bookshop", "pharmacy", "post office", "hardware store", "florist", "library", "grocery"];

/** Roughly 4 characters per token for English-like text. */
export const CHARS_PER_TOKEN = 4;

function hash32(text: string): number {
  // FNV-1a
  let h = 0x811c9dc5;
  for (let i = 0; i < text.length; i++) {
    h ^= text.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return h >>> 0;
}

function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** A random-looking run salt; pass it explicitly to reproduce a run. */
export function newRunSalt(): string {
  return Math.random().toString(36).slice(2, 10);
}

/**
 * Builds the cacheable prefix for one sample: a header naming the run and sample, then filler sentences
 * until about `targetTokens` tokens.
 */
export function makePrefix(runSalt: string, sampleId: string, targetTokens = 2500, filler: Filler = "words"): string {
  const rand = mulberry32(hash32(`${runSalt}/${sampleId}`));
  const targetChars = Math.max(1, targetTokens) * CHARS_PER_TOKEN;
  const parts: string[] = [
    `Cache probe run ${runSalt}, sample ${sampleId}. The text below is filler used to measure prompt-cache lifetime; ` +
      "it has no meaning. Answer the final question briefly.\n\n",
  ];
  let length = parts[0].length;
  let sentence = 0;
  while (length < targetChars) {
    let line: string;
    if (filler === "list") {
      const pick = <T>(list: readonly T[]): T => list[Math.floor(rand() * list.length)];
      line = `${sentence + 1}. The ${pick(SHOPS)} on ${pick(STREETS)} opens at ${7 + Math.floor(rand() * 4)} and closes at ${5 + Math.floor(rand() * 4)} on weekdays.\n`;
    } else {
      const count = 8 + Math.floor(rand() * 10);
      const words: string[] = [];
      for (let i = 0; i < count; i++) words.push(WORDS[Math.floor(rand() * WORDS.length)]);
      line = `${sentence + 1}. ${words.join(" ")}.\n`;
    }
    parts.push(line);
    length += line.length;
    sentence++;
  }
  return parts.join("");
}
