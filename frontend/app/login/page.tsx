"use client";
import { useState, type FormEvent } from "react";
import { getSupabaseBrowserClient } from "../lib/supabase/client";

type Status =
  | { kind: "idle" }
  | { kind: "sending" }
  | { kind: "sent"; email: string }
  | { kind: "error"; message: string };

function looksLikeEmail(s: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(s.trim());
}

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<Status>({ kind: "idle" });

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const trimmed = email.trim();
    if (!looksLikeEmail(trimmed)) {
      setStatus({ kind: "error", message: "Please enter a valid email address." });
      return;
    }

    setStatus({ kind: "sending" });
    try {
      const supabase = getSupabaseBrowserClient();
      const redirectTo =
        typeof window !== "undefined"
          ? `${window.location.origin}/auth/callback`
          : undefined;

      const { error } = await supabase.auth.signInWithOtp({
        email: trimmed,
        options: { emailRedirectTo: redirectTo },
      });

      if (error) {
        const msg = /rate/i.test(error.message)
          ? "Too many requests — please wait a minute and try again."
          : error.message;
        setStatus({ kind: "error", message: msg });
        return;
      }

      setStatus({ kind: "sent", email: trimmed });
    } catch (err) {
      setStatus({
        kind: "error",
        message: err instanceof Error ? err.message : "Something went wrong.",
      });
    }
  }

  const sending = status.kind === "sending";
  const sent = status.kind === "sent";

  return (
    <div className="min-h-screen flex flex-col relative z-[1]">
      <main className="flex-1 flex items-center justify-center px-6 py-12">
        <div
          className="w-full max-w-[440px] bg-paper/80 backdrop-blur-[20px] border border-rule rounded-2xl px-10 py-12 shadow-[0_30px_80px_-40px_rgba(108,76,255,0.35)]"
          style={{ animation: "fadeUp 0.6s ease-out both" }}
        >
          <div className="mb-9 text-center">
            <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-purple mb-4">
              InfoVision · Consumer Intelligence
            </div>
            <h1
              className="text-[34px] leading-[1.15] font-medium text-ink"
              style={{ fontFamily: "var(--font-display)" }}
            >
              Sign in to{" "}
              <span
                className="italic bg-clip-text text-transparent"
                style={{
                  backgroundImage:
                    "linear-gradient(120deg, var(--color-purple) 0%, var(--color-pink) 100%)",
                }}
              >
                CI Studio
              </span>
            </h1>
            <p className="mt-3 text-[14px] text-muted">
              We&apos;ll email you a magic link — no password needed.
            </p>
          </div>

          {sent ? (
            <div
              className="rounded-xl border border-purple-rule bg-purple-soft/60 px-5 py-5 text-center"
              style={{ animation: "fadeUp 0.4s ease-out both" }}
            >
              <div className="font-mono text-[11px] uppercase tracking-[0.14em] text-purple mb-2">
                ✓ Check your email
              </div>
              <p
                className="text-[15px] text-ink"
                style={{ fontFamily: "var(--font-display)" }}
              >
                We sent a magic link to{" "}
                <span className="font-medium">{status.email}</span>
              </p>
              <p className="mt-3 text-[12px] text-muted">
                Click the link to finish signing in. You can close this tab.
              </p>
              <button
                type="button"
                onClick={() => {
                  setStatus({ kind: "idle" });
                  setEmail("");
                }}
                className="mt-5 font-mono text-[11px] text-purple hover:underline uppercase tracking-[0.1em]"
              >
                Use a different email
              </button>
            </div>
          ) : (
            <form onSubmit={onSubmit} className="space-y-4">
              <label className="block">
                <span className="block font-mono text-[10px] uppercase tracking-[0.14em] text-muted mb-2">
                  Email
                </span>
                <input
                  type="email"
                  autoComplete="email"
                  autoFocus
                  required
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value);
                    if (status.kind === "error") setStatus({ kind: "idle" });
                  }}
                  placeholder="you@company.com"
                  disabled={sending}
                  className="w-full px-4 py-3 rounded-xl border border-rule-2 bg-white text-ink text-[14px] outline-none transition focus:border-purple focus:ring-2 focus:ring-purple/15 disabled:opacity-60"
                />
              </label>

              {status.kind === "error" && (
                <div
                  role="alert"
                  className="rounded-lg border border-pink/30 bg-pink-soft px-3.5 py-2.5 text-[12.5px] text-ink-2"
                >
                  {status.message}
                </div>
              )}

              <button
                type="submit"
                disabled={sending}
                className="w-full py-3 rounded-xl text-white font-medium text-[14px] transition shadow-[0_8px_24px_-10px_rgba(108,76,255,0.6)] disabled:opacity-60 disabled:cursor-not-allowed"
                style={{
                  backgroundImage:
                    "linear-gradient(120deg, var(--color-purple) 0%, var(--color-pink) 100%)",
                }}
              >
                {sending ? "Sending…" : "Send magic link"}
              </button>
            </form>
          )}
        </div>
      </main>

      <footer className="px-6 py-6 text-center font-mono text-[10px] uppercase tracking-[0.16em] text-muted-2">
        Powered by InfoVision Consumer Intelligence
      </footer>
    </div>
  );
}
