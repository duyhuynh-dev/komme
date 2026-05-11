"use client";

import { useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BellRing } from "lucide-react";
import { getEmailPreferences, saveEmailPreferences } from "@/lib/api";
import type { EmailPreferences } from "@/lib/types";
import { formatDigestTime } from "@/lib/utils";
import { useAuth } from "@/components/auth-provider";

const digestDays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"] as const;

const schema = z.object({
  weeklyDigestEnabled: z.boolean(),
  digestDay: z.enum(digestDays),
  digestTimeLocal: z.string().regex(/^\d{2}:\d{2}$/),
  timezone: z.string().min(1)
});

type FormValues = z.infer<typeof schema>;

export function DigestSettingsCard({ compact = false }: { compact?: boolean }) {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [status, setStatus] = useState("Weekly shortlist email.");
  const browserTimezone = useMemo(
    () => Intl.DateTimeFormat().resolvedOptions().timeZone || "America/New_York",
    [],
  );

  const preferencesQuery = useQuery({
    queryKey: ["email-preferences", user?.id ?? "demo"],
    queryFn: getEmailPreferences,
    enabled: Boolean(user),
  });

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      weeklyDigestEnabled: true,
      digestDay: "Tuesday",
      digestTimeLocal: "09:00",
      timezone: browserTimezone,
    },
  });

  useEffect(() => {
    if (!preferencesQuery.data) {
      return;
    }

    form.reset({
      weeklyDigestEnabled: preferencesQuery.data.weeklyDigestEnabled,
      digestDay: preferencesQuery.data.digestDay as FormValues["digestDay"],
      digestTimeLocal: preferencesQuery.data.digestTimeLocal,
      timezone: preferencesQuery.data.timezone || browserTimezone,
    });
    setStatus(
      preferencesQuery.data.weeklyDigestEnabled
        ? `${preferencesQuery.data.digestDay} · ${formatDigestTime(preferencesQuery.data.digestTimeLocal)}`
        : "Paused.",
    );
  }, [browserTimezone, form, preferencesQuery.data]);

  const saveMutation = useMutation({
    mutationFn: (payload: EmailPreferences) => saveEmailPreferences(payload),
    onSuccess: (data) => {
      queryClient.setQueryData(["email-preferences", user?.id ?? "demo"], data);
      setStatus(
        data.weeklyDigestEnabled
          ? `Saved · ${data.digestDay} ${formatDigestTime(data.digestTimeLocal)}`
          : "Saved. Weekly digests are paused for now.",
      );
    },
    onError: (error) => {
      setStatus(error instanceof Error ? error.message : "Unable to save weekly digest timing right now.");
    },
  });

  const values = form.watch();
  const containerClass = compact
    ? "rounded-[1.1rem] border border-stroke/80 bg-white/60 p-2.5 backdrop-blur"
    : "rounded-[1.75rem] border border-stroke bg-white/70 p-4";

  return (
    <div className={containerClass}>
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <BellRing className={compact ? "h-4 w-4 text-accent" : "h-5 w-5 text-accent"} />
          <h3 className={compact ? "text-sm font-semibold" : "text-lg font-semibold"}>Weekly digest</h3>
        </div>
        <span className="rounded-full bg-canvas px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-500">
          {values.weeklyDigestEnabled ? "On" : "Paused"}
        </span>
      </div>

      {!compact ? (
        <p className="mt-2 text-sm leading-6 text-slate-600">
          Keep the shortlist on autopilot without putting the email workflow in the middle of the main map experience.
        </p>
      ) : null}

      <p className={compact ? "mt-2 rounded-[0.95rem] bg-canvas/80 px-3 py-2 text-xs leading-5 text-slate-500" : "mt-3 rounded-[1.15rem] bg-canvas/80 px-3 py-3 text-sm leading-6 text-slate-600"}>{status}</p>

      <form
        onSubmit={form.handleSubmit((nextValues) =>
          saveMutation.mutate({
            ...nextValues,
            timezone: nextValues.timezone || browserTimezone,
          })
        )}
        className={compact ? "mt-3 grid gap-2.5" : "mt-4 grid gap-4"}
      >
        <label className="flex items-center justify-between gap-3 rounded-[0.95rem] border border-stroke bg-white/70 px-3 py-2">
          <span>
            <span className="block text-sm font-medium text-slate-800">Email weekly shortlist</span>
            {!compact ? (
              <span className="mt-1 block text-xs leading-5 text-slate-500">
                Komme checks the schedule every 15 minutes, then sends the latest completed recommendation run when your window opens.
              </span>
            ) : null}
          </span>
          <input
            type="checkbox"
            className="h-4 w-4 rounded border-stroke text-accent focus:ring-accent"
            {...form.register("weeklyDigestEnabled")}
          />
        </label>

        <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <label className="grid min-w-0 gap-1">
            <span className={compact ? "text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500" : "text-sm font-medium text-slate-700"}>Day</span>
            <select
              {...form.register("digestDay")}
              disabled={!values.weeklyDigestEnabled}
              className="w-full min-w-0 rounded-[0.9rem] border border-stroke bg-white px-3 py-2 text-sm text-slate-700 outline-none transition focus:border-accent/35 focus:ring-2 focus:ring-accent/15 disabled:bg-canvas/70 disabled:text-slate-400"
            >
              {digestDays.map((day) => (
                <option key={day} value={day}>
                  {day}
                </option>
              ))}
            </select>
          </label>

          <label className="grid min-w-0 gap-1">
            <span className={compact ? "text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500" : "text-sm font-medium text-slate-700"}>Time</span>
            <input
              type="time"
              {...form.register("digestTimeLocal")}
              disabled={!values.weeklyDigestEnabled}
              className="w-full min-w-0 rounded-[0.9rem] border border-stroke bg-white px-3 py-2 text-sm text-slate-700 outline-none transition focus:border-accent/35 focus:ring-2 focus:ring-accent/15 disabled:bg-canvas/70 disabled:text-slate-400"
            />
          </label>
        </div>

        <div className="flex items-center justify-between gap-3">
          <p className="text-xs leading-5 text-slate-500">
            Timezone: <span className="font-medium text-slate-700">{values.timezone || browserTimezone}</span>
          </p>
          <button
            type="submit"
            disabled={saveMutation.isPending || preferencesQuery.isLoading}
            className="rounded-full border border-stroke bg-white px-3 py-1.5 text-sm font-medium text-slate-700 shadow-sm transition hover:bg-canvas disabled:opacity-60"
          >
            {saveMutation.isPending ? "Saving..." : "Save"}
          </button>
        </div>
      </form>
    </div>
  );
}
