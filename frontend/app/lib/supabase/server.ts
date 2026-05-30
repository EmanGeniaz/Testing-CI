import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
import type { SupabaseClient } from "@supabase/supabase-js";

/**
 * Server-side Supabase client for Server Components and Route Handlers.
 *
 * In Next 16, `cookies()` is async, so this helper is async too.
 * In Server Components, attempts to set cookies will throw — we swallow
 * that error because middleware (proxy.ts) is responsible for refreshing
 * the session there.
 */
export async function getSupabaseServerClient(): Promise<SupabaseClient> {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

  if (!url || !anonKey) {
    throw new Error(
      "Missing NEXT_PUBLIC_SUPABASE_URL or NEXT_PUBLIC_SUPABASE_ANON_KEY env vars",
    );
  }

  const cookieStore = await cookies();

  return createServerClient(url, anonKey, {
    cookies: {
      getAll() {
        return cookieStore.getAll();
      },
      setAll(cookiesToSet) {
        try {
          cookiesToSet.forEach(({ name, value, options }) => {
            cookieStore.set(name, value, options);
          });
        } catch {
          // Called from a Server Component — cookies can't be mutated here.
          // proxy.ts handles refreshing the session for SSR requests.
        }
      },
    },
  });
}
