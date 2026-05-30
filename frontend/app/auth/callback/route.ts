import { NextResponse, type NextRequest } from "next/server";
import { getSupabaseServerClient } from "../../lib/supabase/server";

/**
 * Magic-link callback. Supabase redirects the user here after they click
 * the link in their email. We exchange the `?code=...` for a session
 * and drop the user on `/` (or the originally requested `next` path).
 */
export async function GET(request: NextRequest) {
  const { searchParams, origin } = new URL(request.url);
  const code = searchParams.get("code");
  const next = searchParams.get("next") ?? "/";

  if (code) {
    const supabase = await getSupabaseServerClient();
    const { error } = await supabase.auth.exchangeCodeForSession(code);
    if (!error) {
      return NextResponse.redirect(`${origin}${next}`);
    }
    // Fall through to error redirect below.
    return NextResponse.redirect(
      `${origin}/login?error=${encodeURIComponent(error.message)}`,
    );
  }

  return NextResponse.redirect(`${origin}/login?error=missing_code`);
}
