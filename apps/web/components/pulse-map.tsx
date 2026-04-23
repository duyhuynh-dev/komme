"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { LngLatBoundsLike, Map as MapLibreMap, Marker as MapLibreMarker, StyleSpecification } from "maplibre-gl";
import type { MapVenuePin, MapViewport } from "@/lib/types";

type MapLibreModule = typeof import("maplibre-gl");
type MapMode = "loading" | "ready" | "error";

const NYC_DEFAULT_VIEWPORT: MapViewport = {
  latitude: 40.73061,
  longitude: -73.935242,
  latitudeDelta: 0.22,
  longitudeDelta: 0.22
};

const OPEN_STREET_MAP_STYLE: StyleSpecification = {
  version: 8,
  sources: {
    "openstreetmap-tiles": {
      type: "raster",
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      attribution: "&copy; OpenStreetMap contributors"
    }
  },
  layers: [
    {
      id: "openstreetmap-layer",
      type: "raster",
      source: "openstreetmap-tiles"
    }
  ]
};

function zoomFromViewport(viewport: MapViewport) {
  const normalizedLongitudeDelta = Math.max(viewport.longitudeDelta, 0.015);
  return Math.min(15.5, Math.max(10.25, Math.log2(360 / normalizedLongitudeDelta)));
}

function createMarkerElement(pin: MapVenuePin, selectedVenueId: string | null, onSelectVenue: (venueId: string) => void) {
  const markerElement = document.createElement("button");
  markerElement.type = "button";
  markerElement.className = [
    "pulse-map-marker",
    `band-${pin.scoreBand}`,
    pin.venueId === selectedVenueId ? "is-selected" : ""
  ]
    .filter(Boolean)
    .join(" ");
  markerElement.setAttribute("aria-label", `Select ${pin.venueName}`);
  const dotElement = document.createElement("span");
  dotElement.className = "pulse-map-marker__dot";
  dotElement.setAttribute("aria-hidden", "true");

  const labelElement = document.createElement("span");
  labelElement.className = "pulse-map-marker__label";
  labelElement.textContent = pin.venueName;

  markerElement.append(dotElement, labelElement);
  markerElement.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    onSelectVenue(pin.venueId);
  });
  return markerElement;
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
  const maplibreRef = useRef<MapLibreModule | null>(null);
  const mapInstanceRef = useRef<MapLibreMap | null>(null);
  const markersRef = useRef<MapLibreMarker[]>([]);
  const [mode, setMode] = useState<MapMode>("loading");
  const [error, setError] = useState<string | null>(null);

  const resolvedViewport = useMemo<MapViewport>(
    () => viewport ?? NYC_DEFAULT_VIEWPORT,
    [viewport],
  );

  useEffect(() => {
    let cancelled = false;

    async function setupMap() {
      if (!mapRef.current || mapInstanceRef.current || typeof window === "undefined") {
        return;
      }

      try {
        const maplibregl = await import("maplibre-gl");

        if (cancelled || !mapRef.current) {
          return;
        }

        maplibreRef.current = maplibregl;
        const map = new maplibregl.Map({
          container: mapRef.current,
          style: OPEN_STREET_MAP_STYLE,
          center: [NYC_DEFAULT_VIEWPORT.longitude, NYC_DEFAULT_VIEWPORT.latitude],
          zoom: zoomFromViewport(NYC_DEFAULT_VIEWPORT),
          attributionControl: { compact: true },
          dragRotate: false
        });

        map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "bottom-right");
        map.touchZoomRotate.disableRotation();
        map.on("load", () => {
          if (!cancelled) {
            setMode("ready");
          }
        });

        mapInstanceRef.current = map;
      } catch (mapError) {
        if (!cancelled) {
          setMode("error");
          setError(mapError instanceof Error ? mapError.message : "Unable to initialize the map.");
        }
      }
    }

    void setupMap();

    return () => {
      cancelled = true;
      markersRef.current.forEach((marker) => marker.remove());
      markersRef.current = [];
      mapInstanceRef.current?.remove();
      mapInstanceRef.current = null;
      maplibreRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapInstanceRef.current;
    const maplibregl = maplibreRef.current;
    if (!map || !maplibregl) {
      return;
    }

    if (!pins.length) {
      map.easeTo({
        center: [resolvedViewport.longitude, resolvedViewport.latitude],
        zoom: zoomFromViewport(resolvedViewport),
        duration: 900
      });
      return;
    }

    if (pins.length === 1) {
      map.easeTo({
        center: [pins[0].longitude, pins[0].latitude],
        zoom: Math.max(13.4, zoomFromViewport(resolvedViewport)),
        duration: 900
      });
      return;
    }

    const bounds = pins.reduce(
      (currentBounds, pin) => currentBounds.extend([pin.longitude, pin.latitude]),
      new maplibregl.LngLatBounds(
        [pins[0].longitude, pins[0].latitude],
        [pins[0].longitude, pins[0].latitude]
      ),
    );

    map.fitBounds(bounds as LngLatBoundsLike, {
      padding: {
        top: 112,
        right: 36,
        bottom: 36,
        left: 36
      },
      duration: 900,
      maxZoom: 13.8
    });
  }, [pins, resolvedViewport]);

  useEffect(() => {
    const map = mapInstanceRef.current;
    const maplibregl = maplibreRef.current;
    if (!map || !maplibregl) {
      return;
    }

    markersRef.current.forEach((marker) => marker.remove());

    const markers = pins.map((pin) => {
      const markerElement = createMarkerElement(pin, selectedVenueId, onSelectVenue);
      return new maplibregl.Marker({
        element: markerElement,
        anchor: "bottom"
      })
        .setLngLat([pin.longitude, pin.latitude])
        .addTo(map);
    });

    markersRef.current = markers;
    return () => {
      markers.forEach((marker) => marker.remove());
    };
  }, [onSelectVenue, pins, selectedVenueId]);

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
    <div className="relative h-[62vh] min-h-[420px] w-full overflow-hidden bg-[radial-gradient(circle_at_top,#f7efe0,transparent_35%),linear-gradient(135deg,#f4ede2,#e8f4f1)]">
      <div className="pointer-events-none absolute inset-x-0 top-0 z-10 flex items-center justify-between gap-4 border-b border-stroke/70 bg-white/78 px-5 py-4 backdrop-blur">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">Interactive Map</p>
          <p className="mt-1 text-sm text-slate-600">
            Live venue pins powered by MapLibre and OpenStreetMap, centered around your current shortlist.
          </p>
        </div>
        <span className="hidden rounded-full bg-white/85 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-accent md:inline-flex">
          MapLibre + OSM
        </span>
      </div>
      {mode === "loading" ? (
        <div className="absolute inset-0 z-10 flex items-center justify-center bg-white/80 text-sm text-slate-500">
          Loading live map...
        </div>
      ) : null}
      <div ref={mapRef} className="h-full w-full" />
    </div>
  );
}
