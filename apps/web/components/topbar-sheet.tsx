"use client";

import { useEffect, useState, type ReactNode } from "react";
import { X } from "lucide-react";
import { createPortal } from "react-dom";

export function TopbarSheet({
  open,
  onClose,
  title,
  eyebrow,
  widthClass = "max-w-[28rem]",
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  eyebrow?: string;
  widthClass?: string;
  children: ReactNode;
}) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!open) {
      return;
    }

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [onClose, open]);

  if (!mounted || !open) {
    return null;
  }

  return createPortal(
    <div className="fixed inset-0 z-[120]">
      <button
        type="button"
        aria-label={`Close ${title}`}
        onClick={onClose}
        className="absolute inset-0 bg-black/40 backdrop-blur-[1px]"
      />

      <aside
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={`absolute right-0 top-0 h-full w-full ${widthClass} overflow-y-auto border-l border-stroke/80 bg-white shadow-[0_28px_80px_rgba(15,23,42,0.24)]`}
      >
        <div className="sticky top-0 z-10 border-b border-stroke/80 bg-white px-5 py-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              {eyebrow ? (
                <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">{eyebrow}</p>
              ) : null}
              <h2 className="mt-1 text-2xl font-semibold text-slate-900">{title}</h2>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-stroke bg-white text-slate-500 transition hover:text-slate-900"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        <div className="px-5 py-5">{children}</div>
      </aside>
    </div>,
    document.body,
  );
}
