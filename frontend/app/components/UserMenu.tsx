"use client";
import { useEffect, useRef, useState } from "react";
import { useAuth } from "./AuthProvider";

function initialsFor(email: string | undefined | null): string {
  if (!email) return "?";
  const name = email.split("@")[0] ?? "";
  const parts = name.split(/[._-]+/).filter(Boolean);
  if (parts.length >= 2) {
    return (parts[0][0] + parts[1][0]).toUpperCase();
  }
  return (name[0] ?? email[0] ?? "?").toUpperCase();
}

export default function UserMenu() {
  const { user, signOut, isLoading } = useAuth();
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onDocClick(e: MouseEvent) {
      if (!wrapRef.current?.contains(e.target as Node)) setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  if (isLoading || !user) {
    return (
      <div className="w-8 h-8 rounded-full bg-paper-2 border border-rule animate-pulse" />
    );
  }

  const initials = initialsFor(user.email);

  return (
    <div className="relative" ref={wrapRef}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        title={user.email ?? "Account"}
        className="w-8 h-8 rounded-full flex items-center justify-center text-white text-[11px] font-medium tracking-wide shadow-[0_4px_14px_-6px_rgba(108,76,255,0.55)] transition hover:scale-[1.04] focus:outline-none focus:ring-2 focus:ring-purple/30"
        style={{
          backgroundImage:
            "linear-gradient(120deg, var(--color-purple) 0%, var(--color-pink) 100%)",
        }}
      >
        {initials}
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 mt-2 w-64 rounded-xl border border-rule bg-paper/95 backdrop-blur-[20px] shadow-[0_20px_50px_-20px_rgba(20,19,42,0.25)] overflow-hidden z-30"
          style={{ animation: "fadeUp 0.18s ease-out both" }}
        >
          <div className="px-4 py-3 border-b border-rule">
            <div className="font-mono text-[9px] uppercase tracking-[0.16em] text-muted-2 mb-1">
              Signed in as
            </div>
            <div
              className="text-[13px] text-ink truncate"
              title={user.email ?? undefined}
            >
              {user.email ?? "Unknown user"}
            </div>
          </div>
          <button
            type="button"
            onClick={() => {
              setOpen(false);
              void signOut();
            }}
            className="w-full text-left px-4 py-2.5 text-[13px] text-ink-2 hover:bg-paper-2 transition"
            role="menuitem"
          >
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}
