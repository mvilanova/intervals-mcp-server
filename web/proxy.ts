import { NextResponse, type NextRequest } from "next/server";
import { COOKIE_NAME, verifySession } from "@/lib/auth";

/**
 * Protects routes by allowing public paths, validating session cookies, and redirecting unauthenticated requests to the login page.
 *
 * Examines the request path and cookie session to decide whether to continue the request, redirect to `/login` (clearing query parameters), or return a 503 when server secrets are missing.
 *
 * @param req - The incoming Next.js request to inspect
 * @returns A `NextResponse` that either continues processing (`NextResponse.next()`), redirects the client to `/login`, or is a 503 response with the message "Server misconfigured: DASHBOARD_PIN and SESSION_SECRET must be set."
 */
export function proxy(req: NextRequest) {
  const { pathname } = req.nextUrl;

  if (
    pathname === "/login" ||
    pathname === "/health" ||
    pathname.startsWith("/_next") ||
    pathname.startsWith("/api/login")
  ) {
    return NextResponse.next();
  }

  // Fail closed: refuse to serve protected routes if either secret is missing.
  if (!process.env.DASHBOARD_PIN || !process.env.SESSION_SECRET) {
    return new NextResponse(
      "Server misconfigured: DASHBOARD_PIN and SESSION_SECRET must be set.",
      { status: 503 },
    );
  }

  if (verifySession(req.cookies.get(COOKIE_NAME)?.value)) {
    return NextResponse.next();
  }

  const url = req.nextUrl.clone();
  url.pathname = "/login";
  url.search = "";
  return NextResponse.redirect(url);
}

export const config = {
  // `fonts(?:/|$)` excludes both `/fonts` and `/fonts/*` from middleware —
  // a bare `fonts/` would only exclude the trailing-slash form, leaking
  // `/fonts` into the auth-gated path.
  matcher: ["/((?!_next/static|_next/image|favicon.ico|fonts(?:/|$)).*)"],
};
