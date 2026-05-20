// functions/_middleware.js
// Runs for every request handled by Pages Functions (i.e. every HTML page
// AND every /api/* call — static-asset requests served directly from the
// edge cache also pass through here on cache miss).
//
// Behavior:
//   - Pass-through (no auth gate) for: /login, /api/login, /api/logout,
//     /api/bootstrap, /api/me, /logo.png, and any path with a static-asset
//     extension (.css .js .png .jpg .jpeg .gif .svg .webp .ico .woff .woff2
//     .ttf .map).
//   - For everything else: require a valid mv_session cookie. If missing/
//     invalid, 302 to /login?next=<encoded original URL>.
//   - If SESSION_SECRET is unset, return 500 with a clear error so the owner
//     notices in dev/prod instead of silently allowing traffic through.

import { readSessionFromRequest } from './lib/session.js';

// Paths that are always allowed through without a valid session.
// Note: trailing slashes are normalized away before matching.
const PUBLIC_EXACT = new Set([
  '/login',
  '/api/login',
  '/api/logout',
  '/api/bootstrap',
  '/api/me',
  '/logo.png',
]);

// Lowercased file extensions that are always treated as public static assets.
const STATIC_EXTENSIONS = new Set([
  '.css',
  '.js',
  '.png',
  '.jpg',
  '.jpeg',
  '.gif',
  '.svg',
  '.webp',
  '.ico',
  '.woff',
  '.woff2',
  '.ttf',
  '.map',
]);

function getExtension(pathname) {
  // Last segment of the path, then the substring from the last "." onwards.
  const lastSlash = pathname.lastIndexOf('/');
  const lastSeg = lastSlash >= 0 ? pathname.slice(lastSlash + 1) : pathname;
  const dot = lastSeg.lastIndexOf('.');
  if (dot <= 0) return '';
  return lastSeg.slice(dot).toLowerCase();
}

function isPublic(pathname) {
  // Normalize: strip trailing slash unless it's the root.
  let p = pathname;
  if (p.length > 1 && p.endsWith('/')) p = p.slice(0, -1);
  if (PUBLIC_EXACT.has(p)) return true;
  const ext = getExtension(p);
  if (ext && STATIC_EXTENSIONS.has(ext)) return true;
  return false;
}

export async function onRequest(context) {
  const { request, env, next } = context;
  const url = new URL(request.url);

  // Always allow CORS preflights through unscathed.
  if (request.method === 'OPTIONS') return next();

  if (isPublic(url.pathname)) return next();

  if (!env.SESSION_SECRET) {
    return new Response(
      JSON.stringify({
        error:
          'SESSION_SECRET is not configured. Set it as a Pages environment variable in the Cloudflare dashboard.',
      }),
      { status: 500, headers: { 'Content-Type': 'application/json' } }
    );
  }

  const payload = await readSessionFromRequest(request, env.SESSION_SECRET);
  if (payload) {
    // Authenticated — let downstream handler / static asset serve.
    return next();
  }

  // Not authenticated. For HTML / page navigations, redirect to /login with
  // a `next` param so the login page can bounce back. For API calls, return
  // 401 JSON so XHR / fetch callers can react without a confusing 302.
  if (url.pathname.startsWith('/api/')) {
    return new Response(JSON.stringify({ error: 'Authentication required' }), {
      status: 401,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  const nextTarget = url.pathname + url.search;
  const loginUrl = `/login?next=${encodeURIComponent(nextTarget)}`;
  return new Response(null, {
    status: 302,
    headers: {
      Location: loginUrl,
      'Cache-Control': 'no-store',
    },
  });
}
