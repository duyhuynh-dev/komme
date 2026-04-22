"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { MapPinned, Sparkles, Compass, CalendarDays } from "lucide-react";
import {
  getInterests,
  getMapRecommendations,
  patchInterests,
  submitFeedback
} from "@/lib/api";
import type { InterestTopic, VenueRecommendationCard } from "@/lib/types";
import { MagicLinkCard } from "@/components/sign-in-card";
import { LocationOnboardingCard } from "@/components/location-onboarding-card";
import { RecommendationDrawer } from "@/components/recommendation-drawer";
import { PulseMap } from "@/components/pulse-map";

export function PulseShell() {
  const queryClient = useQueryClient();
  const [selectedVenueId, setSelectedVenueId] = useState<string | null>(null);

  const mapQuery = useQuery({
    queryKey: ["map-recommendations"],
    queryFn: getMapRecommendations
  });

  const interestsQuery = useQuery({
    queryKey: ["interests"],
    queryFn: getInterests
  });

  const toggleTopicMutation = useMutation({
    mutationFn: (topics: InterestTopic[]) => patchInterests(topics),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["interests"] });
      void queryClient.invalidateQueries({ queryKey: ["map-recommendations"] });
    }
  });

  const feedbackMutation = useMutation({
    mutationFn: ({
      recommendationId,
      action
    }: {
      recommendationId: string;
      action: "save" | "dismiss";
    }) => submitFeedback(recommendationId, action, []),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["map-recommendations"] });
      void queryClient.invalidateQueries({ queryKey: ["archive"] });
    }
  });

  const selectedCard: VenueRecommendationCard | null = useMemo(() => {
    if (!mapQuery.data) {
      return null;
    }

    const initialVenueId = mapQuery.data.pins.at(0)?.venueId ?? null;
    const activeVenueId = selectedVenueId ?? initialVenueId;
    if (!activeVenueId) {
      return null;
    }

    return mapQuery.data.cards[activeVenueId] ?? null;
  }, [mapQuery.data, selectedVenueId]);

  const toggleTopic = (topic: InterestTopic) => {
    const topics = (interestsQuery.data?.topics ?? []).map((current) => {
      if (current.id !== topic.id) {
        return current;
      }

      return {
        ...current,
        muted: !current.muted
      };
    });

    toggleTopicMutation.mutate(topics);
  };

  return (
    <main className="min-h-screen px-4 py-4 md:px-6 md:py-6">
      <div className="mx-auto flex max-w-[1600px] flex-col gap-4">
        <section className="grid gap-4 lg:grid-cols-[1.1fr_1.6fr]">
          <div className="rounded-[2rem] border border-stroke/80 bg-card/80 p-6 shadow-float backdrop-blur">
            <div className="flex items-start justify-between gap-4">
              <div>
                <span className="inline-flex rounded-full bg-accentSoft px-3 py-1 text-xs font-semibold uppercase tracking-[0.22em] text-accent">
                  Private Beta
                </span>
                <h1 className="mt-4 text-4xl font-semibold tracking-tight md:text-5xl">
                  Your Reddit taste, turned into a city map.
                </h1>
                <p className="mt-4 max-w-2xl text-sm leading-6 text-slate-600 md:text-base">
                  Pulse ranks NYC venues by how well their upcoming events match your current interests, then
                  highlights the best places directly on the map.
                </p>
              </div>
              <Link
                href="/archive"
                className="hidden rounded-full border border-stroke bg-white/70 px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-white lg:inline-flex"
              >
                Weekly archive
              </Link>
            </div>

            <div className="mt-6 grid gap-3 sm:grid-cols-3">
              <StatCard icon={MapPinned} label="Map-first picks" value="3-5 primary spots" />
              <StatCard icon={Compass} label="Travel aware" value="Approx walk + transit" />
              <StatCard icon={CalendarDays} label="Weekly cadence" value="Tuesday 9 AM digest" />
            </div>

            <div className="mt-6 grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
              <LocationOnboardingCard />
              <MagicLinkCard />
            </div>
          </div>

          <div className="rounded-[2rem] border border-stroke/80 bg-card/70 p-6 shadow-float backdrop-blur">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium uppercase tracking-[0.22em] text-accent">Interest profile</p>
                <h2 className="mt-2 text-2xl font-semibold">Editable signals, not a black box</h2>
              </div>
              <Sparkles className="h-5 w-5 text-accent" />
            </div>

            <div className="mt-4 flex flex-wrap gap-2">
              {(interestsQuery.data?.topics ?? []).map((topic) => (
                <button
                  key={topic.id}
                  type="button"
                  onClick={() => toggleTopic(topic)}
                  className={[
                    "rounded-full border px-4 py-2 text-sm transition",
                    topic.muted
                      ? "border-stroke bg-slate-100 text-slate-400"
                      : "border-accent/25 bg-accentSoft text-accent"
                  ].join(" ")}
                >
                  {topic.label}
                </button>
              ))}

              {!interestsQuery.data?.topics.length && (
                <p className="text-sm text-slate-500">
                  Connect Reddit to see inferred themes like underground dance, indie gigs, gallery nights, and meetups.
                </p>
              )}
            </div>
          </div>
        </section>

        <section className="grid gap-4 xl:grid-cols-[1.45fr_0.55fr]">
          <div className="map-surface overflow-hidden rounded-[2rem] border border-stroke/80 shadow-float">
            <div className="flex items-center justify-between border-b border-stroke/70 px-5 py-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">Map View</p>
                <h2 className="mt-1 text-2xl font-semibold">Recommended venues across NYC</h2>
              </div>
              <Link href="/archive" className="rounded-full border border-stroke px-4 py-2 text-sm text-slate-700 lg:hidden">
                Archive
              </Link>
            </div>

            <PulseMap
              pins={mapQuery.data?.pins ?? []}
              viewport={mapQuery.data?.viewport ?? null}
              selectedVenueId={selectedCard?.venueId ?? null}
              onSelectVenue={setSelectedVenueId}
            />
          </div>

          <RecommendationDrawer
            loading={mapQuery.isLoading}
            cards={mapQuery.data?.cards ?? {}}
            selectedVenueId={selectedCard?.venueId ?? null}
            onSelectVenue={setSelectedVenueId}
            onSave={(card) =>
              feedbackMutation.mutate({ recommendationId: card.eventId, action: "save" })
            }
            onDismiss={(card) =>
              feedbackMutation.mutate({ recommendationId: card.eventId, action: "dismiss" })
            }
          />
        </section>
      </div>
    </main>
  );
}

function StatCard({
  icon: Icon,
  label,
  value
}: {
  icon: typeof MapPinned;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-3xl border border-stroke bg-white/70 p-4">
      <Icon className="h-5 w-5 text-accent" />
      <p className="mt-3 text-xs uppercase tracking-[0.2em] text-slate-500">{label}</p>
      <p className="mt-1 text-sm font-semibold text-slate-800">{value}</p>
    </div>
  );
}

