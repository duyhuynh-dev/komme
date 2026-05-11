import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, Eye, Map, RefreshCw, Route, ShieldCheck, Sparkles, Ticket } from "lucide-react";

export const metadata: Metadata = {
  title: "Komme | Plan better nights in NYC",
  description: "Komme turns real NYC event supply into a personal map and a simple night plan.",
};

const proofPoints = [
  "Live NYC event supply",
  "Personal taste signals",
  "2-3 stop planning",
  "Ticket and source links",
];

const features = [
  {
    icon: Ticket,
    title: "Real events first",
    body: "Komme pulls from ticketing and venue sources, then keeps provenance visible so the shortlist feels trustworthy.",
    label: "Supply",
  },
  {
    icon: Map,
    title: "A map that adapts",
    body: "Your location, budget, feedback, and taste signals shape what rises instead of handing you a generic list.",
    label: "Personalization",
  },
  {
    icon: Route,
    title: "A plan, not a pile",
    body: "The planner sequences a workable night from the shortlist with timing, neighborhood fit, and backups.",
    label: "Planner",
  },
];

const steps = [
  "Choose a vibe or connect Spotify.",
  "Komme ranks real NYC options around your context.",
  "Open a clean route, swap weak stops, and jump to the source link.",
];

const planTitles = ["Brooklyn after dark", "Jazz then drinks", "Cheap dance night", "Date night in LES"];

const trustSignals = [
  {
    icon: Eye,
    title: "Sources stay visible",
    body: "Cards keep ticket/source links and trust context close to the decision.",
  },
  {
    icon: RefreshCw,
    title: "Feedback changes the map",
    body: "Saves, hides, visits, and planner outcomes feed future recommendations.",
  },
  {
    icon: ShieldCheck,
    title: "Taste is controllable",
    body: "Spotify and manual signals can shape ranking without hiding why.",
  },
];

export default function LandingPage() {
  return (
    <main className="landing-page min-h-screen overflow-hidden bg-[#f8f3ea] text-slate-950">
      <section className="relative isolate px-5 py-5 sm:px-8 lg:px-10">
        <div className="landing-ambient absolute inset-0 -z-10 bg-[radial-gradient(circle_at_18%_12%,rgba(15,118,110,0.16),transparent_28%),radial-gradient(circle_at_86%_8%,rgba(245,158,11,0.15),transparent_24%),linear-gradient(180deg,#fffdf8_0%,#f1e7d9_100%)]" />
        <div className="landing-reveal mx-auto flex max-w-7xl items-center justify-between rounded-full border border-stroke/80 bg-white/65 px-4 py-3 shadow-[0_18px_48px_rgba(15,23,42,0.08)] backdrop-blur">
          <Link href="/landing" className="flex items-center gap-2 text-sm font-semibold tracking-tight text-slate-950">
            <span className="landing-pulse-mark flex h-8 w-8 items-center justify-center rounded-full bg-accent text-white">
              <Sparkles className="h-4 w-4" />
            </span>
            Komme
          </Link>
          <nav className="hidden items-center gap-6 text-sm font-medium text-slate-600 md:flex">
            <a href="#product" className="transition hover:text-slate-950">
              Product
            </a>
            <a href="#how" className="transition hover:text-slate-950">
              How it works
            </a>
            <a href="#trust" className="transition hover:text-slate-950">
              Trust
            </a>
          </nav>
          <Link
            href="/"
            className="landing-button inline-flex items-center gap-2 rounded-full border border-stroke bg-white px-4 py-2 text-sm font-semibold text-slate-900 transition hover:bg-canvas"
          >
            Try it out
            <ArrowRight className="h-4 w-4" />
          </Link>
        </div>

        <div className="mx-auto grid max-w-7xl gap-10 pb-16 pt-16 lg:grid-cols-[1.02fr_0.98fr] lg:items-center lg:pb-24 lg:pt-24">
          <div>
            <div className="landing-reveal [animation-delay:120ms] inline-flex items-center gap-2 rounded-full border border-teal-200 bg-white/70 px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.18em] text-teal-800">
              <ShieldCheck className="h-3.5 w-3.5" />
              NYC event planner
            </div>
            <h1 className="landing-reveal mt-6 max-w-4xl text-5xl font-semibold tracking-[-0.06em] text-slate-950 [animation-delay:210ms] sm:text-6xl lg:text-7xl">
              Plan the night. Not another list.
            </h1>
            <p className="landing-reveal mt-6 max-w-2xl text-lg leading-8 text-slate-600 [animation-delay:300ms] sm:text-xl">
              Komme turns real NYC events into a personal map, then builds a simple route you can actually use tonight.
            </p>
            <div className="landing-reveal mt-8 flex flex-col gap-3 [animation-delay:390ms] sm:flex-row">
              <Link
                href="/"
                className="landing-button inline-flex items-center justify-center gap-2 rounded-full bg-slate-950 px-6 py-3 text-sm font-semibold text-white shadow-[0_18px_36px_rgba(15,23,42,0.22)] transition hover:-translate-y-0.5"
              >
                Try Komme
                <ArrowRight className="h-4 w-4" />
              </Link>
              <a
                href="#how"
                className="landing-button inline-flex items-center justify-center rounded-full border border-stroke bg-white/75 px-6 py-3 text-sm font-semibold text-slate-900 transition hover:bg-white"
              >
                See how it works
              </a>
            </div>
            <div className="landing-reveal mt-8 flex flex-wrap gap-2 [animation-delay:480ms]">
              {proofPoints.map((point) => (
                <span key={point} className="landing-proof-pill rounded-full border border-stroke/80 bg-white/65 px-3 py-1.5 text-xs font-medium text-slate-600">
                  {point}
                </span>
              ))}
            </div>
          </div>

          <div className="landing-reveal relative [animation-delay:320ms]">
            <div className="landing-orb absolute -inset-8 -z-10 rounded-[3rem] bg-gradient-to-br from-teal-200/35 via-white/10 to-amber-200/45 blur-2xl" />
            <div className="landing-float rounded-[2rem] border border-stroke/80 bg-white/78 p-4 shadow-[0_30px_80px_rgba(15,23,42,0.16)] backdrop-blur">
              <div className="rounded-[1.5rem] border border-stroke bg-[#fbf8f1] p-4">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Tonight plan</p>
                    <h2 className="landing-title-slot mt-2 text-2xl font-semibold tracking-[-0.04em] text-slate-950">
                      <span className="sr-only">Brooklyn after dark</span>
                      <span aria-hidden="true" className="landing-title-cycle">
                        {planTitles.map((title) => (
                          <span key={title}>{title}</span>
                        ))}
                      </span>
                    </h2>
                  </div>
                  <span className="rounded-full bg-teal-50 px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-teal-800">
                    Live
                  </span>
                </div>
                <div className="landing-plan-stack mt-5 space-y-3">
                  <PlanRow time="7:30" role="Pregame" title="Low-key listening room" meta="13 min transit" />
                  <PlanRow time="9:00" role="Main" title="Dance floor pick" meta="Ticket/source ready" active />
                  <PlanRow time="11:15" role="Late option" title="Backup nearby" meta="Short hop" />
                </div>
              </div>
              <div className="mt-4 grid gap-3 sm:grid-cols-3">
                <Metric label="Real links" value="329" />
                <Metric label="Sources" value="3" />
                <Metric label="Stops" value="2-3" />
              </div>
            </div>
          </div>
        </div>
      </section>

      <section id="product" className="px-5 py-12 sm:px-8 lg:px-10">
        <div className="mx-auto max-w-7xl">
          <div className="grid gap-5 md:grid-cols-[0.9fr_1.1fr] md:items-end">
            <div className="max-w-2xl">
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">Product</p>
              <h2 className="mt-3 text-3xl font-semibold tracking-[-0.045em] text-slate-950 sm:text-4xl">
                Built for the moment when you actually decide where to go.
              </h2>
            </div>
            <p className="max-w-xl text-sm leading-6 text-slate-600 md:justify-self-end">
              Komme keeps the experience focused: one map, one shortlist, one route, and enough context to trust the pick.
            </p>
          </div>
          <div className="mt-8 grid gap-4 md:grid-cols-3">
            {features.map((feature) => {
              const Icon = feature.icon;
              return (
                <article key={feature.title} className="landing-hover-card rounded-[1.6rem] border border-stroke/80 bg-white/72 p-5 shadow-[0_18px_44px_rgba(15,23,42,0.08)]">
                  <div className="flex items-center justify-between gap-3">
                    <Icon className="h-5 w-5 text-accent" />
                    <span className="rounded-full border border-stroke/80 bg-white px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                      {feature.label}
                    </span>
                  </div>
                  <h3 className="mt-5 text-xl font-semibold tracking-[-0.035em] text-slate-950">{feature.title}</h3>
                  <p className="mt-3 text-sm leading-6 text-slate-600">{feature.body}</p>
                </article>
              );
            })}
          </div>
        </div>
      </section>

      <section id="how" className="px-5 py-12 sm:px-8 lg:px-10">
        <div className="mx-auto grid max-w-7xl gap-6 rounded-[2rem] border border-stroke/80 bg-slate-950 p-6 text-white shadow-[0_24px_72px_rgba(15,23,42,0.18)] md:grid-cols-[0.8fr_1.2fr] md:p-8">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-teal-200">How it works</p>
            <h2 className="mt-3 text-3xl font-semibold tracking-[-0.045em]">Three moves. One usable plan.</h2>
            <div className="mt-6 rounded-[1.25rem] border border-white/10 bg-white/[0.06] p-4 text-xs font-medium uppercase tracking-[0.18em] text-slate-300">
              Vibe / Map / Route
            </div>
          </div>
          <div className="grid gap-3">
            {steps.map((step, index) => (
              <div key={step} className="landing-step-row flex gap-4 rounded-[1.25rem] border border-white/10 bg-white/[0.06] p-4">
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-white text-sm font-semibold text-slate-950">
                  {index + 1}
                </span>
                <p className="pt-1 text-sm leading-6 text-slate-200">{step}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="trust" className="px-5 py-12 sm:px-8 lg:px-10">
        <div className="mx-auto max-w-7xl rounded-[2rem] border border-stroke/80 bg-white/70 p-6 shadow-[0_18px_52px_rgba(15,23,42,0.08)] md:p-8">
          <div>
            <div className="max-w-2xl">
              <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">
                <ShieldCheck className="h-4 w-4 text-accent" />
                Trust layer
              </div>
              <h2 className="mt-3 text-3xl font-semibold tracking-[-0.045em] text-slate-950">Useful recommendations need receipts.</h2>
              <p className="mt-3 text-sm leading-6 text-slate-600">
                Komme is designed to show where events came from, why they ranked, and how your actions change the next run.
              </p>
            </div>
          </div>
          <div className="mt-7 grid gap-3 md:grid-cols-3">
            {trustSignals.map((item) => {
              const Icon = item.icon;
              return (
                <div key={item.title} className="landing-hover-card rounded-[1.35rem] border border-stroke/80 bg-[#fbf8f1] p-4">
                  <Icon className="h-4 w-4 text-accent" />
                  <h3 className="mt-4 text-sm font-semibold text-slate-950">{item.title}</h3>
                  <p className="mt-2 text-xs leading-5 text-slate-600">{item.body}</p>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      <footer className="px-5 pb-8 pt-6 sm:px-8 lg:px-10">
        <div className="mx-auto flex max-w-7xl flex-col gap-5 border-t border-stroke/80 pt-6 text-sm text-slate-500 md:flex-row md:items-center md:justify-between">
          <div>
            <Link href="/landing" className="font-semibold text-slate-900">
              Komme
            </Link>
            <p className="mt-1 text-xs leading-5">NYC event discovery, personalization, and night planning.</p>
          </div>
          <div className="flex flex-wrap gap-4 text-xs font-medium">
            <Link href="/" className="transition hover:text-slate-900">
              Try it out
            </Link>
            <span>Privacy: connected signals stay user-controlled.</span>
            <span>Copyright © 2026 Duy Huynh.</span>
          </div>
        </div>
      </footer>
    </main>
  );
}

function PlanRow({
  time,
  role,
  title,
  meta,
  active = false,
}: {
  time: string;
  role: string;
  title: string;
  meta: string;
  active?: boolean;
}) {
  return (
    <div className={["landing-plan-row rounded-[1.15rem] border p-3", active ? "border-teal-200 bg-teal-50" : "border-stroke bg-white/75"].join(" ")}>
      <div className="flex items-center justify-between gap-3">
        <span className="text-sm font-semibold text-slate-950">{time}</span>
        <span className="rounded-full border border-stroke/70 bg-white px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">
          {role}
        </span>
      </div>
      <p className="mt-2 text-sm font-semibold text-slate-900">{title}</p>
      <p className="mt-1 text-xs text-slate-500">{meta}</p>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="landing-metric rounded-[1.2rem] border border-stroke/80 bg-white/75 p-3">
      <p className="text-2xl font-semibold tracking-[-0.05em] text-slate-950">{value}</p>
      <p className="mt-1 text-xs font-medium text-slate-500">{label}</p>
    </div>
  );
}
