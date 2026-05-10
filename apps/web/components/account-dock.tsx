"use client";

import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Disc3,
  LogOut,
  Mail,
  X,
} from "lucide-react";
import {
  applySpotifyTaste,
  consumePulseSessionTokenFromUrl,
  getAuthViewer,
  getSpotifyTastePreview,
  startSpotifyConnection,
  syncSpotifyTaste,
} from "@/lib/api";
import { connectedSourceSetupState } from "@/lib/connected-source-health";
import { getSupabaseBrowserClient } from "@/lib/supabase-browser";
import { useAuth } from "@/components/auth-provider";

function statusCopy(isSignedIn: boolean) {
  if (isSignedIn) {
    return {
      eyebrow: "Pulse account",
      detail: "Taste controls shape your map.",
    };
  }
  return {
    eyebrow: "Demo mode",
    detail: "Use Spotify or email to start.",
  };
}

export function AccountDock() {
  const { isConfigured, isLoading, isAuthenticated, user, signOut, authMethod, refresh } = useAuth();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [showSwitchForm, setShowSwitchForm] = useState(false);
  const [isConnectingSpotify, setIsConnectingSpotify] = useState(false);
  const [isSyncingSpotify, setIsSyncingSpotify] = useState(false);
  const panelRef = useRef<HTMLDivElement | null>(null);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const supabase = getSupabaseBrowserClient();

  const viewerQuery = useQuery({
    queryKey: ["auth-viewer", user?.id ?? "demo"],
    queryFn: getAuthViewer,
  });

  const isSignedIn = Boolean(isAuthenticated && !isLoading);
  const status = statusCopy(isSignedIn);
  const spotifyTasteHealth =
    viewerQuery.data?.connectedSources?.find((source) => source.provider === "spotify") ??
    viewerQuery.data?.spotifyTasteHealth;
  const spotifyConnected = Boolean(spotifyTasteHealth?.connected ?? viewerQuery.data?.spotifyConnected);
  const spotifySetupState = connectedSourceSetupState(spotifyTasteHealth);
  const spotifyPreviewQuery = useQuery({
    queryKey: ["spotify-taste-preview", user?.id ?? "demo"],
    queryFn: getSpotifyTastePreview,
    enabled: isSignedIn && spotifyConnected,
  });
  const spotifyThemes = spotifyPreviewQuery.data?.themes ?? [];
  const hasSpotifyThemes = spotifyThemes.length > 0;
  const spotifyLowSignalReason = "Not enough nightlife signal yet.";
  const spotifyShortDetail = !spotifyConnected
    ? "Connect Spotify to personalize taste."
    : spotifyTasteHealth?.stale
      ? "Stale taste is paused. Refresh to use it."
      : spotifyTasteHealth?.latestRunStatus && spotifyTasteHealth.latestRunStatus !== "completed"
        ? "Last sync failed. Retry when ready."
        : !spotifyTasteHealth?.latestRunStatus
          ? "Connected. Not shaping picks yet."
          : spotifyTasteHealth.currentlyInfluencingRanking
            ? "Shaping recommendations now."
            : "Connected. Not enough active signal yet.";

  useEffect(() => {
    if (!open) {
      return;
    }

    const onPointerDown = (event: PointerEvent) => {
      const target = event.target as Node | null;
      if (!target) {
        return;
      }
      if (panelRef.current?.contains(target) || triggerRef.current?.contains(target)) {
        return;
      }
      setOpen(false);
    };

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
      }
    };

    window.addEventListener("pointerdown", onPointerDown);
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("pointerdown", onPointerDown);
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    const searchParams = new URLSearchParams(window.location.search);
    const spotifyStatus = searchParams.get("spotify");
    if (spotifyStatus !== "connected") {
      return;
    }

    consumePulseSessionTokenFromUrl();
    setOpen(true);
    setMessage("Spotify connected.");
    void refresh();
    void queryClient.invalidateQueries({ queryKey: ["auth-viewer"] });
    void queryClient.invalidateQueries({ queryKey: ["spotify-taste-preview"] });
    window.history.replaceState({}, "", window.location.pathname);
  }, [queryClient, refresh]);

  useEffect(() => {
    if (!spotifyPreviewQuery.error) {
      return;
    }

    setMessage(
      spotifyPreviewQuery.error instanceof Error
        ? spotifyPreviewQuery.error.message
        : "Unable to read a Spotify taste preview right now.",
    );
  }, [spotifyPreviewQuery.error]);

  const sendMagicLink = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (!supabase) {
      setMessage("Supabase browser keys are missing. Configure them to enable magic-link sign-in.");
      return;
    }

    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: {
        emailRedirectTo: typeof window !== "undefined" ? window.location.origin : undefined,
      },
    });

    setMessage(error ? error.message : `Magic link sent to ${email}. Check your inbox and come right back.`);
  };

  const connectSpotify = async () => {
    setIsConnectingSpotify(true);
    try {
      const response = await startSpotifyConnection();
      window.location.assign(response.authorizeUrl);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to start Spotify connection.");
      setIsConnectingSpotify(false);
    }
  };

  const applySpotifyProfile = async () => {
    try {
      await applySpotifyTaste();
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["auth-viewer"] }),
        queryClient.invalidateQueries({ queryKey: ["interests"] }),
        queryClient.invalidateQueries({ queryKey: ["map-recommendations"] }),
        queryClient.invalidateQueries({ queryKey: ["archive"] }),
        queryClient.invalidateQueries({ queryKey: ["spotify-taste-preview"] }),
      ]);
      setMessage("Spotify taste applied.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to apply the Spotify taste profile.");
    }
  };

  const retrySpotifySync = async () => {
    setIsSyncingSpotify(true);
    try {
      await syncSpotifyTaste();
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["auth-viewer"] }),
        queryClient.invalidateQueries({ queryKey: ["interests"] }),
        queryClient.invalidateQueries({ queryKey: ["map-recommendations"] }),
        queryClient.invalidateQueries({ queryKey: ["archive"] }),
        queryClient.invalidateQueries({ queryKey: ["spotify-taste-preview"] }),
      ]);
      setMessage("Spotify sync refreshed.");
    } catch (error) {
      await queryClient.invalidateQueries({ queryKey: ["auth-viewer"] });
      setMessage(error instanceof Error ? error.message : "Unable to refresh Spotify taste right now.");
    } finally {
      setIsSyncingSpotify(false);
    }
  };

  return (
    <div className="relative z-[70] overflow-visible">
      <button
        ref={triggerRef}
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="inline-flex h-11 items-center gap-2 rounded-full border border-stroke bg-white/70 px-4 py-2 text-left text-sm font-medium text-slate-700 transition hover:bg-white"
      >
        <span className="text-sm font-medium text-slate-900">Profile</span>
        {open ? <ChevronUp className="h-4 w-4 text-slate-400" /> : <ChevronDown className="h-4 w-4 text-slate-400" />}
      </button>

      {open ? (
        <div
          ref={panelRef}
          className="absolute right-0 top-[calc(100%+0.5rem)] z-[90] w-[min(23rem,calc(100vw-2rem))] max-h-[calc(100vh-120px)] overflow-y-auto rounded-[1.35rem] border border-stroke bg-white p-3.5 shadow-[0_22px_60px_rgba(15,23,42,0.18)]"
        >
          <div className="absolute right-6 top-0 h-3.5 w-3.5 -translate-y-1/2 rotate-45 border-l border-t border-stroke bg-white" />

          <div className="relative flex items-start justify-between gap-3">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-500">Account</p>
              <h3 className="mt-0.5 text-lg font-semibold text-slate-900">{isSignedIn ? "Profile" : "Start quietly"}</h3>
            </div>
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-stroke bg-white text-slate-500 transition hover:text-slate-900"
              aria-label="Close"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          <div className="mt-3 rounded-[1rem] border border-stroke/80 bg-canvas/70 p-2.5">
            {isConfigured ? (
              <div className="flex min-w-0 items-center gap-2.5">
                <span className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-white text-accent shadow-sm">
                  {isSignedIn ? <CheckCircle2 className="h-4 w-4" /> : <Mail className="h-4 w-4" />}
                </span>
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-slate-900">
                    {isSignedIn ? user?.email : "No active session"}
                  </p>
                  <p className="mt-0.5 text-xs leading-5 text-slate-500">
                    <span className="font-semibold uppercase tracking-[0.14em]">{status.eyebrow}</span>
                    <span className="mx-1.5 text-slate-300">/</span>
                    {status.detail}
                  </p>
                </div>
              </div>
            ) : (
              <p className="text-sm leading-6 text-slate-600">
                Pulse auth is not configured in this environment yet.
              </p>
            )}
          </div>

          {isSignedIn ? (
            <div className="mt-4 space-y-3">
              <div className="grid gap-2">
                {!spotifyConnected ? (
                  <button
                    type="button"
                    onClick={() => void connectSpotify()}
                    disabled={isConnectingSpotify}
                    className="inline-flex items-center justify-center gap-2 rounded-full bg-emerald-600 px-4 py-2.5 text-sm font-medium text-white disabled:opacity-60"
                  >
                    <Disc3 className="h-4 w-4" />
                    {isConnectingSpotify ? "Redirecting..." : authMethod === "pulse_session" ? "Reconnect Spotify" : "Connect Spotify"}
                  </button>
                ) : hasSpotifyThemes ? (
                  <button
                    type="button"
                    onClick={() => void applySpotifyProfile()}
                    disabled={spotifyPreviewQuery.isLoading}
                    className="inline-flex items-center justify-center gap-2 rounded-full bg-emerald-600 px-4 py-2.5 text-sm font-medium text-white disabled:opacity-60"
                  >
                    <Disc3 className="h-4 w-4" />
                    {spotifyPreviewQuery.isLoading ? "Reading Spotify..." : "Use Spotify taste"}
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={() => void spotifyPreviewQuery.refetch()}
                    disabled={spotifyPreviewQuery.isLoading}
                    className="inline-flex items-center justify-center gap-2 rounded-full border border-stroke bg-white px-4 py-2.5 text-sm font-medium text-slate-700 disabled:opacity-60"
                  >
                    <Disc3 className="h-4 w-4" />
                    {spotifyPreviewQuery.isLoading ? "Reading Spotify..." : "Refresh Spotify"}
                  </button>
                )}
              </div>

              <div className="rounded-[1rem] border border-stroke/80 bg-white/80 px-3 py-2.5">
                <div className="grid gap-1.5">
                  <div className="flex items-center justify-between gap-2">
                    <h4 className="text-sm font-semibold text-slate-900">Spotify</h4>
                    <span
                      className={[
                        "inline-flex shrink-0 items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.14em]",
                        spotifyConnected
                          ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                          : "border-stroke bg-white text-slate-500",
                      ].join(" ")}
                    >
                      <Disc3 className="h-3.5 w-3.5" />
                      {spotifyConnected ? "Connected" : "Off"}
                    </span>
                  </div>
                  <p className="text-xs leading-5 text-slate-500">{spotifyShortDetail}</p>
                </div>
                {spotifyConnected && !isSignedIn ? (
                  <div className="mt-3 rounded-2xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm leading-6 text-amber-900">
                    Allow cookies for Pulse, then reconnect Spotify.
                  </div>
                ) : null}
                <div className="mt-2.5 flex flex-wrap gap-2 text-xs font-medium text-slate-600">
                  <span className="rounded-full border border-stroke bg-white px-2.5 py-1">
                    {spotifySetupState.syncLabel}
                  </span>
                  <span className="rounded-full border border-stroke bg-white px-2.5 py-1">
                    {spotifyTasteHealth?.currentlyInfluencingRanking ? "Shaping picks" : "Not shaping picks"}
                  </span>
                </div>
                {spotifySetupState.action === "connect" ? (
                  <button
                    type="button"
                    onClick={() => void connectSpotify()}
                    disabled={isConnectingSpotify}
                    className="mt-2.5 inline-flex items-center justify-center rounded-full border border-stroke bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 disabled:opacity-60"
                  >
                    {isConnectingSpotify ? "Redirecting..." : "Connect Spotify"}
                  </button>
                ) : spotifySetupState.action === "sync" ? (
                  <button
                    type="button"
                    onClick={() => void retrySpotifySync()}
                    disabled={isSyncingSpotify}
                    className="mt-2.5 inline-flex items-center justify-center rounded-full border border-amber-200 bg-white px-3 py-1.5 text-xs font-semibold text-amber-800 disabled:opacity-60"
                  >
                    {isSyncingSpotify ? "Refreshing Spotify..." : "Retry Spotify sync"}
                  </button>
                ) : null}
                {spotifyConnected && spotifyPreviewQuery.data && hasSpotifyThemes ? (
                  <>
                    <p className="mt-3 text-xs leading-5 text-slate-500">{spotifyThemes.length} themes found.</p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {spotifyThemes.slice(0, 3).map((theme) => (
                        <span
                          key={theme.id}
                          className="rounded-full border border-stroke bg-white px-2.5 py-1 text-xs font-medium text-slate-700"
                        >
                          {theme.label} · {theme.confidenceLabel}
                        </span>
                      ))}
                    </div>
                  </>
                ) : spotifyConnected && spotifyPreviewQuery.data ? (
                  <>
                    <p className="mt-3 text-xs leading-5 text-slate-500">{spotifyLowSignalReason}</p>
                  </>
                ) : null}
              </div>
              <div className="flex flex-wrap items-center justify-between gap-3 border-t border-stroke/80 pt-3">
                {authMethod === "supabase" ? (
                  <button
                    type="button"
                    onClick={() => setShowSwitchForm((value) => !value)}
                    className="inline-flex items-center gap-2 text-sm font-medium text-slate-600 transition hover:text-slate-900"
                  >
                    {showSwitchForm ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                    Use another email
                  </button>
                ) : (
                  <span className="text-xs leading-5 text-slate-500">Spotify session active.</span>
                )}
                <button
                  type="button"
                  onClick={() => void signOut()}
                  className="inline-flex items-center gap-2 text-sm font-medium text-slate-500 transition hover:text-slate-900"
                >
                  <LogOut className="h-4 w-4" />
                  Sign out
                </button>
              </div>
            </div>
          ) : null}

          {!isSignedIn || showSwitchForm ? (
            <form
              onSubmit={sendMagicLink}
              className="mt-4 grid gap-2 rounded-[1.25rem] border border-dashed border-stroke bg-white/70 p-3"
            >
              {isSignedIn ? (
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Add magic-link sign-in</p>
              ) : (
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Magic-link sign in</p>
              )}
              <input
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                type="email"
                required
                placeholder="you@example.com"
                className="rounded-2xl border border-stroke bg-white px-3 py-2 text-sm"
              />
              <button type="submit" className="rounded-full bg-slate-900 px-4 py-2.5 text-sm font-medium text-white">
                {isSignedIn ? "Send magic link" : "Send magic link"}
              </button>
            </form>
          ) : null}

          {!isSignedIn ? (
            <div className="mt-4 grid gap-2">
              <button
                type="button"
                onClick={() => void connectSpotify()}
                disabled={isConnectingSpotify}
                className="inline-flex items-center justify-center gap-2 rounded-full bg-emerald-600 px-4 py-2.5 text-sm font-medium text-white disabled:opacity-60"
              >
                <Disc3 className="h-4 w-4" />
                {isConnectingSpotify ? "Redirecting to Spotify..." : "Continue with Spotify"}
              </button>
            </div>
          ) : null}

          {message ? <p className="mt-4 text-xs leading-5 text-slate-500">{message}</p> : null}
        </div>
      ) : null}
    </div>
  );
}
