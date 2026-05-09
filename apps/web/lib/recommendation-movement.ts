import type { RecommendationMovementExplanation } from "@/lib/types";

export function movementExplanationTone(explanation: RecommendationMovementExplanation) {
  if (explanation.direction === "positive") {
    return "border-emerald-200 bg-emerald-50 text-emerald-800";
  }
  if (explanation.direction === "negative") {
    return "border-amber-200 bg-amber-50 text-amber-800";
  }
  return "border-stroke/80 bg-canvas text-slate-700";
}

export function movementExplanationSourceLabel(source: RecommendationMovementExplanation["source"]) {
  const labels: Record<string, string> = {
    feedback: "Feedback",
    planner: "Planner",
    source_health: "Source health",
    profile: "Profile",
    score: "Score",
  };
  return labels[source] ?? source.replace("_", " ");
}
