import assert from "node:assert/strict";
import { test } from "node:test";

import {
  buildTonightPlannerPanelState,
  plannerFallbackActionLabel,
  plannerOutcomePrompt,
  plannerRerouteButtonLabel,
  plannerStopActionLabel,
  plannerSupportLabel,
} from "./tonight-planner.ts";
import type { TonightPlannerResponse } from "./types";

test("buildTonightPlannerPanelState returns a populated planner view model", () => {
  const planner: TonightPlannerResponse = {
    status: "ready",
    title: "Tonight planner",
    summary: "Open in Bushwick, anchor the night at Elsewhere, and keep Good Room ready if timing shifts.",
    planningNote: "Built from the live shortlist.",
    executionStatus: "locked",
    executionNote: "Elsewhere is currently locked into tonight's plan.",
    activeTargetEventId: "main-event",
    activeTargetVenueName: "Elsewhere",
    outcomeStatus: "pending",
    outcomeNote: null,
    rerouteStatus: "idle",
    rerouteNote: null,
    rerouteOption: null,
    stops: [
      {
        role: "pregame",
        roleLabel: "Pregame",
        venueId: "pregame-venue",
        venueName: "Night Cafe",
        eventId: "pregame-event",
        eventTitle: "Cocktails and warm-up set",
        neighborhood: "Lower East Side",
        startsAt: "2026-04-25T23:15:00+00:00",
        priceLabel: "$18",
        scoreBand: "high",
        hopLabel: "12 min transit",
        roleReason: "Starts before the main event.",
        confidence: "high",
        confidenceLabel: "Strong fit",
        confidenceReason: "Timing and travel line up cleanly.",
        selected: false,
        fallbacks: [],
      },
      {
        role: "main_event",
        roleLabel: "Main event",
        venueId: "main-venue",
        venueName: "Elsewhere",
        eventId: "main-event",
        eventTitle: "Headliner set",
        neighborhood: "Bushwick",
        startsAt: "2026-04-26T01:00:00+00:00",
        priceLabel: "$35",
        scoreBand: "high",
        hopLabel: "18 min transit",
        roleReason: "Strongest anchor from the shortlist.",
        confidence: "high",
        confidenceLabel: "Confident anchor",
        confidenceReason: "Best mix of timing and trust.",
        selected: true,
        fallbacks: [
          {
            venueId: "backup-venue",
            venueName: "Good Room",
            eventId: "backup-event",
            eventTitle: "Alternate room set",
            neighborhood: "Greenpoint",
            startsAt: "2026-04-26T01:20:00+00:00",
            priceLabel: "$28",
            scoreBand: "high",
            hopLabel: "15 min transit",
            fallbackReason: "Use this if Elsewhere feels thin.",
            selected: false,
          },
        ],
      },
    ],
  };

  const state = buildTonightPlannerPanelState(planner);

  assert.equal(state.mode, "plan");
  assert.equal(state.headline, "2 stops ready");
  assert.equal(state.fallbackCount, 1);
  assert.equal(state.executionStatus, "locked");
  assert.equal(state.executionNote, "Elsewhere is currently locked into tonight's plan.");
  assert.equal(state.activeTargetEventId, "main-event");
  assert.equal(state.activeTargetVenueName, "Elsewhere");
  assert.equal(state.outcomeStatus, "pending");
  assert.equal(state.outcomeNote, null);
  assert.equal(state.rerouteStatus, "idle");
  assert.equal(state.rerouteOption, null);
  assert.equal(state.stops[1].venueName, "Elsewhere");
});

test("buildTonightPlannerPanelState carries planner session recomposition state", () => {
  const stop: TonightPlannerResponse["stops"][number] = {
    role: "main_event",
    roleLabel: "Main event",
    venueId: "main-venue",
    venueName: "Elsewhere",
    eventId: "main-event",
    eventTitle: "Headliner set",
    neighborhood: "Bushwick",
    startsAt: "2026-04-26T01:00:00+00:00",
    priceLabel: "$35",
    scoreBand: "high",
    hopLabel: "18 min transit",
    roleReason: "Strongest anchor from the shortlist.",
    confidence: "high",
    confidenceLabel: "Confident anchor",
    confidenceReason: "Best mix of timing and trust.",
    selected: true,
    fallbacks: [],
  };
  const planner: TonightPlannerResponse = {
    status: "ready",
    title: "Tonight planner",
    summary: "Route recomposed.",
    planningNote: null,
    executionStatus: "locked",
    executionNote: null,
    activeTargetEventId: "main-event",
    activeTargetVenueName: "Elsewhere",
    outcomeStatus: "pending",
    outcomeNote: null,
    rerouteStatus: "idle",
    rerouteNote: null,
    rerouteOption: null,
    sessionId: "session-1",
    sessionStatus: "active",
    activeStop: stop,
    remainingStops: [stop],
    droppedStops: [],
    recompositionReason: "Pulse recomposed the remaining route around live timing.",
    lastEventAt: "2026-04-26T00:30:00+00:00",
    stops: [stop],
  };

  const state = buildTonightPlannerPanelState(planner);

  assert.equal(state.sessionId, "session-1");
  assert.equal(state.activeStop?.eventId, "main-event");
  assert.equal(state.remainingStops.length, 1);
  assert.equal(state.recompositionReason, "Pulse recomposed the remaining route around live timing.");
});

test("buildTonightPlannerPanelState returns the empty planner copy when no viable plan exists", () => {
  const planner: TonightPlannerResponse = {
    status: "empty",
    title: "Tonight planner",
    summary: "Pulse needs more tonight options before it can sketch a route.",
    planningNote: "Refresh after new events land.",
    executionStatus: "idle",
    executionNote: null,
    activeTargetEventId: null,
    activeTargetVenueName: null,
    outcomeStatus: "idle",
    outcomeNote: null,
    rerouteStatus: "idle",
    rerouteNote: null,
    rerouteOption: null,
    stops: [],
  };

  const state = buildTonightPlannerPanelState(planner);

  assert.equal(state.mode, "empty");
  assert.equal(state.headline, "Build a night from the shortlist");
  assert.equal(state.summary, "Pulse needs more tonight options before it can sketch a route.");
});

test("plannerSupportLabel surfaces swap counts before the confidence note", () => {
  const stop: TonightPlannerResponse["stops"][number] = {
    role: "late_option",
    roleLabel: "Late option",
    venueId: "late-venue",
    venueName: "Very Late Warehouse",
    eventId: "late-event",
    eventTitle: "Stretch set",
    neighborhood: "Bushwick",
    startsAt: "2026-04-26T03:55:00+00:00",
    priceLabel: "$42",
    scoreBand: "medium",
    hopLabel: "10 min transit",
    roleReason: "Runs late.",
    confidence: "watch",
    confidenceLabel: "Keep a backup ready",
    confidenceReason: "Timing pushes late into the night.",
    selected: false,
    fallbacks: [
      {
        venueId: "alt-venue",
        venueName: "Good Room",
        eventId: "alt-event",
        eventTitle: "Alternate late set",
        neighborhood: "Greenpoint",
        startsAt: "2026-04-26T03:20:00+00:00",
        priceLabel: "$28",
        scoreBand: "high",
        hopLabel: "16 min transit",
        fallbackReason: "Use this if the main late option slides too late.",
        selected: true,
      },
      {
        venueId: "alt-venue-2",
        venueName: "Public Records",
        eventId: "alt-event-2",
        eventTitle: "Backup room set",
        neighborhood: "Gowanus",
        startsAt: "2026-04-26T03:30:00+00:00",
        priceLabel: "$30",
        scoreBand: "high",
        hopLabel: "18 min transit",
        fallbackReason: "Use this if you want a steadier close.",
        selected: false,
      },
    ],
  };

  assert.equal(
    plannerSupportLabel(stop),
    "2 swaps ready · Timing pushes late into the night.",
  );
});

test("planner action labels reflect active planner execution state", () => {
  assert.equal(plannerStopActionLabel({ selected: true } as never), "Locked tonight");
  assert.equal(plannerStopActionLabel({ selected: false } as never), "Lock this stop");
  assert.equal(plannerFallbackActionLabel(true), "Swap active");
  assert.equal(plannerFallbackActionLabel(false), "Use this swap");
});

test("plannerOutcomePrompt guides pending and completed planner outcomes", () => {
  assert.equal(
    plannerOutcomePrompt("Elsewhere", "pending", null),
    "Let Pulse know whether Elsewhere actually made tonight's plan.",
  );
  assert.equal(
    plannerOutcomePrompt("Elsewhere", "attended", "Elsewhere is confirmed as part of tonight's plan."),
    "Elsewhere is confirmed as part of tonight's plan.",
  );
  assert.equal(plannerOutcomePrompt(null, "idle", null), null);
});

test("plannerRerouteButtonLabel reflects the reroute source", () => {
  assert.equal(plannerRerouteButtonLabel(null), "Switch now");
  assert.equal(plannerRerouteButtonLabel({ sourceKind: "fallback" } as never), "Use this pivot");
  assert.equal(plannerRerouteButtonLabel({ sourceKind: "next_stop" } as never), "Jump ahead");
});
