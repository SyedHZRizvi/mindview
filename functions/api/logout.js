// functions/api/logout.js
// POST /api/logout  — clears the mv_session cookie and returns {ok:true}.
// GET  /api/logout  — same, but 302-redirects to /login so a plain
//                     <a href="/api/logout">Logout</a> link works in the UI.

import { serializeClearCookie } from '../lib/session.js';

export async function onRequest(context) {
  const { request } = context;
  const method = request.method;

  // Accept GET (for plain anchor-tag logout links) and POST.
  // Anything else is rejected so we don't get clobbered by stray verbs.
  if (method !== 'GET' && method !== 'POST') {
    return new Response(JSON.stringify({ error: 'Method not allowed' }), {
      status: 405,
      headers: { 'Content-Type': 'application/json', Allow: 'GET, POST' },
    });
  }

  const clearCookie = serializeClearCookie();

  if (method === 'GET') {
    return new Response(null, {
      status: 302,
      headers: {
        Location: '/login',
        'Set-Cookie': clearCookie,
        // Prevent any cached intermediary from holding onto the cookie state.
        'Cache-Control': 'no-store',
      },
    });
  }

  // POST
  return new Response(JSON.stringify({ ok: true }), {
    status: 200,
    headers: {
      'Content-Type': 'application/json',
      'Set-Cookie': clearCookie,
      'Cache-Control': 'no-store',
    },
  });
}
