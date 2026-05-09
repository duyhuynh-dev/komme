import assert from "node:assert/strict";
import { test } from "node:test";

import { outcomeAttributionSourceLabel, outcomeAttributionTone } from "./outcome-attribution.ts";

test("outcome attribution helper labels ops sources", () => {
  assert.equal(outcomeAttributionSourceLabel("feedback"), "Feedback");
  assert.equal(outcomeAttributionSourceLabel("planner"), "Planner");
  assert.equal(outcomeAttributionSourceLabel("digest"), "Digest");
});

test("outcome attribution helper maps influence direction to tone", () => {
  assert.match(outcomeAttributionTone({ direction: "positive" } as never), /emerald/);
  assert.match(outcomeAttributionTone({ direction: "negative" } as never), /amber/);
  assert.match(outcomeAttributionTone({ direction: "neutral" } as never), /slate/);
});
