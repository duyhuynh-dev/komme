"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { getArchive } from "@/lib/api";

export function ArchivePageContent() {
  const archiveQuery = useQuery({
    queryKey: ["archive"],
    queryFn: getArchive
  });

  return (
    <main className="min-h-screen px-4 py-6 md:px-6">
      <div className="mx-auto max-w-5xl rounded-[2rem] border border-stroke/80 bg-card/80 p-6 shadow-float">
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">Archive</p>
            <h1 className="mt-2 text-4xl font-semibold tracking-tight">Weekly venue picks</h1>
          </div>
          <Link href="/" className="rounded-full border border-stroke px-4 py-2 text-sm text-slate-700">
            Back to map
          </Link>
        </div>

        <div className="mt-6 grid gap-3">
          {archiveQuery.data?.items.map((item) => (
            <article key={`${item.venueId}-${item.eventId}`} className="rounded-[1.75rem] border border-stroke bg-white/80 p-5">
              <p className="text-xs uppercase tracking-[0.22em] text-slate-500">{item.neighborhood}</p>
              <h2 className="mt-2 text-2xl font-semibold">{item.venueName}</h2>
              <p className="mt-1 text-slate-700">{item.eventTitle}</p>
              <div className="mt-3 flex flex-wrap gap-2 text-sm text-slate-600">
                <span>{new Date(item.startsAt).toLocaleString()}</span>
                <span>{item.priceLabel}</span>
                {item.travel.map((travel) => (
                  <span key={`${item.eventId}-${travel.mode}`} className="rounded-full bg-canvas px-3 py-1">
                    {travel.label}
                  </span>
                ))}
              </div>
            </article>
          ))}

          {!archiveQuery.data?.items.length && (
            <div className="rounded-[1.75rem] border border-dashed border-stroke bg-white/70 p-5 text-sm text-slate-500">
              The archive will fill in after the first recommendation run is generated.
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
