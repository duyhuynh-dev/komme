"use client";

import { useEffect, useState } from "react";
import { RailModal } from "@/components/rail-modal";
import type { FeedbackReason } from "@/lib/types";

const SAVE_REASON_OPTIONS: FeedbackReason[] = [
  { key: "right_vibe", label: "Right vibe" },
  { key: "love_lineup", label: "Love lineup" },
  { key: "great_venue", label: "Great venue" },
  { key: "good_area", label: "Good area" },
  { key: "easy_to_get_to", label: "Easy to get to" },
  { key: "good_price", label: "Good price" },
];

const DISMISS_REASON_OPTIONS: FeedbackReason[] = [
  { key: "wrong_vibe", label: "Wrong vibe" },
  { key: "too_far", label: "Too far" },
  { key: "too_expensive", label: "Too expensive" },
  { key: "bad_timing", label: "Bad timing" },
  { key: "already_seen", label: "Already seen enough like this" },
  { key: "not_trustworthy", label: "Not trustworthy enough" },
];

const MAX_REASON_SELECTIONS = 3;

export function FeedbackReasonModal({
  open,
  action,
  venueName,
  isSubmitting,
  onClose,
  onSubmit,
}: {
  open: boolean;
  action: "save" | "dismiss" | null;
  venueName: string | null;
  isSubmitting: boolean;
  onClose: () => void;
  onSubmit: (reasons: FeedbackReason[]) => void;
}) {
  const [selectedReasons, setSelectedReasons] = useState<FeedbackReason[]>([]);

  useEffect(() => {
    if (!open) {
      setSelectedReasons([]);
    }
  }, [open, action, venueName]);

  if (!open || action === null) {
    return null;
  }

  const options = action === "save" ? SAVE_REASON_OPTIONS : DISMISS_REASON_OPTIONS;
  const prompt =
    action === "save"
      ? `What makes ${venueName ?? "this spot"} worth keeping?`
      : `What makes ${venueName ?? "this spot"} a miss for now?`;

  const submitLabel = action === "save" ? "Save spot" : "Hide spot";
  const skipLabel = action === "save" ? "Save without details" : "Hide without details";

  const toggleReason = (reason: FeedbackReason) => {
    setSelectedReasons((current) => {
      const exists = current.some((item) => item.key === reason.key);
      if (exists) {
        return current.filter((item) => item.key !== reason.key);
      }
      if (current.length >= MAX_REASON_SELECTIONS) {
        return current;
      }
      return [...current, reason];
    });
  };

  return (
    <RailModal
      open={open}
      title={action === "save" ? "Save feedback" : "Hide feedback"}
      onClose={onClose}
    >
      <div className="space-y-5">
        <div>
          <p className="text-sm leading-6 text-slate-600">{prompt}</p>
          <p className="mt-2 text-xs uppercase tracking-[0.18em] text-slate-400">
            Pick up to {MAX_REASON_SELECTIONS}. This helps Komme sharpen future ranking.
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          {options.map((reason) => {
            const active = selectedReasons.some((item) => item.key === reason.key);
            return (
              <button
                key={reason.key}
                type="button"
                onClick={() => toggleReason(reason)}
                className={[
                  "rounded-full border px-4 py-2 text-sm font-medium transition",
                  active
                    ? "border-accent bg-accent text-white"
                    : "border-stroke bg-white text-slate-700 hover:bg-canvas",
                ].join(" ")}
              >
                {reason.label}
              </button>
            );
          })}
        </div>

        <div className="flex flex-wrap items-center gap-3 border-t border-stroke/70 pt-4">
          <button
            type="button"
            onClick={() => onSubmit(selectedReasons)}
            disabled={isSubmitting}
            className="rounded-full bg-accent px-5 py-2.5 text-sm font-medium text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isSubmitting ? "Saving..." : submitLabel}
          </button>
          <button
            type="button"
            onClick={() => onSubmit([])}
            disabled={isSubmitting}
            className="rounded-full border border-stroke bg-white px-5 py-2.5 text-sm font-medium text-slate-700 transition hover:bg-canvas disabled:cursor-not-allowed disabled:opacity-60"
          >
            {skipLabel}
          </button>
        </div>
      </div>
    </RailModal>
  );
}
