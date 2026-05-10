import assert from "node:assert/strict";
import { test } from "node:test";

import {
  outcomeAttributionActionLabel,
  outcomeAttributionSourceLabel,
  outcomeAttributionTone,
} from "./outcome-attribution.ts";

test("outcome attribution helper labels supported actions", () => {
  assert.equal(outcomeAttributionActionLabel("save"), "Save");
  assert.equal(outcomeAttributionActionLabel("dismiss"), "Dismiss");
  assert.equal(outcomeAttributionActionLabel("digest_click"), "Digest click");
  assert.equal(outcomeAttributionActionLabel("ticket_click"), "Ticket click");
  assert.equal(outcomeAttributionActionLabel("archive_revisit"), "Archive revisit");
  assert.equal(outcomeAttributionActionLabel("planner_attended"), "Planner attended");
  assert.equal(outcomeAttributionActionLabel("planner_skipped"), "Planner skipped");
});

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
