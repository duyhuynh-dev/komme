import type { TonightPlannerResponse, TonightPlannerStop } from "./types";

export interface TonightPlannerPanelState {
  mode: "empty" | "plan";
  title: string;
  headline: string;
  summary: string;
  planningNote: string | null;
  stopCountLabel: string | null;
  fallbackCount: number;
  stops: TonightPlannerStop[];
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
        "Pulse will sketch a 2-3 stop route once tonight has enough viable options in the current shortlist.",
      planningNote: planner?.planningNote ?? null,
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
      "Pulse turned the current shortlist into a lightweight plan for tonight.",
    planningNote: planner.planningNote ?? null,
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
