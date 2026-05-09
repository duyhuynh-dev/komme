import assert from "node:assert/strict";
import { test } from "node:test";

import { movementExplanationSourceLabel, movementExplanationTone } from "./recommendation-movement.ts";

test("movement explanation helper labels trusted movement sources", () => {
  assert.equal(movementExplanationSourceLabel("feedback"), "Feedback");
  assert.equal(movementExplanationSourceLabel("planner"), "Planner");
  assert.equal(movementExplanationSourceLabel("source_health"), "Source health");
});

test("movement explanation helper maps direction to compact ops tone", () => {
  assert.match(
    movementExplanationTone({
      title: "Recent feedback",
      detail: "Saved before.",
      direction: "positive",
      source: "feedback",
    }),
    /emerald/,
  );
  assert.match(
    movementExplanationTone({
      title: "Provider freshness",
      detail: "Spotify stale.",
      direction: "negative",
      source: "source_health",
    }),
    /amber/,
  );
});
