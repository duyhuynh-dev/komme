"use client";

import { Sparkles } from "lucide-react";
import type { InterestTopic } from "@/lib/types";

type InterestAction = "boost" | "mute" | "reset";

interface InterestProfilePanelProps {
  topics: InterestTopic[];
  isLoading: boolean;
  isSaving: boolean;
  onAction: (topicId: string, action: InterestAction) => void;
  mode?: "rail" | "modal";
  previewCount?: number;
  isExpanded?: boolean;
  onToggleExpanded?: () => void;
}

export function InterestProfilePanel({
  topics,
  isLoading,
  isSaving,
  onAction,
  mode = "rail",
  previewCount = 2,
  isExpanded = false,
  onToggleExpanded,
}: InterestProfilePanelProps) {
  const isRail = mode === "rail";
  const visibleTopics = mode === "rail" ? topics.slice(0, previewCount) : topics;
  const canShowAll = mode === "rail" && topics.length > visibleTopics.length;

  return (
    <div
      className={[
        "flex min-h-0 flex-col",
        isRail
          ? "max-h-[16.25rem] min-h-[11.25rem] shrink-0 overflow-hidden rounded-[1.6rem] border border-stroke/80 bg-card/70 p-4 shadow-float backdrop-blur"
          : ""
      ].join(" ")}
    >
      <div className="flex items-start justify-between gap-2.5">
        <button
          type="button"
          onClick={isRail ? onToggleExpanded : undefined}
          className={[
            "min-w-0 text-left",
            isRail ? "transition hover:opacity-80" : ""
          ].join(" ")}
          aria-expanded={isRail ? isExpanded : undefined}
        >
          <h2 className={`${isRail ? "text-lg" : "text-xl"} font-semibold text-slate-900`}>Interest signals</h2>
          <p className={`${isRail ? "mt-0.5 text-[13px] leading-5" : "mt-1 text-sm"} text-slate-500`}>
            Boost or mute a theme, then watch the map and shortlist respond around that edit.
          </p>
        </button>
        <button
          type="button"
          title="More signal sources are coming soon."
          className={[
            "inline-flex items-center gap-2 whitespace-nowrap rounded-full border border-stroke bg-white/70 font-medium text-slate-600 transition hover:bg-white",
            isRail ? "px-2.5 py-1.5 text-[13px]" : "px-3 py-2 text-sm"
          ].join(" ")}
        >
          <Sparkles className={isRail ? "h-3.5 w-3.5" : "h-4 w-4"} />
          Add signal
        </button>
      </div>

      <div
        className={[
          "pr-1",
          isRail ? "mt-3 min-h-0 flex-1 space-y-2 overflow-y-auto" : "mt-5 space-y-4"
        ].join(" ")}
      >
        {isLoading ? (
          <div className={`${isRail ? "rounded-[1.35rem] p-4 text-[13px]" : "rounded-3xl p-5 text-sm"} border border-dashed border-stroke bg-white/50 text-slate-500`}>
            Loading inferred interests...
          </div>
        ) : null}

        {!isLoading && topics.length === 0 ? (
          <div className={`${isRail ? "rounded-[1.35rem] p-4 text-[13px] leading-5" : "rounded-3xl p-5 text-sm leading-6"} border border-dashed border-stroke bg-white/50 text-slate-500`}>
            Connect Reddit or load the sample profile to see inferred themes like underground dance, indie gigs,
            gallery nights, and creative meetups.
          </div>
        ) : null}

        {visibleTopics.map((topic) => {
          const confidencePercent = Math.round(topic.confidence * 100);
          return (
            <article
              key={topic.id}
              className={[
                "border bg-white/75 transition",
                isRail ? "rounded-[1.35rem] p-3" : "rounded-3xl p-4",
                topic.muted
                  ? "border-slate-200 shadow-[inset_3px_0_0_0_rgba(100,116,139,0.4)]"
                  : topic.boosted
                    ? "border-accent/35 shadow-[inset_3px_0_0_0_rgba(15,118,110,0.72)]"
                    : "border-stroke"
              ].join(" ")}
            >
              <div className="flex flex-wrap items-start justify-between gap-2.5">
                <div>
                  <div className="flex items-center gap-2">
                    {(topic.boosted || topic.muted) ? (
                      <span
                        className={[
                          "h-2.5 w-2.5 rounded-full",
                          topic.boosted ? "bg-accent" : "bg-slate-400"
                        ].join(" ")}
                      />
                    ) : null}
                    <h3 className={`${isRail ? "text-[15px]" : "text-base"} font-semibold text-slate-900`}>{topic.label}</h3>
                  </div>
                  <p className={`${isRail ? "mt-1.5 text-[13px]" : "mt-2 text-sm"} text-slate-500`}>
                    Confidence {confidencePercent}% from observed signals.
                  </p>
                </div>

                <div className={`${isRail ? "gap-1.5" : "gap-2"} flex flex-wrap`}>
                  <ActionButton
                    label="Boost"
                    active={topic.boosted}
                    disabled={isSaving}
                    compact={isRail}
                    title="Lift venues that match this theme higher in the ranking."
                    onClick={() => onAction(topic.id, "boost")}
                  />
                  <ActionButton
                    label="Mute"
                    active={topic.muted}
                    disabled={isSaving}
                    compact={isRail}
                    tone="muted"
                    title="Downrank venues that match this theme."
                    onClick={() => onAction(topic.id, "mute")}
                  />
                  <ActionButton
                    label="Reset"
                    active={false}
                    disabled={isSaving || (!topic.boosted && !topic.muted)}
                    compact={isRail}
                    tone="ghost"
                    title="Clear your manual override for this theme."
                    onClick={() => onAction(topic.id, "reset")}
                  />
                </div>
              </div>

              <div className={`${isRail ? "mt-3 h-1.5" : "mt-4 h-2"} overflow-hidden rounded-full bg-slate-100`}>
                <div
                  className={[
                    "h-full rounded-full transition-all",
                    topic.muted ? "bg-slate-300" : topic.boosted ? "bg-accent" : "bg-slate-700"
                  ].join(" ")}
                  style={{ width: `${confidencePercent}%` }}
                />
              </div>

              <div className={`${isRail ? "mt-3 gap-1.5" : "mt-4 gap-2"} flex flex-wrap`}>
                {topic.sourceSignals.map((signal) => (
                  <span
                    key={signal}
                    className={`${isRail ? "px-2.5 py-0.5 text-[11px]" : "px-3 py-1 text-xs"} rounded-full border border-stroke bg-slate-50 text-slate-600`}
                  >
                    {signal}
                  </span>
                ))}
              </div>
            </article>
          );
        })}
      </div>

      {canShowAll ? (
        <button
          type="button"
          onClick={onToggleExpanded}
          className="mt-3 inline-flex self-start rounded-full border border-stroke bg-white/75 px-3 py-1.5 text-[13px] font-medium text-slate-700 transition hover:bg-white"
        >
          Show all ({topics.length}) &rarr;
        </button>
      ) : null}
    </div>
  );
}

function ActionButton({
  label,
  active,
  disabled,
  onClick,
  compact = false,
  tone = "accent",
  title,
}: {
  label: string;
  active: boolean;
  disabled: boolean;
  onClick: () => void;
  compact?: boolean;
  tone?: "accent" | "muted" | "ghost";
  title: string;
}) {
  const className =
    tone === "muted"
      ? active
        ? "border-slate-300 bg-slate-900 text-white"
        : "border-stroke bg-white text-slate-700"
      : tone === "ghost"
        ? "border-stroke bg-transparent text-slate-500 disabled:border-stroke/50 disabled:text-slate-300"
        : active
          ? "border-accent bg-accent text-white"
          : "border-accent/20 bg-accentSoft text-accent";

  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      title={title}
      className={`rounded-full border font-medium transition disabled:cursor-not-allowed disabled:opacity-60 ${compact ? "px-2.5 py-1.5 text-[13px]" : "px-3 py-2 text-sm"} ${className}`}
    >
      {label}
    </button>
  );
}
