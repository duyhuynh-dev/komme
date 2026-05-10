import assert from "node:assert/strict";
import test from "node:test";
import { parseConciergeIntent, type ConciergeThemeOption } from "./pulse-concierge.ts";

const options: ConciergeThemeOption[] = [
  { id: "underground_dance", label: "Underground dance", description: "Warehouse sets and techno." },
  { id: "indie_live_music", label: "Indie live music", description: "Touring bands and intimate rooms." },
  { id: "late_night_food", label: "Late-night food scene", description: "Late bites and pop-ups." },
  { id: "dive_bar_scene", label: "Dive bars / local scene", description: "Low-key neighborhood bars." },
  { id: "gallery_nights", label: "Gallery nights", description: "Art openings and gallery crawls." },
];

test("parseConciergeIntent maps natural language into theme ids", () => {
  const result = parseConciergeIntent("cheap late techno night in Brooklyn", options);

  assert.deepEqual(new Set(result.selectedThemeIds), new Set(["underground_dance", "dive_bar_scene", "late_night_food"]));
  assert.equal(result.confidence, "clear");
  assert.match(result.summary, /Underground dance/);
});

test("parseConciergeIntent combines quick picks with typed intent", () => {
  const result = parseConciergeIntent("something arty", options, ["indie_live_music"]);

  assert.deepEqual(result.selectedThemeIds, ["indie_live_music", "gallery_nights"]);
  assert.deepEqual(result.matchedLabels, ["Indie live music", "Gallery nights"]);
});

test("parseConciergeIntent returns a useful fallback when no signal is present", () => {
  const result = parseConciergeIntent("", options);

  assert.deepEqual(result.selectedThemeIds, []);
  assert.equal(result.confidence, "fallback");
});
