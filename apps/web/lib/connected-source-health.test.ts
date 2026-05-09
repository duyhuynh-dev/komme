import assert from "node:assert/strict";
import { test } from "node:test";

import {
  connectedSourceInfluenceLabel,
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
