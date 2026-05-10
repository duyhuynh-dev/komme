import assert from "node:assert/strict";
import { test } from "node:test";

import {
  connectedSourceInfluenceLabel,
  connectedSourceSetupState,
  connectedSourceStatusLabel,
  connectedSourceSyncLabel,
  personalizationSourceLabel,
} from "./connected-source-health.ts";
import type { ConnectedSourceHealth, RecommendationPersonalizationSource } from "./types.ts";

const healthySpotify: ConnectedSourceHealth = {
  provider: "spotify",
  connected: true,
  latestRunStatus: "completed",
  latestRunAt: "2026-04-27T13:00:00+00:00",
  stale: false,
  currentlyInfluencingRanking: true,
  confidenceState: "healthy",
  healthReason: "Spotify taste is currently influencing ranking through 2 active themes.",
  debugReason: "spotify: connected=True",
};

test("connected source status helper distinguishes healthy Spotify influence", () => {
  assert.equal(connectedSourceStatusLabel(healthySpotify), "Influencing ranking");
  assert.equal(connectedSourceSyncLabel(healthySpotify), "Last sync succeeded");
  assert.equal(connectedSourceInfluenceLabel(healthySpotify), "Currently shaping recommendations");
});

test("connected source status helper marks stale Spotify as refreshable", () => {
  const staleSpotify: ConnectedSourceHealth = {
    ...healthySpotify,
    latestRunStatus: "failed",
    stale: true,
    currentlyInfluencingRanking: false,
    confidenceState: "degraded",
  };

  assert.equal(connectedSourceStatusLabel(staleSpotify), "Needs refresh");
  assert.equal(connectedSourceSyncLabel(staleSpotify), "Last sync failed");
  assert.equal(connectedSourceInfluenceLabel(staleSpotify), "Not shaping recommendations");
});

test("connected source setup state guides disconnected Spotify connection", () => {
  const state = connectedSourceSetupState({
    provider: "spotify",
    connected: false,
    stale: false,
    currentlyInfluencingRanking: false,
    confidenceState: "disconnected",
    healthReason: "Spotify is not connected.",
  });

  assert.equal(state.statusLabel, "Spotify disconnected");
  assert.equal(state.syncLabel, "Disconnected");
  assert.equal(state.influenceLabel, "Not shaping recommendations");
  assert.equal(state.action, "connect");
  assert.equal(state.tone, "neutral");
});

test("connected source setup state distinguishes unsynced Spotify", () => {
  const state = connectedSourceSetupState({
    ...healthySpotify,
    latestRunStatus: null,
    latestRunAt: null,
    currentlyInfluencingRanking: false,
    confidenceState: "inactive",
    healthReason: "Spotify is connected, but its taste has not been applied to ranking yet.",
  });

  assert.equal(state.statusLabel, "Connected, not synced");
  assert.equal(state.syncLabel, "No sync yet");
  assert.equal(state.influenceLabel, "Not shaping recommendations");
  assert.equal(state.action, "sync");
});

test("connected source setup state distinguishes failed Spotify retry", () => {
  const failedState = connectedSourceSetupState({
    ...healthySpotify,
    latestRunStatus: "failed",
    stale: false,
    currentlyInfluencingRanking: false,
    confidenceState: "degraded",
    healthReason: "Latest Spotify sync failed.",
  });

  assert.equal(failedState.statusLabel, "Last sync failed");
  assert.equal(failedState.syncLabel, "Last sync failed");
  assert.equal(failedState.influenceLabel, "Not shaping recommendations");
  assert.equal(failedState.action, "sync");
  assert.equal(failedState.tone, "warning");
});

test("connected source setup state marks stale Spotify as suppressed", () => {
  const staleState = connectedSourceSetupState({
    ...healthySpotify,
    latestRunStatus: "failed",
    stale: true,
    currentlyInfluencingRanking: false,
    confidenceState: "degraded",
    healthReason: "Latest Spotify sync failed.",
  });

  assert.equal(staleState.statusLabel, "Stale taste suppressed");
  assert.equal(staleState.syncLabel, "Last sync failed");
  assert.equal(staleState.influenceLabel, "Not shaping recommendations");
  assert.equal(staleState.action, "sync");
  assert.equal(staleState.tone, "warning");
});

test("connected source setup state marks influencing Spotify as healthy", () => {
  const state = connectedSourceSetupState(healthySpotify);

  assert.equal(state.statusLabel, "Influencing recommendations");
  assert.equal(state.syncLabel, "Last sync succeeded");
  assert.equal(state.influenceLabel, "Currently shaping recommendations");
  assert.equal(state.action, null);
  assert.equal(state.tone, "healthy");
});

test("personalization source copy names provider-backed and learning signals", () => {
  const spotifySource: RecommendationPersonalizationSource = {
    sourceProvider: "spotify",
    label: "Spotify",
    influence: "supporting",
    topicLabels: ["Underground dance"],
    detail: "Spotify-derived taste matched Underground dance.",
  };
  const staleSource: RecommendationPersonalizationSource = {
    ...spotifySource,
    influence: "suppressed",
  };
  const feedbackSource: RecommendationPersonalizationSource = {
    sourceProvider: "feedback",
    label: "Recent feedback",
    influence: "reducing",
    topicLabels: [],
  };

  assert.equal(personalizationSourceLabel(spotifySource), "Spotify taste supporting");
  assert.equal(personalizationSourceLabel(staleSource), "Spotify paused");
  assert.equal(personalizationSourceLabel(feedbackSource), "Feedback learning reducing");
});
