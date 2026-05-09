import type { RecommendationOutcomeAttribution } from "@/lib/types";

export function outcomeAttributionSourceLabel(source: RecommendationOutcomeAttribution["source"]) {
  const labels: Record<string, string> = {
    feedback: "Feedback",
    planner: "Planner",
    digest: "Digest",
  };
  return labels[source] ?? source.replace("_", " ");
}

export function outcomeAttributionTone(attribution: RecommendationOutcomeAttribution) {
  if (attribution.direction === "positive") {
    return "border-emerald-200 bg-emerald-50 text-emerald-800";
  }
  if (attribution.direction === "negative") {
    return "border-amber-200 bg-amber-50 text-amber-800";
  }
  return "border-stroke/80 bg-white text-slate-700";
}
