import { NextResponse, type NextRequest } from "next/server";

// UX-level guard only: redirects visitors without a session cookie away from /app.
// Real authentication and authorization are enforced by the FastAPI backend on every request.
export function middleware(req: NextRequest) {
  if (!req.cookies.get("lf_session")) {
    const url = req.nextUrl.clone();
    url.pathname = "/login";
    url.searchParams.set("next", req.nextUrl.pathname);
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
}

export const config = { matcher: ["/app/:path*"] };
