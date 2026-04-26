"use client";

import { CircleCheck, Clock3, Route, Sparkles } from "lucide-react";
import {
  buildTonightPlannerPanelState,
  plannerFallbackActionLabel,
  plannerOutcomePrompt,
  plannerStopActionLabel,
  plannerSupportLabel,
} from "@/lib/tonight-planner";
import type { TonightPlannerFallbackOption, TonightPlannerResponse, TonightPlannerStop } from "@/lib/types";
import { formatEventStart } from "@/lib/utils";

function roleTone(role: TonightPlannerStop["role"]) {
  if (role === "main_event") {
    return "border-teal-200 bg-teal-50 text-teal-900";
  }
  if (role === "pregame") {
    return "border-amber-200 bg-amber-50 text-amber-900";
  }
  if (role === "late_option") {
    return "border-sky-200 bg-sky-50 text-sky-900";
  }
  return "border-slate-200 bg-slate-100 text-slate-700";
}

function confidenceTone(confidence: TonightPlannerStop["confidence"]) {
  if (confidence === "high") {
    return "border-teal-200 bg-teal-50 text-teal-900";
  }
  if (confidence === "medium") {
    return "border-sky-200 bg-sky-50 text-sky-900";
  }
  return "border-amber-200 bg-amber-50 text-amber-900";
}

function metaChips(stop: TonightPlannerStop) {
  return [stop.neighborhood, stop.priceLabel, stop.hopLabel].filter((item): item is string => Boolean(item));
}

export function TonightPlannerPanel({
  loading,
  planner,
  timezone,
  selectedVenueId,
  onSelectVenue,
  onCommitStop,
  onSwapFallback,
  actionPending,
  outcomePending,
  onMarkOutcome,
}: {
  loading: boolean;
  planner: TonightPlannerResponse | null | undefined;
  timezone: string;
  selectedVenueId: string | null;
  onSelectVenue: (venueId: string) => void;
  onCommitStop: (stop: TonightPlannerStop) => void;
  onSwapFallback: (option: TonightPlannerFallbackOption) => void;
  actionPending: boolean;
  outcomePending: boolean;
  onMarkOutcome: (action: "planner_attended" | "planner_skipped") => void;
}) {
  const panelState = buildTonightPlannerPanelState(planner);
  const outcomePrompt = plannerOutcomePrompt(
    panelState.activeTargetVenueName,
    panelState.outcomeStatus,
    panelState.outcomeNote,
  );

  return (
    <section className="rounded-[2rem] border border-stroke/80 bg-card/80 p-4 shadow-float backdrop-blur">
      <div className="px-2 pb-3">
        <div className="flex flex-wrap items-center gap-2 text-sm font-medium uppercase tracking-[0.22em] text-slate-500">
          <Sparkles className="h-4 w-4 text-accent" />
          <span>{panelState.title}</span>
          {panelState.stopCountLabel ? (
            <span className="rounded-full border border-stroke/80 bg-white/70 px-3 py-1 text-[11px] tracking-[0.18em] text-slate-600">
              {panelState.stopCountLabel}
            </span>
          ) : null}
          {panelState.fallbackCount ? (
            <span className="rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-[11px] tracking-[0.18em] text-amber-800">
              {panelState.fallbackCount === 1 ? "1 swap flagged" : `${panelState.fallbackCount} swaps flagged`}
            </span>
          ) : null}
        </div>
        <h2 className="mt-2 text-xl font-semibold text-slate-900">{panelState.headline}</h2>
        <p className="mt-1 text-sm leading-6 text-slate-500">
          {loading ? "Pulse is sequencing the live shortlist into a workable night..." : panelState.summary}
        </p>
        {panelState.executionNote ? (
          <div
            className={[
              "mt-3 inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-medium",
              panelState.executionStatus === "swapped"
                ? "border-amber-200 bg-amber-50 text-amber-900"
                : "border-teal-200 bg-teal-50 text-teal-900",
            ].join(" ")}
          >
            <CircleCheck className="h-3.5 w-3.5" />
            {panelState.executionNote}
          </div>
        ) : null}
        {panelState.activeTargetVenueName && outcomePrompt ? (
          <div className="mt-3 rounded-[1.5rem] border border-stroke/80 bg-white/80 p-3">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="min-w-0">
                <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Tonight outcome</p>
                <p className="mt-1 text-sm leading-6 text-slate-600">{outcomePrompt}</p>
              </div>
              <div className="flex shrink-0 flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => onMarkOutcome("planner_attended")}
                  disabled={outcomePending}
                  className={[
                    "rounded-full px-3 py-2 text-xs font-medium transition disabled:opacity-60",
                    panelState.outcomeStatus === "attended"
                      ? "border border-teal-200 bg-teal-50 text-teal-900"
                      : "bg-accent text-white",
                  ].join(" ")}
                >
                  Made it
                </button>
                <button
                  type="button"
                  onClick={() => onMarkOutcome("planner_skipped")}
                  disabled={outcomePending}
                  className={[
                    "rounded-full px-3 py-2 text-xs font-medium transition disabled:opacity-60",
                    panelState.outcomeStatus === "skipped"
                      ? "border border-slate-200 bg-slate-100 text-slate-700"
                      : "border border-stroke bg-white text-slate-700",
                  ].join(" ")}
                >
                  Passed
                </button>
              </div>
            </div>
          </div>
        ) : null}
      </div>

      {loading ? (
        <div className="rounded-[1.75rem] border border-stroke bg-white/70 p-5 text-sm text-slate-500">
          Loading tonight&apos;s route from the current shortlist...
        </div>
      ) : null}

      {!loading && panelState.mode === "empty" ? (
        <div className="rounded-[1.75rem] border border-dashed border-stroke bg-white/70 p-5 text-sm leading-6 text-slate-500">
          {panelState.summary}
          {panelState.planningNote ? <p className="mt-3 text-xs uppercase tracking-[0.18em] text-slate-400">{panelState.planningNote}</p> : null}
        </div>
      ) : null}

      {!loading && panelState.mode === "plan" ? (
        <div className="space-y-3">
          {panelState.stops.map((stop) => {
            const selected = stop.venueId === selectedVenueId;
            return (
              <article
                key={`${stop.role}-${stop.venueId}`}
                role="button"
                tabIndex={0}
                onClick={() => onSelectVenue(stop.venueId)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    onSelectVenue(stop.venueId);
                  }
                }}
                className={[
                  "rounded-[1.75rem] border p-4 text-left transition",
                  selected ? "border-accent bg-accentSoft/60" : "border-stroke bg-white/80 hover:bg-white",
                ].join(" ")}
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className={["rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.2em]", roleTone(stop.role)].join(" ")}>
                    {stop.roleLabel}
                  </span>
                  <span
                    className={[
                      "rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.2em]",
                      confidenceTone(stop.confidence),
                    ].join(" ")}
                  >
                    {stop.confidenceLabel}
                  </span>
                </div>

                <div className="mt-3">
                  <h3 className="text-lg font-semibold text-slate-900">{stop.venueName}</h3>
                  <p className="mt-1 text-sm text-slate-600">{stop.eventTitle}</p>
                </div>

                <div className="mt-3 flex flex-wrap items-center gap-3 text-sm text-slate-600">
                  <span className="inline-flex items-center gap-1">
                    <Clock3 className="h-4 w-4" />
                    {formatEventStart(stop.startsAt, timezone)}
                  </span>
                </div>

                <div className="mt-3 flex flex-wrap gap-2 text-xs font-medium text-slate-600">
                  {metaChips(stop).map((item) => (
                    <span key={`${stop.venueId}-${item}`} className="rounded-full border border-stroke/80 bg-white px-3 py-1">
                      {item}
                    </span>
                  ))}
                </div>

                <p className="mt-3 text-sm leading-6 text-slate-700">{stop.roleReason}</p>

                <div className="mt-3 inline-flex items-center gap-2 rounded-full border border-stroke/80 bg-white/75 px-3 py-1 text-xs font-medium text-slate-600">
                  <Route className="h-3.5 w-3.5" />
                  {plannerSupportLabel(stop)}
                </div>

                <div className="mt-4 flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={(event) => {
                      event.stopPropagation();
                      onCommitStop(stop);
                    }}
                    disabled={actionPending}
                    className={[
                      "inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium transition disabled:opacity-60",
                      stop.selected
                        ? "border border-teal-200 bg-teal-50 text-teal-900"
                        : "bg-accent text-white",
                    ].join(" ")}
                  >
                    <CircleCheck className="h-4 w-4" />
                    {plannerStopActionLabel(stop)}
                  </button>
                </div>

                {stop.fallbacks.length ? (
                  <div className="mt-4 rounded-2xl border border-dashed border-amber-200 bg-amber-50/80 p-3">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-amber-800">Swap if needed</p>
                    <div className="mt-2 space-y-2">
                      {stop.fallbacks.map((option) => (
                        <FallbackOptionButton
                          key={`${stop.venueId}-${option.venueId}`}
                          option={option}
                          timezone={timezone}
                          selected={selectedVenueId === option.venueId}
                          actionPending={actionPending}
                          onSelectVenue={onSelectVenue}
                          onSwapFallback={onSwapFallback}
                        />
                      ))}
                    </div>
                  </div>
                ) : null}
              </article>
            );
          })}

          {panelState.planningNote ? <p className="px-2 text-xs uppercase tracking-[0.18em] text-slate-400">{panelState.planningNote}</p> : null}
        </div>
      ) : null}
    </section>
  );
}

function FallbackOptionButton({
  option,
  timezone,
  selected,
  actionPending,
  onSelectVenue,
  onSwapFallback,
}: {
  option: TonightPlannerFallbackOption;
  timezone: string;
  selected: boolean;
  actionPending: boolean;
  onSelectVenue: (venueId: string) => void;
  onSwapFallback: (option: TonightPlannerFallbackOption) => void;
}) {
  return (
    <div
      className={[
        "rounded-2xl border px-3 py-3 text-left transition",
        selected ? "border-accent bg-white" : "border-amber-200 bg-white/80 hover:bg-white",
      ].join(" ")}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-sm font-semibold text-slate-900">{option.venueName}</span>
        <span className="rounded-full border border-stroke/80 bg-white px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-600">
          {option.scoreBand}
        </span>
      </div>
      <p className="mt-1 text-sm text-slate-600">{option.eventTitle}</p>
      <div className="mt-2 flex flex-wrap gap-2 text-xs font-medium text-slate-600">
        <span className="rounded-full border border-stroke/80 bg-white px-3 py-1">{formatEventStart(option.startsAt, timezone)}</span>
        <span className="rounded-full border border-stroke/80 bg-white px-3 py-1">{option.priceLabel}</span>
        {option.hopLabel ? <span className="rounded-full border border-stroke/80 bg-white px-3 py-1">{option.hopLabel}</span> : null}
      </div>
      <p className="mt-2 text-xs leading-5 text-amber-900">{option.fallbackReason}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={(event) => {
            event.stopPropagation();
            onSelectVenue(option.venueId);
          }}
          className="rounded-full border border-stroke bg-white px-3 py-2 text-xs font-medium text-slate-700"
        >
          Focus on map
        </button>
        <button
          type="button"
          onClick={(event) => {
            event.stopPropagation();
            onSwapFallback(option);
          }}
          disabled={actionPending}
          className={[
            "rounded-full px-3 py-2 text-xs font-medium transition disabled:opacity-60",
            option.selected
              ? "border border-amber-200 bg-amber-100 text-amber-900"
              : "bg-amber-500 text-white",
          ].join(" ")}
        >
          {plannerFallbackActionLabel(option.selected)}
        </button>
      </div>
    </div>
  );
}
