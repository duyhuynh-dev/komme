"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { load } from "@apple/mapkit-loader";
import { getMapToken } from "@/lib/api";
import type { MapVenuePin, MapViewport } from "@/lib/types";

type MapKitMap = {
  removeAnnotations: (annotations: unknown[]) => void;
  addAnnotations: (annotations: unknown[]) => void;
  setRegionAnimated: (region: unknown, animated: boolean) => void;
};

function buildRegion(
  mapkit: NonNullable<Window["mapkit"]>,
  viewport: MapViewport,
) {
  const center = new mapkit.Coordinate(viewport.latitude, viewport.longitude);
  const span = new mapkit.CoordinateSpan(viewport.latitudeDelta, viewport.longitudeDelta);
  return new mapkit.CoordinateRegion(center, span);
}

declare global {
  interface Window {
    mapkit?: {
      init: (options: { authorizationCallback: (done: (token: string) => void) => void }) => void;
      Map: new (container: HTMLElement, options: Record<string, unknown>) => MapKitMap;
      Coordinate: new (latitude: number, longitude: number) => unknown;
      CoordinateRegion: new (center: unknown, span: unknown) => unknown;
      CoordinateSpan: new (latitudeDelta: number, longitudeDelta: number) => unknown;
      MarkerAnnotation: new (coordinate: unknown, options: Record<string, unknown>) => unknown;
      mapkitjsVersion: string;
    };
  }
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
  const mapInstanceRef = useRef<MapKitMap | null>(null);
  const annotationsRef = useRef<unknown[]>([]);
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
        const mapkit = await load({
          token: tokenResponse.token,
          libraries: ["map"]
        });

        if (cancelled || !mapRef.current) {
          return;
        }

        mapkit.init({
          authorizationCallback: (done) => done(tokenResponse.token)
        });

        mapInstanceRef.current = new mapkit.Map(mapRef.current, {
          showsCompass: false,
          showsZoomControl: false,
          colorScheme: "light",
          isRotationEnabled: false,
          region: buildRegion(mapkit, resolvedViewport)
        });
      } catch (mapError) {
        setError(mapError instanceof Error ? mapError.message : "Unable to initialize Apple MapKit.");
      }
    }

    void setupMap();

    return () => {
      cancelled = true;
    };
  }, [resolvedViewport]);

  useEffect(() => {
    const mapkit = window.mapkit;
    const map = mapInstanceRef.current;
    if (!mapkit || !map) {
      return;
    }

    map.setRegionAnimated(buildRegion(mapkit, resolvedViewport), true);
  }, [resolvedViewport]);

  useEffect(() => {
    const mapkit = window.mapkit;
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

      (annotation as { data?: Record<string, string> }).data = { venueId: pin.venueId };
      (annotation as { addEventListener?: (eventName: string, handler: () => void) => void }).addEventListener?.(
        "select",
        () => onSelectVenue(pin.venueId),
      );

      return annotation;
    });

    annotationsRef.current = annotations;
    map.addAnnotations(annotations);
  }, [onSelectVenue, pins, selectedVenueId]);

  return (
    <div className="relative h-[62vh] min-h-[420px] w-full">
      {error ? (
        <div className="absolute inset-0 flex items-center justify-center bg-white/90 p-6 text-center text-sm text-slate-500">
          {error}
        </div>
      ) : null}
      <div ref={mapRef} className="h-full w-full" />
    </div>
  );
}
