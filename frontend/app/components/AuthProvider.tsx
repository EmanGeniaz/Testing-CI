"use client";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import type { User } from "@supabase/supabase-js";
import { getSupabaseBrowserClient } from "../lib/supabase/client";

interface AuthContextValue {
  user: User | null;
  isLoading: boolean;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let mounted = true;

    // Lazily instantiate the browser client so we don't trip during
    // static prerender (when env vars may not be available).
    let supabase;
    try {
      supabase = getSupabaseBrowserClient();
    } catch (err) {
      console.error("[Auth] Supabase client init failed:", err);
      // Defer to avoid setState-in-effect-body lint.
      queueMicrotask(() => {
        if (mounted) setIsLoading(false);
      });
      return () => {
        mounted = false;
      };
    }

    // Initial fetch.
    supabase.auth.getUser().then(({ data }) => {
      if (!mounted) return;
      setUser(data.user ?? null);
      setIsLoading(false);
    });

    // Live updates (sign-in, sign-out, token refresh).
    const { data: sub } = supabase.auth.onAuthStateChange((_event, session) => {
      if (!mounted) return;
      setUser(session?.user ?? null);
      setIsLoading(false);
    });

    return () => {
      mounted = false;
      sub.subscription.unsubscribe();
    };
  }, []);

  const signOut = useCallback(async () => {
    try {
      const supabase = getSupabaseBrowserClient();
      await supabase.auth.signOut();
    } catch (err) {
      console.error("[Auth] signOut failed:", err);
    }
    // Hard reload so the proxy re-runs and redirects to /login.
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ user, isLoading, signOut }),
    [user, isLoading, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an <AuthProvider>");
  }
  return ctx;
}
