import { NextRequest, NextResponse } from 'next/server';

export function middleware(req: NextRequest) {
  // Use environment variables for production, but fallback to requested credentials
  const ADMIN_USER = process.env.ADMIN_USER || 'RamanSir';
  const ADMIN_PASS = process.env.ADMIN_PASSWORD || 'RamanSir1234@';

  const basicAuth = req.headers.get('authorization');

  if (basicAuth) {
    const authValue = basicAuth.split(' ')[1];
    const [user, pwd] = atob(authValue).split(':');

    if (user === ADMIN_USER && pwd === ADMIN_PASS) {
      return NextResponse.next();
    }
  }

  return new NextResponse('Authentication Required', {
    status: 401,
    headers: {
      'WWW-Authenticate': 'Basic realm="Admin Dashboard"',
    },
  });
}

// Apply this middleware to all pages to completely lock down the frontend
export const config = {
  matcher: [
    /*
     * Match all request paths except for the ones starting with:
     * - api (API routes, if any)
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico, sitemap.xml, robots.txt (metadata files)
     */
    '/((?!api|_next/static|_next/image|favicon.ico|sitemap.xml|robots.txt).*)',
  ],
};
