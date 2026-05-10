"use client";

import { useEffect, useRef } from "react";
import { Bookmark, MapPin, MoveRight, XCircle } from "lucide-react";
import { personalizationSourceLabel } from "@/lib/connected-source-health";
import type { RecommendationRunComparisonItem, VenueRecommendationCard } from "@/lib/types";
import { formatEventStart, formatRelativeTimestamp } from "@/lib/utils";

export function RecommendationDrawer({
  loading,
  cards,
  timezone,
  selectedVenueId,
  onSelectVenue,
  onExposeCards,
  onTrackInteraction,
  onSave,
  onDismiss,
  comparisonByVenueId = {},
  mode = "rail",
  previewCount = 2,
  isExpanded = false,
  onToggleExpanded
}: {
  loading: boolean;
  cards: Record<string, VenueRecommendationCard>;
  timezone: string;
  selectedVenueId: string | null;
  onSelectVenue: (venueId: string) => void;
  onExposeCards?: (cards: VenueRecommendationCard[]) => void;
  onTrackInteraction?: (recommendationId: string, action: "ticket_click") => void;
  onSave: (card: VenueRecommendationCard) => void;
  onDismiss: (card: VenueRecommendationCard) => void;
  comparisonByVenueId?: Record<string, RecommendationRunComparisonItem>;
  mode?: "rail" | "modal";
  previewCount?: number;
  isExpanded?: boolean;
  onToggleExpanded?: () => void;
}) {
  const isRail = mode === "rail";
  const orderedCards = Object.values(cards).sort((left, right) => right.score - left.score);
  const visibleCards = isRail ? orderedCards.slice(0, previewCount) : orderedCards;
  const canShowAll = isRail && orderedCards.length > visibleCards.length;
  const breakdownPreviewCount = isRail ? 3 : 5;
  const cardRefs = useRef<Record<string, HTMLElement | null>>({});
  const visibleCardSignature = visibleCards.map((card) => card.eventId).join("|");

  useEffect(() => {
    if (!selectedVenueId) {
      return;
    }

    const target = cardRefs.current[selectedVenueId];
    target?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [selectedVenueId]);

  useEffect(() => {
    if (loading || !onExposeCards || !visibleCards.length) {
      return;
    }
    onExposeCards(visibleCards);
  }, [loading, onExposeCards, visibleCardSignature]);

  return (
    <aside
      className={[
        "flex min-h-0 flex-col",
        isRail
          ? "h-full rounded-[1.6rem] border border-stroke/80 bg-card/80 p-3.5 shadow-float backdrop-blur"
          : ""
      ].join(" ")}
    >
      <div className={isRail ? "px-1.5 pb-2.5" : "px-2 pb-3"}>
        <button
          type="button"
          onClick={isRail ? onToggleExpanded : undefined}
          className={[
            "min-w-0 text-left",
            isRail ? "transition hover:opacity-80" : ""
          ].join(" ")}
          aria-expanded={isRail ? isExpanded : undefined}
        >
          <h2 className={`${isRail ? "text-base" : "text-2xl"} font-semibold`}>Top events</h2>
          <p className={`${isRail ? "mt-0.5 text-xs leading-5" : "mt-1 text-sm"} text-slate-500`}>
            {isRail ? "Tap to focus." : "Choose an event to focus the map."}
          </p>
        </button>
      </div>

      <div className={["min-h-0 pr-1", isRail ? "flex-1 space-y-2.5 overflow-y-auto" : "space-y-4"].join(" ")}>
        {loading ? (
          <div className={`${isRail ? "rounded-[1.25rem] p-3 text-xs" : "rounded-3xl p-5 text-sm"} border border-stroke bg-white/70 text-slate-500`}>
            Loading your current event shortlist...
          </div>
        ) : null}

        {!loading && !orderedCards.length ? (
          <div className={`${isRail ? "rounded-[1.25rem] p-3 text-xs" : "rounded-3xl p-5 text-sm"} border border-dashed border-stroke bg-white/70 text-slate-500`}>
            No saved recommendation run yet. Check for new events, then refresh picks to populate this drawer.
          </div>
        ) : null}

        {visibleCards.map((card) => {
          const selected = card.venueId === selectedVenueId;
          const comparison = comparisonByVenueId[card.venueId];
          const movementCues = comparison?.movementCues ?? [];
          const eventUrl = card.eventUrl ?? card.ticketUrl;
          const movementLabel =
            comparison?.movement === "new"
              ? "New"
              : comparison?.movement === "up"
                ? `Up ${Math.abs(comparison.rankDelta ?? 0)}`
                : comparison?.movement === "down"
                  ? `Down ${Math.abs(comparison.rankDelta ?? 0)}`
                  : null;

          return (
            <article
              key={card.venueId}
              ref={(node) => {
                cardRefs.current[card.venueId] = node;
              }}
              role="button"
              tabIndex={0}
              onClick={() => onSelectVenue(card.venueId)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  onSelectVenue(card.venueId);
                }
              }}
              className={[
                "w-full border text-left transition",
                isRail ? "rounded-[1.25rem] p-3" : "rounded-[1.75rem] p-4",
                selected ? "border-accent bg-accentSoft/60" : "border-stroke bg-white/80 hover:bg-white"
              ].join(" ")}
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className={`${isRail ? "text-[11px] tracking-[0.2em]" : "text-xs tracking-[0.22em]"} uppercase text-slate-500`}>{card.neighborhood}</p>
                  <h3 className={`${isRail ? "mt-1 text-[15px]" : "mt-2 text-lg"} font-semibold text-slate-900`}>{card.eventTitle}</h3>
                  <p className={`${isRail ? "mt-0.5 text-xs" : "mt-1 text-sm"} text-slate-600`}>at {card.venueName}</p>
                </div>
                <span className={`${isRail ? "px-2.5 py-0.5 text-[10px] tracking-[0.18em]" : "px-3 py-1 text-xs tracking-[0.2em]"} rounded-full bg-white font-semibold uppercase text-accent`}>
                  {card.scoreBand}
                </span>
              </div>

              <div className={`${isRail ? "mt-2.5 gap-2 text-xs" : "mt-4 gap-3 text-sm"} flex flex-wrap items-center text-slate-600`}>
                <span>{formatEventStart(card.startsAt, timezone)}</span>
                <span>{card.priceLabel}</span>
                {!isRail ? (
                  <span className="inline-flex items-center gap-1">
                    <MapPin className="h-4 w-4" />
                    {card.address}
                  </span>
                ) : null}
              </div>

              <div className="mt-4 flex flex-wrap gap-2 text-xs font-medium text-slate-600">
                <span className="rounded-full border border-stroke/80 bg-white px-3 py-1">
                  {card.provenance.sourceName}
                </span>
                <span className="rounded-full border border-stroke/80 bg-white px-3 py-1">
                  {card.provenance.sourceConfidenceLabel}
                </span>
                {!isRail ? (
                  <span className="rounded-full border border-stroke/80 bg-white px-3 py-1">
                    {card.freshness.freshnessLabel}
                    {card.freshness.lastVerifiedAt ? ` · ${formatRelativeTimestamp(card.freshness.lastVerifiedAt)}` : ""}
                  </span>
                ) : null}
              </div>

              {!isRail && card.scoreSummary ? (
                <p className="mt-4 text-sm leading-6 text-slate-700">{card.scoreSummary}</p>
              ) : null}

              {!isRail && (movementLabel || movementCues.length) ? (
                <div className="mt-3 flex flex-wrap gap-2 text-xs font-medium">
                  {movementLabel ? (
                    <span
                      className={[
                        "rounded-full border px-3 py-1",
                        comparison?.movement === "down"
                          ? "border-amber-200 bg-amber-50 text-amber-800"
                          : "border-sky-200 bg-sky-50 text-sky-800"
                      ].join(" ")}
                    >
                      {movementLabel}
                    </span>
                  ) : null}
                  {movementCues.slice(0, 3).map((cue) => (
                    <span
                      key={`${card.venueId}-movement-${cue.key}`}
                      className={[
                        "rounded-full border px-3 py-1",
                        cue.direction === "negative"
                          ? "border-amber-200 bg-amber-50 text-amber-800"
                          : "border-sky-200 bg-sky-50 text-sky-800"
                      ].join(" ")}
                      title={`Contribution delta ${cue.delta > 0 ? "+" : ""}${cue.delta.toFixed(3)}`}
                    >
                      {cue.label} {cue.direction === "positive" ? "\u2191" : "\u2193"}
                    </span>
                  ))}
                </div>
              ) : null}

              {!isRail && card.scoreBreakdown.length ? (
                <div className="mt-3 flex flex-wrap gap-2 text-xs font-medium">
                  {card.scoreBreakdown.slice(0, breakdownPreviewCount).map((item) => (
                    <span
                      key={`${card.venueId}-${item.key}`}
                      className={[
                        "rounded-full border px-3 py-1",
                        item.direction === "negative"
                          ? "border-amber-200 bg-amber-50 text-amber-800"
                          : "border-stroke/80 bg-white text-slate-700"
                      ].join(" ")}
                      title={item.detail}
                    >
                      {item.label} · {item.impactLabel}
                    </span>
                  ))}
                </div>
              ) : null}

              {!isRail && card.personalizationProvenance.length ? (
                <div className="mt-3 flex flex-wrap gap-2 text-xs font-medium">
                  {card.personalizationProvenance.slice(0, 4).map((source) => (
                    <span
                      key={`${card.venueId}-${source.sourceProvider}-${source.influence}`}
                      className={[
                        "rounded-full border px-3 py-1",
                        source.influence === "suppressed" || source.influence === "reducing"
                          ? "border-amber-200 bg-amber-50 text-amber-800"
                          : "border-emerald-200 bg-emerald-50 text-emerald-700",
                      ].join(" ")}
                      title={source.detail ?? undefined}
                    >
                      {personalizationSourceLabel(source)}
                    </span>
                  ))}
                </div>
              ) : null}

              {!isRail ? (
                <div className="mt-4 space-y-2">
                  {card.reasons.filter((reason) => reason.title !== "Travel fit").map((reason) => (
                    <div key={reason.title} className="rounded-2xl bg-white/70 px-3 py-2 text-sm text-slate-700">
                      <span className="font-semibold">{reason.title}:</span> {reason.detail}
                    </div>
                  ))}
                </div>
              ) : null}

              {!isRail ? (
                <div className="mt-4 flex flex-wrap gap-2 text-sm text-slate-600">
                  {card.travel.map((travel) => (
                    <span key={`${card.venueId}-${travel.mode}`} className="rounded-full bg-white px-3 py-1">
                      {travel.label}
                    </span>
                  ))}
                </div>
              ) : null}

              <div className="mt-4 flex flex-wrap gap-2">
                {eventUrl ? (
                  <a
                    href={eventUrl}
                    target="_blank"
                    rel="noreferrer"
                    onClick={(event) => {
                      event.stopPropagation();
                      onTrackInteraction?.(card.eventId, "ticket_click");
                    }}
                    className="inline-flex items-center justify-center gap-2 rounded-full border border-stroke bg-white px-4 py-2 text-sm font-medium text-slate-700"
                  >
                    Open event
                  </a>
                ) : null}
                <button
                  type="button"
                  onClick={(event) => {
                    event.stopPropagation();
                    onSave(card);
                  }}
                  className="inline-flex flex-1 items-center justify-center gap-2 rounded-full bg-accent px-4 py-2 text-sm font-medium text-white"
                >
                  <Bookmark className="h-4 w-4" />
                  Save
                </button>
                <button
                  type="button"
                  onClick={(event) => {
                    event.stopPropagation();
                    onDismiss(card);
                  }}
                  className="inline-flex items-center justify-center gap-2 rounded-full border border-stroke bg-white px-4 py-2 text-sm font-medium text-slate-700"
                  title="Hide from this run"
                  aria-label={`Hide ${card.venueName} from this run`}
                >
                  <XCircle className="h-4 w-4" />
                  Hide
                </button>
              </div>

              {card.secondaryEvents.length ? (
                <div className="mt-4 rounded-2xl border border-stroke/80 bg-white/70 p-3 text-sm text-slate-600">
                  <p className="font-semibold text-slate-800">Also upcoming at {card.venueName}</p>
                  <div className="mt-2 space-y-1">
                    {card.secondaryEvents.map((event) => (
                      <div key={event.eventId} className="flex items-center justify-between gap-2">
                        <span>{event.title}</span>
                        <MoveRight className="h-4 w-4 shrink-0 text-slate-400" />
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
            </article>
          );
        })}
      </div>

      {canShowAll ? (
        <button
          type="button"
          onClick={onToggleExpanded}
          className="mt-4 inline-flex self-start rounded-full border border-stroke bg-white/75 px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-white"
        >
          Show all ({orderedCards.length}) &rarr;
        </button>
      ) : null}
    </aside>
  );
}
