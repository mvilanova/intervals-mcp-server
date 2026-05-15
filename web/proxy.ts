import { NextResponse, type NextRequest } from "next/server";
import { COOKIE_NAME, verifySession } from "@/lib/auth";

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
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
