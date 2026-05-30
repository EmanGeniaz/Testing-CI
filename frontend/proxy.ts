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
  const { pathname } = request.nextUrl;

  // Always let auth-related API routes through untouched.
  if (pathname.startsWith("/api/auth/")) {
    return NextResponse.next();
  }

  let response = NextResponse.next({ request });

  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

  // If env is missing (e.g. local dev without keys), don't hard-fail —
  // just let the request through. The app will surface the error itself.
  if (!url || !anonKey) {
    return response;
  }

  const supabase = createServerClient(url, anonKey, {
    cookies: {
      getAll() {
        return request.cookies.getAll();
      },
      setAll(cookiesToSet) {
        cookiesToSet.forEach(({ name, value }) => {
          request.cookies.set(name, value);
        });
        response = NextResponse.next({ request });
        cookiesToSet.forEach(({ name, value, options }) => {
          response.cookies.set(name, value, options);
        });
      },
    },
  });

  // IMPORTANT: getUser() revalidates the JWT — don't use getSession() here.
  const {
    data: { user },
  } = await supabase.auth.getUser();

  const isLoginRoute = pathname === "/login";
  const isAuthRoute = pathname.startsWith("/auth/");

  if (!user && !isLoginRoute && !isAuthRoute) {
    const redirectUrl = request.nextUrl.clone();
    redirectUrl.pathname = "/login";
    redirectUrl.search = "";
    return NextResponse.redirect(redirectUrl);
  }

  if (user && isLoginRoute) {
    const redirectUrl = request.nextUrl.clone();
    redirectUrl.pathname = "/";
    redirectUrl.search = "";
    return NextResponse.redirect(redirectUrl);
  }

  return response;
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
