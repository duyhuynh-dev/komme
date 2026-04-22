"use client";

import { useState } from "react";
import { Mail, Link2 } from "lucide-react";
import { createClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

const supabase =
  supabaseUrl && supabaseAnonKey ? createClient(supabaseUrl, supabaseAnonKey) : null;

export function MagicLinkCard() {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("Use email magic links for Pulse identity, then connect Reddit as a separate signal source.");

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

  return (
    <div className="rounded-[1.75rem] border border-stroke bg-white/70 p-4">
      <div className="flex items-center gap-2">
        <Mail className="h-5 w-5 text-accent" />
        <h3 className="text-lg font-semibold">Magic-link sign in</h3>
      </div>
      <p className="mt-2 text-sm leading-6 text-slate-600">{message}</p>

      <form onSubmit={sendMagicLink} className="mt-4 grid gap-3">
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

      <a
        href={`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/v1/reddit/connect/start`}
        className="mt-4 inline-flex items-center gap-2 rounded-full border border-stroke px-4 py-2 text-sm font-medium text-slate-700"
      >
        <Link2 className="h-4 w-4" />
        Connect Reddit
      </a>
    </div>
  );
}

