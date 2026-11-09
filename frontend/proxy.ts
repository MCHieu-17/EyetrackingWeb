import { NextResponse, type NextRequest } from "next/server";

const PROTECTED_PREFIXES = ["/teacher", "/student", "/admin"];
const PUBLIC_ONLY = ["/account/login", "/account/register"];

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  const hasAccess = request.cookies.has("access_token");
  const hasRefresh = request.cookies.has("refresh_token");
  const isAuthenticated = hasAccess || hasRefresh;

  const isProtected = PROTECTED_PREFIXES.some(
    (p) => pathname === p || pathname.startsWith(`${p}/`),
  );
  const isPublicOnly = PUBLIC_ONLY.some(
    (p) => pathname === p || pathname.startsWith(`${p}/`),
  );

  if (isProtected && !isAuthenticated) {
    const loginUrl = new URL("/account/login", request.url);
    loginUrl.searchParams.set("next", pathname);
    return NextResponse.redirect(loginUrl);
  }

  if (isPublicOnly && isAuthenticated) {
    const next = request.nextUrl.searchParams.get("next");
    if (next && PROTECTED_PREFIXES.some((p) => next.startsWith(p))) {
      return NextResponse.redirect(new URL(next, request.url));
    }
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/teacher/:path*", "/student/:path*", "/admin/:path*", "/account/login", "/account/register"],
};
