"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { getRecommendationDebugSummary, getRecommendationRunComparison } from "@/lib/api";
import type {
  RecommendationDebugSummary,
  RecommendationDriverSummary,
  RecommendationFeedbackReasonSummary,
  RecommendationMovementCue,
  RecommendationRunComparison,
  RecommendationRunComparisonItem,
  RecommendationScoreBreakdownItem,
} from "@/lib/types";
import { formatTimestamp } from "@/lib/utils";

function SectionShell({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
}) {
  return (
    <section className="rounded-[1.75rem] border border-stroke bg-white/80 p-5 shadow-[0_16px_40px_rgba(20,33,61,0.06)]">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-2xl font-semibold text-slate-900">{title}</h2>
          {subtitle ? <p className="mt-1 text-sm leading-6 text-slate-500">{subtitle}</p> : null}
        </div>
      </div>
      <div className="mt-5">{children}</div>
    </section>
  );
}

function DriverChip({ driver }: { driver: RecommendationDriverSummary }) {
  return (
    <div className="rounded-[1.25rem] border border-stroke/80 bg-canvas px-4 py-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-semibold text-slate-900">{driver.label}</p>
        <span className="rounded-full bg-white px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-slate-600">
          {driver.impactLabel}
        </span>
      </div>
      <p className="mt-2 text-sm text-slate-600">
        Avg contribution {driver.averageContribution > 0 ? "+" : ""}
        {driver.averageContribution.toFixed(3)} across {driver.venueCount} venues
      </p>
      {driver.topVenues.length ? (
        <div className="mt-3 flex flex-wrap gap-2 text-xs font-medium text-slate-600">
          {driver.topVenues.map((venue) => (
            <span key={venue} className="rounded-full border border-stroke/80 bg-white px-3 py-1">
              {venue}
            </span>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function FeedbackReasonChip({ item }: { item: RecommendationFeedbackReasonSummary }) {
  return (
    <div className="rounded-[1.25rem] border border-stroke/80 bg-canvas px-4 py-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-semibold text-slate-900">{item.label}</p>
        <span className="rounded-full bg-white px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-slate-600">
          {item.count}x
        </span>
      </div>
      <p className="mt-2 text-sm text-slate-600">
        Weighted strength {item.weightedStrength.toFixed(3)}
      </p>
    </div>
  );
}

function FactorChip({ factor }: { factor: RecommendationScoreBreakdownItem }) {
  return (
    <span
      className={[
        "rounded-full border px-3 py-1 text-xs font-medium",
        factor.direction === "negative"
          ? "border-amber-200 bg-amber-50 text-amber-800"
          : "border-stroke/80 bg-canvas text-slate-700",
      ].join(" ")}
      title={factor.detail}
    >
      {factor.label} · {factor.impactLabel}
    </span>
  );
}

function MovementChip({ movement }: { movement: RecommendationRunComparisonItem["movement"] }) {
  const styles =
    movement === "new"
      ? "bg-emerald-50 text-emerald-700 border-emerald-200"
      : movement === "dropped"
        ? "bg-rose-50 text-rose-700 border-rose-200"
        : movement === "up"
          ? "bg-sky-50 text-sky-700 border-sky-200"
          : movement === "down"
            ? "bg-amber-50 text-amber-800 border-amber-200"
            : "bg-slate-100 text-slate-700 border-slate-200";

  return (
    <span className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.14em] ${styles}`}>
      {movement}
    </span>
  );
}

function MovementCueChip({ cue }: { cue: RecommendationMovementCue }) {
  return (
    <span
      className={[
        "rounded-full border px-3 py-1 text-xs font-medium",
        cue.direction === "negative"
          ? "border-amber-200 bg-amber-50 text-amber-800"
          : "border-sky-200 bg-sky-50 text-sky-800",
      ].join(" ")}
      title={`Contribution delta ${cue.delta > 0 ? "+" : ""}${cue.delta.toFixed(3)}`}
    >
      {cue.label} {cue.direction === "positive" ? "\u2191" : "\u2193"}
    </span>
  );
}

function ComparisonTable({
  title,
  items,
  emptyLabel,
}: {
  title: string;
  items: RecommendationRunComparisonItem[];
  emptyLabel: string;
}) {
  return (
    <div className="rounded-[1.25rem] border border-stroke/80 bg-canvas/80 p-4">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-lg font-semibold text-slate-900">{title}</h3>
        <span className="rounded-full bg-white px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
          {items.length}
        </span>
      </div>

      {items.length ? (
        <div className="mt-4 space-y-3">
          {items.map((item) => (
            <div key={`${title}-${item.venueId}`} className="rounded-[1rem] border border-stroke/80 bg-white px-4 py-3">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-slate-900">{item.venueName}</p>
                  <p className="mt-1 text-sm text-slate-500">{item.neighborhood}</p>
                </div>
                <MovementChip movement={item.movement} />
              </div>
              <div className="mt-3 flex flex-wrap gap-2 text-xs font-medium text-slate-600">
                {item.currentRank ? (
                  <span className="rounded-full border border-stroke/80 bg-canvas px-3 py-1">Now #{item.currentRank}</span>
                ) : null}
                {item.previousRank ? (
                  <span className="rounded-full border border-stroke/80 bg-canvas px-3 py-1">Was #{item.previousRank}</span>
                ) : null}
                {item.rankDelta ? (
                  <span className="rounded-full border border-stroke/80 bg-canvas px-3 py-1">
                    Rank delta {item.rankDelta > 0 ? "+" : ""}
                    {item.rankDelta}
                  </span>
                ) : null}
                {typeof item.scoreDelta === "number" ? (
                  <span className="rounded-full border border-stroke/80 bg-canvas px-3 py-1">
                    Score delta {item.scoreDelta > 0 ? "+" : ""}
                    {item.scoreDelta.toFixed(3)}
                  </span>
                ) : null}
              </div>
              {item.movementCues.length ? (
                <div className="mt-3 flex flex-wrap gap-2">
                  {item.movementCues.map((cue) => (
                    <MovementCueChip key={`${item.venueId}-${cue.key}`} cue={cue} />
                  ))}
                </div>
              ) : item.scoreSummary ? (
                <p className="mt-3 text-sm leading-6 text-slate-600">{item.scoreSummary}</p>
              ) : null}
            </div>
          ))}
        </div>
      ) : (
        <p className="mt-4 text-sm text-slate-500">{emptyLabel}</p>
      )}
    </div>
  );
}

function SummaryPanel({
  debugSummary,
  comparison,
}: {
  debugSummary: RecommendationDebugSummary;
  comparison: RecommendationRunComparison;
}) {
  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <div className="rounded-[1.25rem] border border-stroke/80 bg-canvas px-4 py-4">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Current run</p>
        <p className="mt-2 text-lg font-semibold text-slate-900">{debugSummary.runId ?? "Unavailable"}</p>
        <p className="mt-2 text-sm text-slate-600">Generated {formatTimestamp(debugSummary.generatedAt)}</p>
        <p className="mt-1 text-sm text-slate-600">{debugSummary.shortlistSize} shortlisted venues</p>
      </div>
      <div className="rounded-[1.25rem] border border-stroke/80 bg-canvas px-4 py-4">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Context hash</p>
        <p className="mt-2 break-all font-mono text-sm text-slate-800">{debugSummary.contextHash ?? "Unavailable"}</p>
        <p className="mt-2 text-sm text-slate-600">Model {debugSummary.rankingModel ?? "Unknown"}</p>
      </div>
      <div className="rounded-[1.25rem] border border-stroke/80 bg-canvas px-4 py-4">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Run comparison</p>
        <p className="mt-2 text-lg font-semibold text-slate-900">{comparison.comparableVenueCount} comparable venues</p>
        <p className="mt-2 text-sm text-slate-600">Previous run {comparison.previousRunId ?? "Unavailable"}</p>
        <p className="mt-1 text-sm text-slate-600">Generated {formatTimestamp(comparison.previousGeneratedAt)}</p>
      </div>
    </div>
  );
}

export function RecommendationOpsPageContent() {
  const debugSummaryQuery = useQuery({
    queryKey: ["recommendation-debug-summary"],
    queryFn: getRecommendationDebugSummary,
  });
  const comparisonQuery = useQuery({
    queryKey: ["recommendation-run-comparison"],
    queryFn: getRecommendationRunComparison,
  });

  const isLoading = debugSummaryQuery.isLoading || comparisonQuery.isLoading;
  const error = debugSummaryQuery.error ?? comparisonQuery.error;
  const debugSummary = debugSummaryQuery.data;
  const comparison = comparisonQuery.data;

  return (
    <main className="min-h-screen px-4 py-6 md:px-6">
      <div className="mx-auto max-w-6xl rounded-[2rem] border border-stroke/80 bg-card/80 p-6 shadow-float">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">Internal ops</p>
            <h1 className="mt-2 text-4xl font-semibold tracking-tight text-slate-900">Recommendation diagnostics</h1>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">
              Use this page to inspect the current run, compare it against the previous shortlist, and see what is driving ranking movement.
            </p>
          </div>
          <Link href="/" className="rounded-full border border-stroke px-4 py-2 text-sm text-slate-700">
            Back to map
          </Link>
        </div>

        {isLoading ? (
          <div className="mt-6 rounded-[1.75rem] border border-stroke bg-white/70 p-5 text-sm text-slate-500">
            Loading recommendation diagnostics...
          </div>
        ) : null}

        {error instanceof Error ? (
          <div className="mt-6 rounded-[1.75rem] border border-rose-200 bg-rose-50 p-5 text-sm text-rose-700">
            {error.message}
          </div>
        ) : null}

        {debugSummary && comparison ? (
          <div className="mt-6 grid gap-6">
            <SummaryPanel debugSummary={debugSummary} comparison={comparison} />

            <SectionShell
              title="Run summary"
              subtitle={debugSummary.summary ?? "Pulse has not generated a summary for this run yet."}
            >
              <div className="grid gap-4 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)]">
                <div className="rounded-[1.25rem] border border-stroke/80 bg-canvas px-4 py-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Anchor context</p>
                  <p className="mt-2 text-lg font-semibold text-slate-900">{debugSummary.mapContext.activeAnchorLabel}</p>
                  <p className="mt-2 text-sm text-slate-600">
                    {debugSummary.mapContext.fallbackReason ?? "No fallback in play for this run."}
                  </p>
                </div>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="rounded-[1.25rem] border border-stroke/80 bg-canvas px-4 py-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Active topics</p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {debugSummary.activeTopics.length ? (
                        debugSummary.activeTopics.map((topic) => (
                          <span key={topic} className="rounded-full border border-stroke/80 bg-white px-3 py-1 text-xs font-medium text-slate-700">
                            {topic}
                          </span>
                        ))
                      ) : (
                        <span className="text-sm text-slate-500">None</span>
                      )}
                    </div>
                  </div>
                  <div className="rounded-[1.25rem] border border-stroke/80 bg-canvas px-4 py-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Muted topics</p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {debugSummary.mutedTopics.length ? (
                        debugSummary.mutedTopics.map((topic) => (
                          <span key={topic} className="rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-medium text-amber-800">
                            {topic}
                          </span>
                        ))
                      ) : (
                        <span className="text-sm text-slate-500">None</span>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </SectionShell>

            <SectionShell title="Driver summary" subtitle="Aggregated across the current shortlist.">
              <div className="grid gap-4 lg:grid-cols-2">
                <div className="space-y-4">
                  <h3 className="text-lg font-semibold text-slate-900">Top positive drivers</h3>
                  {debugSummary.topPositiveDrivers.length ? (
                    debugSummary.topPositiveDrivers.map((driver) => <DriverChip key={driver.key} driver={driver} />)
                  ) : (
                    <p className="text-sm text-slate-500">No strong positive drivers were detected.</p>
                  )}
                </div>
                <div className="space-y-4">
                  <h3 className="text-lg font-semibold text-slate-900">Top negative drivers</h3>
                  {debugSummary.topNegativeDrivers.length ? (
                    debugSummary.topNegativeDrivers.map((driver) => <DriverChip key={driver.key} driver={driver} />)
                  ) : (
                    <p className="text-sm text-slate-500">No strong negative drivers were detected.</p>
                  )}
                </div>
              </div>
            </SectionShell>

            <SectionShell title="Feedback learning" subtitle="Recent save and dismiss reasons feeding the current ranker.">
              <div className="grid gap-4 lg:grid-cols-2">
                <div className="space-y-4">
                  <h3 className="text-lg font-semibold text-slate-900">Top save reasons</h3>
                  {debugSummary.topSaveReasons.length ? (
                    debugSummary.topSaveReasons.map((item) => <FeedbackReasonChip key={`save-${item.key}`} item={item} />)
                  ) : (
                    <p className="text-sm text-slate-500">No save reasons have been captured yet.</p>
                  )}
                </div>
                <div className="space-y-4">
                  <h3 className="text-lg font-semibold text-slate-900">Top dismiss reasons</h3>
                  {debugSummary.topDismissReasons.length ? (
                    debugSummary.topDismissReasons.map((item) => (
                      <FeedbackReasonChip key={`dismiss-${item.key}`} item={item} />
                    ))
                  ) : (
                    <p className="text-sm text-slate-500">No dismiss reasons have been captured yet.</p>
                  )}
                </div>
              </div>
            </SectionShell>

            <SectionShell
              title="Run comparison"
              subtitle={comparison.summary ?? "Pulse needs more ranking history before the comparison becomes interesting."}
            >
              <div className="grid gap-4 xl:grid-cols-2">
                <ComparisonTable title="New entrants" items={comparison.newEntrants} emptyLabel="No new venues entered this run." />
                <ComparisonTable title="Dropped venues" items={comparison.droppedVenues} emptyLabel="No venues dropped out this run." />
                <ComparisonTable title="Movers" items={comparison.movers} emptyLabel="No venues shifted meaningfully this run." />
                <ComparisonTable title="Steady leaders" items={comparison.steadyLeaders} emptyLabel="No steady leaders yet." />
              </div>
            </SectionShell>

            <SectionShell title="Current shortlist factors" subtitle="Top drivers for each venue in the current run.">
              <div className="grid gap-4">
                {debugSummary.venues.map((venue) => (
                  <div key={venue.venueId} className="rounded-[1.25rem] border border-stroke/80 bg-canvas/80 p-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <p className="text-xs uppercase tracking-[0.18em] text-slate-500">#{venue.rank}</p>
                        <h3 className="mt-1 text-xl font-semibold text-slate-900">{venue.venueName}</h3>
                      </div>
                      <span className="rounded-full bg-white px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-slate-600">
                        {venue.scoreBand} · {venue.score.toFixed(3)}
                      </span>
                    </div>
                    {venue.scoreSummary ? <p className="mt-3 text-sm leading-6 text-slate-700">{venue.scoreSummary}</p> : null}
                    <div className="mt-3 flex flex-wrap gap-2">
                      {venue.topDrivers.map((factor) => (
                        <FactorChip key={`${venue.venueId}-${factor.key}`} factor={factor} />
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </SectionShell>
          </div>
        ) : null}
      </div>
    </main>
  );
}
