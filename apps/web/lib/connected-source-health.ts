import type { ConnectedSourceHealth, RecommendationPersonalizationSource } from "@/lib/types";

export function connectedSourceStatusLabel(health?: ConnectedSourceHealth | null) {
  if (!health?.connected) {
    return "Not connected";
  }
  if (health.stale || health.confidenceState === "degraded") {
    return "Needs refresh";
  }
  if (health.currentlyInfluencingRanking) {
    return "Influencing ranking";
  }
  if (health.latestRunStatus === "failed") {
    return "Sync failed";
  }
  return "Connected";
}

export function connectedSourceSyncLabel(health?: ConnectedSourceHealth | null) {
  if (!health?.connected) {
    return "Disconnected";
  }
  if (!health.latestRunStatus) {
    return "No sync yet";
  }
  return health.latestRunStatus === "completed" ? "Last sync succeeded" : "Last sync failed";
}

export function connectedSourceInfluenceLabel(health?: ConnectedSourceHealth | null) {
  if (!health?.connected) {
    return "Not influencing recommendations";
  }
  return health.currentlyInfluencingRanking ? "Currently shaping recommendations" : "Not shaping recommendations";
}

export function personalizationSourceLabel(source: RecommendationPersonalizationSource) {
  if (source.influence === "suppressed") {
    return `${source.label} paused`;
  }
  if (source.sourceProvider === "spotify") {
    return `Spotify taste ${source.influence}`;
  }
  if (source.sourceProvider === "manual") {
    return `Manual taste ${source.influence}`;
  }
  if (source.sourceProvider === "feedback") {
    return `Feedback learning ${source.influence}`;
  }
  return `${source.label} ${source.influence}`;
}
