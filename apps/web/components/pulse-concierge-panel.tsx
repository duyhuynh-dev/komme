"use client";

import { Compass, Sparkles, Wand2 } from "lucide-react";
import { useMemo, useState } from "react";
import { parseConciergeIntent } from "@/lib/pulse-concierge";
import type { ThemeCatalogItem } from "@/lib/types";

const QUICK_INTENTS = [
  {
    id: "dance_after_dark",
    label: "Dance after dark",
    prompt: "late dance night with a strong main event",
    themeIds: ["underground_dance", "late_night_food"],
  },
  {
    id: "date_with_music",
    label: "Date with music",
    prompt: "intimate live music and a low-friction second stop",
    themeIds: ["jazz_intimate_shows", "indie_live_music"],
  },
  {
    id: "cheap_low_key",
    label: "Cheap + low-key",
    prompt: "affordable casual night with food or a local bar",
    themeIds: ["dive_bar_scene", "late_night_food"],
  },
  {
    id: "art_then_drinks",
    label: "Art then drinks",
    prompt: "gallery opening followed by a social stop nearby",
    themeIds: ["gallery_nights", "dive_bar_scene"],
  },
];

export function PulseConciergePanel({
  themes,
  isLoading,
  isSubmitting,
  onSubmit,
}: {
  themes: ThemeCatalogItem[];
  isLoading: boolean;
  isSubmitting: boolean;
  onSubmit: (payload: { prompt: string; themeIds: string[]; labels: string[] }) => void;
}) {
  const [prompt, setPrompt] = useState("");
  const [activeQuickIntentIds, setActiveQuickIntentIds] = useState<string[]>([]);
  const quickThemeIds = activeQuickIntentIds.flatMap((id) => {
    const intent = QUICK_INTENTS.find((item) => item.id === id);
    return intent?.themeIds ?? [];
  });
  const result = useMemo(
    () => parseConciergeIntent(prompt, themes, quickThemeIds),
    [prompt, quickThemeIds.join("|"), themes],
  );
  const canSubmit = result.selectedThemeIds.length > 0 && !isLoading && !isSubmitting;

  return (
    <section className="relative overflow-hidden rounded-[1.55rem] border border-teal-900/10 bg-[linear-gradient(135deg,rgba(15,118,110,0.12),rgba(255,255,255,0.82)_42%,rgba(245,158,11,0.11))] p-3 shadow-float backdrop-blur">
      <div className="pointer-events-none absolute -right-16 -top-20 h-40 w-40 rounded-full bg-teal-300/20 blur-3xl" />
      <div className="pointer-events-none absolute -bottom-24 left-1/3 h-36 w-36 rounded-full bg-amber-300/20 blur-3xl" />
      <div className="relative grid gap-3 xl:grid-cols-[minmax(0,1fr)_auto] xl:items-end">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-teal-200 bg-white/75 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-teal-900">
              <Sparkles className="h-3 w-3" />
              Komme Concierge
            </span>
            <span className="rounded-full border border-stroke/70 bg-white/65 px-2.5 py-1 text-[11px] font-medium text-slate-600">
              Steers map + planner
            </span>
          </div>
          <h2 className="mt-2.5 text-xl font-semibold tracking-tight text-slate-950 md:text-2xl">
            Tell Komme the night you want.
          </h2>
          <p className="mt-1.5 max-w-2xl text-[13px] leading-5 text-slate-600">
            Type a vibe. Komme re-ranks the map and planner.
          </p>

          <div className="mt-3 grid gap-2.5 lg:grid-cols-[minmax(0,1fr)_auto]">
            <label className="sr-only" htmlFor="pulse-concierge-prompt">
              Night plan prompt
            </label>
            <input
              id="pulse-concierge-prompt"
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              placeholder="Example: cheap late techno night in Brooklyn"
              className="min-h-10 rounded-full border border-stroke bg-white/85 px-3.5 text-[13px] font-medium text-slate-800 shadow-sm outline-none transition placeholder:text-slate-400 focus:border-teal-400"
            />
            <button
              type="button"
              disabled={!canSubmit}
              onClick={() => {
                onSubmit({
                  prompt,
                  themeIds: result.selectedThemeIds,
                  labels: result.matchedLabels,
                });
              }}
              className="inline-flex min-h-10 items-center justify-center gap-1.5 rounded-full bg-slate-950 px-4 text-[13px] font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Wand2 className="h-3.5 w-3.5" />
              {isSubmitting ? "Planning..." : "Plan this"}
            </button>
          </div>

          <div className="mt-2.5 flex flex-wrap gap-1.5">
            {QUICK_INTENTS.map((intent) => {
              const active = activeQuickIntentIds.includes(intent.id);
              return (
                <button
                  key={intent.id}
                  type="button"
                  onClick={() => {
                    setActiveQuickIntentIds((current) =>
                      active ? current.filter((id) => id !== intent.id) : [...current, intent.id],
                    );
                    if (!prompt) {
                      setPrompt(intent.prompt);
                    }
                  }}
                  className={[
                    "rounded-full border px-2.5 py-1 text-[11px] font-semibold transition",
                    active
                      ? "border-teal-300 bg-teal-700 text-white"
                      : "border-stroke bg-white/70 text-slate-700 hover:bg-white",
                  ].join(" ")}
                >
                  {intent.label}
                </button>
              );
            })}
          </div>
        </div>

        <div className="relative rounded-[1.15rem] border border-white/70 bg-white/70 p-2.5 xl:w-72">
          <div className="flex items-start gap-2">
            <Compass className="mt-0.5 h-3.5 w-3.5 shrink-0 text-teal-700" />
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                {result.confidence === "fallback" ? "Need a signal" : "Ready to steer"}
              </p>
              <p className="mt-1 text-[13px] leading-5 text-slate-700">{result.summary}</p>
            </div>
          </div>
          {result.matchedLabels.length ? (
            <div className="mt-2.5 flex flex-wrap gap-1.5">
              {result.matchedLabels.slice(0, 4).map((label) => (
                <span
                  key={label}
                  className="rounded-full border border-teal-100 bg-teal-50 px-2 py-0.5 text-[10px] font-semibold text-teal-900"
                >
                  {label}
                </span>
              ))}
            </div>
          ) : null}
        </div>
      </div>
    </section>
  );
}
