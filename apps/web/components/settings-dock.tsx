"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { DigestSettingsCard } from "@/components/digest-settings-card";
import { LocationOnboardingCard } from "@/components/location-onboarding-card";
import { TopbarSheet } from "@/components/topbar-sheet";

export function SettingsDock({ showDigest = false }: { showDigest?: boolean }) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="inline-flex h-11 items-center gap-2 rounded-full border border-stroke bg-white/70 px-4 py-2 text-left text-sm font-medium text-slate-700 transition hover:bg-white"
      >
        <span className="text-sm font-medium text-slate-900">Settings</span>
        {open ? <ChevronUp className="h-4 w-4 text-slate-400" /> : <ChevronDown className="h-4 w-4 text-slate-400" />}
      </button>

      <TopbarSheet open={open} onClose={() => setOpen(false)} title="Settings" eyebrow="Map context" widthClass="max-w-[30rem]">
        <p className="text-sm leading-6 text-slate-600">Adjust location and weekly delivery without pulling setup into the main map view.</p>
        <div className="mt-4 grid gap-4">
            <LocationOnboardingCard compact />
            {showDigest ? <DigestSettingsCard compact /> : null}
        </div>
      </TopbarSheet>
    </>
  );
}
