import type { TonightPlannerRerouteOption, TonightPlannerResponse, TonightPlannerStop } from "./types";

export interface TonightPlannerPanelState {
  mode: "empty" | "plan";
  title: string;
  headline: string;
  summary: string;
  planningNote: string | null;
  executionStatus: TonightPlannerResponse["executionStatus"];
  executionNote: string | null;
  activeTargetEventId: string | null;
  activeTargetVenueName: string | null;
  outcomeStatus: TonightPlannerResponse["outcomeStatus"];
  outcomeNote: string | null;
  rerouteStatus: TonightPlannerResponse["rerouteStatus"];
  rerouteNote: string | null;
  rerouteOption: TonightPlannerRerouteOption | null;
  sessionId: string | null;
  sessionStatus: TonightPlannerResponse["sessionStatus"];
  activeStop: TonightPlannerStop | null;
  remainingStops: TonightPlannerStop[];
  droppedStops: TonightPlannerStop[];
  recompositionReason: string | null;
  lastRecomputedAt: string | null;
  lifecycleReason: string | null;
  createdFreshBecauseStale: boolean;
  lastEventAt: string | null;
  stopCountLabel: string | null;
  fallbackCount: number;
  stops: TonightPlannerStop[];
}

export interface PlannerSessionRouteUpdate {
  sessionId: string;
  sessionStatus?: string | null;
  activeStop?: TonightPlannerStop | null;
  remainingStops?: TonightPlannerStop[] | null;
  droppedStops?: TonightPlannerStop[] | null;
  recompositionReason?: string | null;
  lastRecomputedAt?: string | null;
  lastEventAt?: string | null;
}

export function applyPlannerSessionRouteUpdate(
  planner: TonightPlannerResponse | null | undefined,
  update: PlannerSessionRouteUpdate | null | undefined,
): TonightPlannerResponse | null | undefined {
  if (!planner || !update) {
    return planner;
  }

  const remainingStops = update.remainingStops ?? planner.remainingStops ?? [];
  const activeStop = update.activeStop ?? planner.activeStop ?? remainingStops[0] ?? null;

  return {
    ...planner,
    sessionId: update.sessionId ?? planner.sessionId,
    sessionStatus: update.sessionStatus ?? planner.sessionStatus,
    activeStop,
    activeTargetEventId: activeStop?.eventId ?? planner.activeTargetEventId ?? null,
    activeTargetVenueName: activeStop?.venueName ?? planner.activeTargetVenueName ?? null,
    remainingStops,
    droppedStops: update.droppedStops ?? planner.droppedStops ?? [],
    recompositionReason: update.recompositionReason ?? planner.recompositionReason ?? null,
    lastRecomputedAt: update.lastRecomputedAt ?? planner.lastRecomputedAt ?? null,
    lastEventAt: update.lastEventAt ?? planner.lastEventAt ?? null,
    stops: remainingStops.length ? remainingStops : planner.stops,
  };
}

export function buildTonightPlannerPanelState(
  planner: TonightPlannerResponse | null | undefined,
): TonightPlannerPanelState {
  if (!planner || planner.status === "empty" || !planner.stops.length) {
    return {
      mode: "empty",
      title: planner?.title ?? "Tonight planner",
      headline: "Build a night from the shortlist",
      summary:
        planner?.summary ??
        "Komme will sketch a 2-3 stop route once tonight has enough viable options in the current shortlist.",
      planningNote: planner?.planningNote ?? null,
      executionStatus: planner?.executionStatus ?? "idle",
      executionNote: planner?.executionNote ?? null,
      activeTargetEventId: planner?.activeTargetEventId ?? null,
      activeTargetVenueName: planner?.activeTargetVenueName ?? null,
      outcomeStatus: planner?.outcomeStatus ?? "idle",
      outcomeNote: planner?.outcomeNote ?? null,
      rerouteStatus: planner?.rerouteStatus ?? "idle",
      rerouteNote: planner?.rerouteNote ?? null,
      rerouteOption: planner?.rerouteOption ?? null,
      sessionId: planner?.sessionId ?? null,
      sessionStatus: planner?.sessionStatus ?? null,
      activeStop: planner?.activeStop ?? null,
      remainingStops: planner?.remainingStops ?? [],
      droppedStops: planner?.droppedStops ?? [],
      recompositionReason: planner?.recompositionReason ?? null,
      lastRecomputedAt: planner?.lastRecomputedAt ?? null,
      lifecycleReason: planner?.lifecycleReason ?? null,
      createdFreshBecauseStale: planner?.createdFreshBecauseStale ?? false,
      lastEventAt: planner?.lastEventAt ?? null,
      stopCountLabel: null,
      fallbackCount: 0,
      stops: [],
    };
  }

  const fallbackCount = planner.stops.reduce((count, stop) => count + stop.fallbacks.length, 0);
  const stopCountLabel = planner.stops.length === 1 ? "1 stop ready" : `${planner.stops.length} stops ready`;

  return {
    mode: "plan",
    title: planner.title || "Tonight planner",
    headline: stopCountLabel,
    summary:
      planner.summary ??
      "Komme turned the current shortlist into a lightweight plan for tonight.",
    planningNote: planner.planningNote ?? null,
    executionStatus: planner.executionStatus,
    executionNote: planner.executionNote ?? null,
    activeTargetEventId: planner.activeTargetEventId ?? null,
    activeTargetVenueName: planner.activeTargetVenueName ?? null,
    outcomeStatus: planner.outcomeStatus,
    outcomeNote: planner.outcomeNote ?? null,
    rerouteStatus: planner.rerouteStatus,
    rerouteNote: planner.rerouteNote ?? null,
    rerouteOption: planner.rerouteOption ?? null,
    sessionId: planner.sessionId ?? null,
    sessionStatus: planner.sessionStatus ?? null,
    activeStop: planner.activeStop ?? null,
    remainingStops: planner.remainingStops ?? planner.stops,
    droppedStops: planner.droppedStops ?? [],
    recompositionReason: planner.recompositionReason ?? null,
    lastRecomputedAt: planner.lastRecomputedAt ?? null,
    lifecycleReason: planner.lifecycleReason ?? null,
    createdFreshBecauseStale: planner.createdFreshBecauseStale ?? false,
    lastEventAt: planner.lastEventAt ?? null,
    stopCountLabel,
    fallbackCount,
    stops: planner.stops,
  };
}

export function plannerSupportLabel(stop: TonightPlannerStop): string {
  if (!stop.fallbacks.length) {
    return stop.confidenceReason;
  }

  const swapLabel = stop.fallbacks.length === 1 ? "1 swap ready" : `${stop.fallbacks.length} swaps ready`;
  return `${swapLabel} · ${stop.confidenceReason}`;
}

export function plannerStopActionLabel(stop: TonightPlannerStop): string {
  return stop.selected ? "Locked tonight" : "Lock this stop";
}

export function plannerFallbackActionLabel(selected: boolean): string {
  return selected ? "Swap active" : "Use this swap";
}

export function plannerOutcomePrompt(
  activeTargetVenueName: string | null,
  outcomeStatus: TonightPlannerResponse["outcomeStatus"],
  outcomeNote: string | null,
): string | null {
  if (!activeTargetVenueName) {
    return null;
  }
  if (outcomeStatus !== "pending" && outcomeNote) {
    return outcomeNote;
  }
  return `Let Komme know whether ${activeTargetVenueName} actually made tonight's plan.`;
}

export function plannerRerouteButtonLabel(option: TonightPlannerRerouteOption | null): string {
  if (!option) {
    return "Switch now";
  }
  return option.sourceKind === "fallback" ? "Use this pivot" : "Jump ahead";
}
