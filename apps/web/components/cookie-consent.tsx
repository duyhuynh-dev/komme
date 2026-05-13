"use client";

import { Cookie, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import type { CookieConsentChoice } from "@/lib/cookie-consent";
import { readCookieConsent, writeCookieConsent } from "@/lib/cookie-consent";

export function CookieConsent() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    setVisible(readCookieConsent() === null);
  }, []);

  if (!visible) {
    return null;
  }

  const choose = (choice: CookieConsentChoice) => {
    writeCookieConsent(choice);
    setVisible(false);
  };

  return (
    <section
      aria-label="Cookie consent"
      aria-live="polite"
      className="fixed inset-x-4 bottom-4 z-[1000] mx-auto max-w-xl rounded-[1.75rem] border border-stroke bg-white/95 p-4 text-ink shadow-[0_24px_70px_rgba(15,23,42,0.16)] backdrop-blur-md sm:bottom-6 sm:left-auto sm:right-6 sm:mx-0"
      role="dialog"
    >
      <div className="flex items-start gap-3">
        <div className="mt-1 grid h-10 w-10 shrink-0 place-items-center rounded-full bg-accent/10 text-accent">
          <Cookie className="h-5 w-5" aria-hidden="true" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 text-xs font-black uppercase tracking-[0.24em] text-muted">
            <ShieldCheck className="h-4 w-4 text-accent" aria-hidden="true" />
            Privacy
          </div>
          <h2 className="mt-2 text-xl font-black tracking-[-0.03em]">Komme uses cookies</h2>
          <p className="mt-2 text-sm leading-6 text-muted">
            We use essential cookies and local storage for sign-in, saved preferences, and safer sessions.
            Accept all lets Komme remember product quality choices too.
          </p>
        </div>
      </div>
      <div className="mt-4 grid gap-2 sm:grid-cols-[1fr_auto_auto] sm:items-center">
        <p className="text-xs font-bold uppercase tracking-[0.18em] text-muted">You can change this later.</p>
        <button
          className="rounded-full border border-stroke px-4 py-2 text-sm font-black text-slate transition hover:border-accent hover:text-accent"
          onClick={() => choose("essential")}
          type="button"
        >
          Essential only
        </button>
        <button
          className="rounded-full bg-accent px-4 py-2 text-sm font-black text-white shadow-soft transition hover:bg-accentDark"
          onClick={() => choose("accepted")}
          type="button"
        >
          Accept all
        </button>
      </div>
    </section>
  );
}
