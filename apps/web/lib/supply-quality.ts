import type { RecommendationSupplyQualityRollup } from "./types";

export function supplyQualityIssueCount(rollup: RecommendationSupplyQualityRollup) {
  return (
    rollup.staleVerificationCount +
    rollup.weakSourceConfidenceCount +
    rollup.missingTicketUrlCount +
    rollup.missingSourceUrlCount
  );
}

export function supplyQualityTone(rollup: RecommendationSupplyQualityRollup) {
  const issueCount = supplyQualityIssueCount(rollup);
  if (issueCount >= Math.max(2, rollup.recommendationCount)) {
    return "border-amber-200 bg-amber-50";
  }
  if (issueCount > 0) {
    return "border-slate-200 bg-white";
  }
  return "border-emerald-200 bg-emerald-50";
}

export function supplyQualityConfidenceDelta(rollup: RecommendationSupplyQualityRollup) {
  return rollup.averageEffectiveSourceConfidence - rollup.averageRawSourceConfidence;
}
