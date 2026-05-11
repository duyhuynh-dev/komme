import type { ConnectedSourceHealth, RecommendationPersonalizationSource } from "@/lib/types";

export type ConnectedSourceSetupAction = "connect" | "sync" | null;

export interface ConnectedSourceSetupState {
  statusLabel: string;
  syncLabel: string;
  influenceLabel: string;
  detail: string;
  tone: "neutral" | "healthy" | "warning";
  action: ConnectedSourceSetupAction;
}

export function connectedSourceStatusLabel(health?: ConnectedSourceHealth | null) {
  return connectedSourceSetupState(health).statusLabel;
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

export function connectedSourceSetupState(health?: ConnectedSourceHealth | null): ConnectedSourceSetupState {
  if (!health?.connected) {
    return {
      statusLabel: "Spotify disconnected",
      syncLabel: "Disconnected",
      influenceLabel: "Not shaping recommendations",
      detail: health?.healthReason ?? "Connect Spotify when you want listening history to help shape your map.",
      tone: "neutral",
      action: "connect",
    };
  }

  const syncLabel = connectedSourceSyncLabel(health);
  const influenceLabel = connectedSourceInfluenceLabel(health);

  if (health.stale) {
    return {
      statusLabel: "Stale taste suppressed",
      syncLabel,
      influenceLabel,
      detail:
        health.healthReason ??
        "Komme suppressed stale Spotify taste so old listening data does not quietly shape recommendations. Retry sync to refresh it.",
      tone: "warning",
      action: "sync",
    };
  }

  if (health.latestRunStatus && health.latestRunStatus !== "completed") {
    return {
      statusLabel: "Last sync failed",
      syncLabel,
      influenceLabel,
      detail: health.healthReason ?? "The latest Spotify sync failed. Retry sync when you are ready.",
      tone: "warning",
      action: "sync",
    };
  }

  if (!health.latestRunStatus) {
    return {
      statusLabel: "Connected, not synced",
      syncLabel,
      influenceLabel,
      detail:
        health.healthReason ??
        "Spotify is connected, but Komme has not synced listening taste into recommendations yet.",
      tone: "neutral",
      action: "sync",
    };
  }

  if (health.currentlyInfluencingRanking) {
    return {
      statusLabel: "Influencing recommendations",
      syncLabel,
      influenceLabel,
      detail: health.healthReason ?? "Spotify taste is currently shaping recommendations.",
      tone: "healthy",
      action: null,
    };
  }

  return {
    statusLabel: "Not influencing yet",
    syncLabel,
    influenceLabel,
    detail:
      health.healthReason ??
      "Spotify is connected, but no active Spotify themes are currently shaping recommendations.",
    tone: "neutral",
    action: "sync",
  };
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
