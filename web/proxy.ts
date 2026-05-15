import { NextResponse, type NextRequest } from "next/server";

const COOKIE = "dashboard_pin";

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

  const expected = process.env.DASHBOARD_PIN;
  if (!expected) {
    return new NextResponse("Authentication configuration missing", { status: 500 });
  }

  const provided = req.cookies.get(COOKIE)?.value;
  if (provided === expected) {
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
