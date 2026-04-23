"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { load } from "@apple/mapkit-loader";
import { MapPin } from "lucide-react";
import { getMapToken } from "@/lib/api";
import type { MapVenuePin, MapViewport } from "@/lib/types";

type MapKitRuntime = Awaited<ReturnType<typeof load>>;
type MapKitMap = InstanceType<MapKitRuntime["Map"]>;
type MapKitAnnotation = InstanceType<MapKitRuntime["MarkerAnnotation"]>;
type MapMode = "loading" | "apple" | "fallback" | "error";

function buildRegion(mapkit: MapKitRuntime, viewport: MapViewport) {
  const center = new mapkit.Coordinate(viewport.latitude, viewport.longitude);
  const span = new mapkit.CoordinateSpan(viewport.latitudeDelta, viewport.longitudeDelta);
  return new mapkit.CoordinateRegion(center, span);
}

export function PulseMap({
  pins,
  viewport,
  selectedVenueId,
  onSelectVenue
}: {
  pins: MapVenuePin[];
  viewport: MapViewport | null;
  selectedVenueId: string | null;
  onSelectVenue: (venueId: string) => void;
}) {
  const mapRef = useRef<HTMLDivElement | null>(null);
  const mapkitRef = useRef<MapKitRuntime | null>(null);
  const mapInstanceRef = useRef<MapKitMap | null>(null);
  const annotationsRef = useRef<MapKitAnnotation[]>([]);
  const [mode, setMode] = useState<MapMode>("loading");
  const [error, setError] = useState<string | null>(null);

  const resolvedViewport = useMemo<MapViewport>(
    () =>
      viewport ?? {
        latitude: 40.73061,
        longitude: -73.935242,
        latitudeDelta: 0.22,
        longitudeDelta: 0.22
      },
    [viewport],
  );

  useEffect(() => {
    let cancelled = false;

    async function setupMap() {
      if (!mapRef.current || mapInstanceRef.current || typeof window === "undefined") {
        return;
      }

      try {
        const tokenResponse = await getMapToken();
        if (!tokenResponse.enabled || !tokenResponse.token) {
          if (!cancelled) {
            setMode("fallback");
          }
          return;
        }

        const mapkit = await load({
          token: tokenResponse.token,
          libraries: ["map"]
        });

        if (cancelled || !mapRef.current) {
          return;
        }

        mapkitRef.current = mapkit;
        mapkit.init({
          authorizationCallback: (done) => done(tokenResponse.token as string)
        });

        mapInstanceRef.current = new mapkit.Map(mapRef.current, {
          showsCompass: mapkit.FeatureVisibility.Hidden,
          showsZoomControl: false,
          colorScheme: "light",
          isRotationEnabled: false,
          region: buildRegion(mapkit, resolvedViewport)
        });
        setMode("apple");
      } catch (mapError) {
        if (!cancelled) {
          setMode("error");
          setError(mapError instanceof Error ? mapError.message : "Unable to initialize Apple MapKit.");
        }
      }
    }

    void setupMap();

    return () => {
      cancelled = true;
    };
  }, [resolvedViewport]);

  useEffect(() => {
    const mapkit = mapkitRef.current;
    const map = mapInstanceRef.current;
    if (!mapkit || !map) {
      return;
    }

    map.setRegionAnimated(buildRegion(mapkit, resolvedViewport), true);
  }, [resolvedViewport]);

  useEffect(() => {
    const mapkit = mapkitRef.current;
    const map = mapInstanceRef.current;
    if (!mapkit || !map) {
      return;
    }

    if (annotationsRef.current.length) {
      map.removeAnnotations(annotationsRef.current);
    }

    const annotations = pins.map((pin) => {
      const coordinate = new mapkit.Coordinate(pin.latitude, pin.longitude);
      const annotation = new mapkit.MarkerAnnotation(coordinate, {
        color:
          pin.venueId === selectedVenueId
            ? "#0f766e"
            : pin.scoreBand === "high"
              ? "#164e63"
              : pin.scoreBand === "medium"
                ? "#ca8a04"
                : "#6b7280",
        title: pin.venueName,
        glyphText: pin.scoreBand === "high" ? "P" : pin.scoreBand === "medium" ? "M" : "L",
        selected: pin.venueId === selectedVenueId
      });

      annotation.data = { venueId: pin.venueId };
      annotation.addEventListener?.("select", () => onSelectVenue(pin.venueId));

      return annotation;
    });

    annotationsRef.current = annotations;
    map.addAnnotations(annotations);
  }, [onSelectVenue, pins, selectedVenueId]);

  if (mode === "fallback") {
    return (
      <div className="relative h-[62vh] min-h-[420px] w-full overflow-hidden bg-[radial-gradient(circle_at_top,#f7efe0,transparent_35%),linear-gradient(135deg,#f4ede2,#e8f4f1)]">
        <div className="absolute inset-0 bg-[linear-gradient(rgba(15,118,110,0.08)_1px,transparent_1px),linear-gradient(90deg,rgba(15,118,110,0.08)_1px,transparent_1px)] bg-[size:72px_72px]" />
        <div className="absolute inset-x-0 top-0 z-10 flex items-center justify-between gap-4 border-b border-stroke/70 bg-white/75 px-5 py-4 backdrop-blur">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">Map Preview</p>
            <p className="mt-1 text-sm text-slate-600">
              Apple Maps preview is unavailable until `APPLE_MAPS_*` credentials are configured. Venue recommendations are still live.
            </p>
          </div>
        </div>

        <div className="absolute inset-0 px-6 pb-6 pt-28">
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {pins.map((pin) => {
              const selected = pin.venueId === selectedVenueId;
              return (
                <button
                  key={pin.venueId}
                  type="button"
                  onClick={() => onSelectVenue(pin.venueId)}
                  className={[
                    "rounded-[1.5rem] border bg-white/80 p-4 text-left shadow-sm backdrop-blur transition",
                    selected ? "border-accent ring-2 ring-accent/20" : "border-stroke hover:bg-white"
                  ].join(" ")}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="inline-flex items-center gap-2">
                      <span
                        className={[
                          "inline-flex h-9 w-9 items-center justify-center rounded-full text-white",
                          pin.scoreBand === "high"
                            ? "bg-deep"
                            : pin.scoreBand === "medium"
                              ? "bg-amber-500"
                              : "bg-slate-400"
                        ].join(" ")}
                      >
                        <MapPin className="h-4 w-4" />
                      </span>
                      <div>
                        <p className="text-sm font-semibold text-slate-900">{pin.venueName}</p>
                        <p className="text-xs uppercase tracking-[0.18em] text-slate-500">{pin.scoreBand}</p>
                      </div>
                    </div>
                    {selected ? (
                      <span className="rounded-full bg-accentSoft px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-accent">
                        Selected
                      </span>
                    ) : null}
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      </div>
    );
  }

  if (mode === "error") {
    return (
      <div className="relative h-[62vh] min-h-[420px] w-full">
        <div className="absolute inset-0 flex items-center justify-center bg-white/90 p-6 text-center text-sm text-slate-500">
          {error}
        </div>
      </div>
    );
  }

  return (
    <div className="relative h-[62vh] min-h-[420px] w-full">
      {mode === "loading" ? (
        <div className="absolute inset-0 z-10 flex items-center justify-center bg-white/80 text-sm text-slate-500">
          Loading map preview...
        </div>
      ) : null}
      <div ref={mapRef} className="h-full w-full" />
    </div>
  );
}
