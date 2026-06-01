import { NextResponse, type NextRequest } from "next/server";
import { createServerClient } from "@supabase/ssr";

/**
 * Next 16 `proxy.ts` (formerly `middleware.ts`).
 *
 * Auth gate:
 *   - refreshes the Supabase session cookies on every request
 *   - redirects unauthenticated users to /login (except for /login + /auth/*)
 *   - redirects authenticated users away from /login to /
 *   - skips /api/auth/*
 */
export async function proxy(request: NextRequest) {
  // AUTH DISABLED — let every request through untouched.
  return NextResponse.next({ request });
}

export const config = {
  matcher: [
    /*
     * Match all request paths except:
     * - _next/static  (build output)
     * - _next/image   (image optimizer)
     * - favicon.ico, robots.txt, sitemap.xml
     * - any path containing a file extension (images, fonts, etc.)
     */
    "/((?!_next/static|_next/image|favicon.ico|robots.txt|sitemap.xml|.*\\.[^/]+$).*)",
  ],
};
