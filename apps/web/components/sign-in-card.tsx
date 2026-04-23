"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Mail, Link2 } from "lucide-react";
import { getAuthViewer, startMockRedditConnection, startRedditConnection } from "@/lib/api";
import { getSupabaseBrowserClient } from "@/lib/supabase-browser";
import { useAuth } from "@/components/auth-provider";

export function MagicLinkCard({ compact = false }: { compact?: boolean }) {
  const { isConfigured, isLoading, session, user, signOut } = useAuth();
  const queryClient = useQueryClient();
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("Use email magic links for Pulse identity, then connect Reddit as a separate signal source.");
  const [isConnectingReddit, setIsConnectingReddit] = useState(false);
  const [isLoadingSample, setIsLoadingSample] = useState(false);
  const supabase = getSupabaseBrowserClient();

  const viewerQuery = useQuery({
    queryKey: ["auth-viewer", user?.id ?? "demo"],
    queryFn: getAuthViewer
  });
  const redditStatusLabel =
    viewerQuery.data?.redditConnectionMode === "live"
      ? "Reddit connected"
      : viewerQuery.data?.redditConnectionMode === "sample"
        ? "Sample profile attached"
        : session
          ? "Ready for Reddit"
          : "Identity only";
  const containerClass = compact
    ? "rounded-[1.5rem] border border-stroke/80 bg-white/60 p-4 backdrop-blur"
    : "rounded-[1.75rem] border border-stroke bg-white/70 p-4";

  const sendMagicLink = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (!supabase) {
      setMessage("Supabase environment variables are missing. Configure them to enable magic-link auth.");
      return;
    }

    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: {
        emailRedirectTo: typeof window !== "undefined" ? window.location.origin : undefined
      }
    });

    setMessage(error ? error.message : "Check your inbox for a sign-in link.");
  };

  const connectReddit = async () => {
    if (!session) {
      setMessage("Sign in first so Pulse can attach the Reddit connection to your account.");
      return;
    }

    setIsConnectingReddit(true);
    try {
      const response = await startRedditConnection();
      window.location.assign(response.authorizeUrl);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to start Reddit connection.");
      setIsConnectingReddit(false);
    }
  };

  const connectSampleProfile = async () => {
    if (!session) {
      setMessage("Sign in first so Pulse can attach the sample profile to your account.");
      return;
    }

    setIsLoadingSample(true);
    try {
      await startMockRedditConnection();
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["auth-viewer"] }),
        queryClient.invalidateQueries({ queryKey: ["interests"] }),
        queryClient.invalidateQueries({ queryKey: ["map-recommendations"] }),
        queryClient.invalidateQueries({ queryKey: ["archive"] }),
      ]);
      setMessage("Sample Reddit profile loaded. You can keep building with the real user flow while approval is pending.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to load the sample Reddit profile.");
    } finally {
      setIsLoadingSample(false);
    }
  };

  return (
    <div className={containerClass}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <Mail className="h-5 w-5 text-accent" />
          <h3 className={compact ? "text-base font-semibold" : "text-lg font-semibold"}>Magic-link sign in</h3>
        </div>
        {compact ? (
          <span className="rounded-full bg-canvas px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
            {redditStatusLabel}
          </span>
        ) : null}
      </div>
      <p className={compact ? "mt-2 text-sm leading-5 text-slate-600" : "mt-2 text-sm leading-6 text-slate-600"}>
        {compact
          ? "Keep account setup tucked away here, then attach Reddit when you want live personalization."
          : message}
      </p>

      <div className={compact ? "mt-3 rounded-[1.25rem] bg-canvas/80 px-3 py-3 text-sm text-slate-700" : "mt-3 rounded-2xl bg-canvas px-3 py-3 text-sm text-slate-700"}>
        {!isConfigured ? (
          <p>Supabase browser keys are missing, so the app stays in demo mode until those env vars are added.</p>
        ) : isLoading ? (
          <p>Checking your session...</p>
        ) : session ? (
          <div className={compact ? "space-y-3" : "space-y-2"}>
            <p className={compact ? "text-sm leading-5" : undefined}>
              Signed in as <span className="font-semibold">{user?.email}</span>
            </p>
            <p className="text-slate-500">
              {viewerQuery.data?.redditConnectionMode === "live"
                ? "Live Reddit connection is attached to this Pulse account."
                : viewerQuery.data?.redditConnectionMode === "sample"
                  ? "Sample Reddit profile is attached while API approval is pending."
                  : "Reddit not connected yet."}
            </p>
            <button
              type="button"
              onClick={() => void signOut()}
              className="rounded-full border border-stroke bg-white px-4 py-2 text-sm font-medium text-slate-700"
            >
              Sign out
            </button>
          </div>
        ) : (
          <p>No active session yet. Send a magic link, then come back here to connect Reddit.</p>
        )}
      </div>

      <form onSubmit={sendMagicLink} className={compact ? "mt-4 grid gap-2" : "mt-4 grid gap-3"}>
        <input
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          type="email"
          required
          placeholder="you@example.com"
          className="rounded-2xl border border-stroke bg-white px-3 py-2 text-sm"
        />

        <button type="submit" className="rounded-full bg-slate-900 px-4 py-2 text-sm font-medium text-white">
          Send magic link
        </button>
      </form>

      <div className={compact ? "mt-3 grid gap-2" : undefined}>
        <button
          type="button"
          onClick={() => void connectReddit()}
          disabled={!session || isConnectingReddit}
          className={
            compact
              ? "inline-flex items-center justify-center gap-2 rounded-full border border-stroke px-4 py-2 text-sm font-medium text-slate-700 disabled:opacity-60"
              : "mt-4 inline-flex items-center justify-center gap-2 rounded-full border border-stroke px-4 py-2 text-sm font-medium text-slate-700 disabled:opacity-60"
          }
        >
          <Link2 className="h-4 w-4" />
          {isConnectingReddit ? "Redirecting to Reddit..." : "Connect Reddit"}
        </button>

        <button
          type="button"
          onClick={() => void connectSampleProfile()}
          disabled={!session || isLoadingSample}
          className={
            compact
              ? "inline-flex items-center justify-center gap-2 rounded-full bg-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
              : "mt-3 inline-flex items-center justify-center gap-2 rounded-full bg-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
          }
        >
          <Link2 className="h-4 w-4" />
          {isLoadingSample ? "Loading sample profile..." : "Load sample Reddit profile"}
        </button>
      </div>

      {compact ? (
        <p className="mt-3 text-xs leading-5 text-slate-500">{message}</p>
      ) : null}
    </div>
  );
}
