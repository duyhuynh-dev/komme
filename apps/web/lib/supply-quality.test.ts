import assert from "node:assert/strict";
import { test } from "node:test";

import {
  supplyQualityConfidenceDelta,
  supplyQualityIssueCount,
  supplyQualityTone,
} from "./supply-quality.ts";
import type { RecommendationSupplyQualityRollup } from "./types.ts";

const baseRollup: RecommendationSupplyQualityRollup = {
  sourceName: "Small Feed",
  sourceKind: "aggregator",
  recommendationCount: 3,
  eventCount: 3,
  staleVerificationCount: 0,
  weakSourceConfidenceCount: 0,
  missingTicketUrlCount: 0,
  missingSourceUrlCount: 0,
  averageRawSourceConfidence: 0.84,
  averageEffectiveSourceConfidence: 0.84,
  topTrustReasons: ["Recently verified"],
};

test("supply quality helper counts visible issue totals", () => {
  assert.equal(
    supplyQualityIssueCount({
      ...baseRollup,
      staleVerificationCount: 1,
      weakSourceConfidenceCount: 1,
      missingTicketUrlCount: 2,
    }),
    4,
  );
});

test("supply quality helper maps issue density to ops tone", () => {
  assert.match(supplyQualityTone(baseRollup), /emerald/);
  assert.match(supplyQualityTone({ ...baseRollup, staleVerificationCount: 1 }), /white/);
  assert.match(
    supplyQualityTone({
      ...baseRollup,
      staleVerificationCount: 1,
      weakSourceConfidenceCount: 1,
      missingTicketUrlCount: 1,
    }),
    /amber/,
  );
});

test("supply quality helper exposes confidence delta", () => {
  assert.equal(
    supplyQualityConfidenceDelta({
      ...baseRollup,
      averageRawSourceConfidence: 0.84,
      averageEffectiveSourceConfidence: 0.71,
    }),
    -0.13,
  );
});
