// functions/api/login.js
// POST /api/login  body: {email, password}
//
// Looks up the user in USERS_KV by email (case-insensitive), verifies that the
// SHA-256 hex digest of the provided password matches user.passwordHash, then
// signs a session cookie and returns it.
//
// On ANY failure path (no body, missing env, missing user, bad password) we
// return 401 with the same generic message so we don't leak which part was
// wrong.
//
// TODO: passwordHash is currently SHA-256 with no salt for compatibility with
// existing KV records. Upgrade to PBKDF2-with-salt (or scrypt via WASM) on the
// next successful login per user — store the new hash format and a small
// version tag (e.g. user.passwordHashVersion = 2).
//
// TODO: KV has no email -> id index, so we paginate `USERS_KV.list()` and scan.
// This is fine for <~1000 users. Add a secondary index ("email:" + lowercased
// email -> id) on user create/update, and use it here, when we outgrow it.

import { signSession, serializeSessionCookie } from '../lib/session.js';

const SESSION_TTL_SECONDS = 60 * 60 * 24 * 7; // 7 days

function json(status, body, extraHeaders = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', ...extraHeaders },
  });
}

async function sha256Hex(str) {
  const buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(str));
  return Array.from(new Uint8Array(buf))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

// Constant-time string compare for hex digests. (Inputs must be same length;
// returns false otherwise.)
function timingSafeStrEq(a, b) {
  if (typeof a !== 'string' || typeof b !== 'string') return false;
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

// Scan USERS_KV for a user whose email matches (case-insensitive). Handles
// cursor pagination so we don't silently miss users in a large namespace.
async function findUserByEmail(kv, email) {
  const target = email.trim().toLowerCase();
  let cursor;
  // Hard cap to avoid runaway loops; in practice we expect <1000 users.
  for (let safety = 0; safety < 50; safety++) {
    const page = cursor ? await kv.list({ cursor }) : await kv.list();
    for (const k of page.keys) {
      const u = await kv.get(k.name, 'json');
      if (u && typeof u.email === 'string' && u.email.toLowerCase() === target) {
        return u;
      }
    }
    if (page.list_complete || !page.cursor) return null;
    cursor = page.cursor;
  }
  return null;
}

export async function onRequest(context) {
  const { request, env } = context;

  if (request.method !== 'POST') {
    return json(405, { error: 'Method not allowed' }, { Allow: 'POST' });
  }

  if (!env.SESSION_SECRET) {
    return json(500, {
      error:
        'SESSION_SECRET is not configured. Set it as a Pages environment variable in the Cloudflare dashboard.',
    });
  }
  if (!env.USERS_KV) {
    return json(503, {
      error:
        'User store not configured. Bind a KV namespace named USERS_KV in Cloudflare Pages settings.',
    });
  }

  let body;
  try {
    body = await request.json();
  } catch {
    return json(401, { error: 'Invalid email or password' });
  }

  const email = typeof body?.email === 'string' ? body.email.trim() : '';
  const password = typeof body?.password === 'string' ? body.password : '';
  if (!email || !password) {
    return json(401, { error: 'Invalid email or password' });
  }

  const user = await findUserByEmail(env.USERS_KV, email);
  if (!user || typeof user.passwordHash !== 'string') {
    return json(401, { error: 'Invalid email or password' });
  }

  const candidateHash = await sha256Hex(password);
  if (!timingSafeStrEq(candidateHash, user.passwordHash)) {
    return json(401, { error: 'Invalid email or password' });
  }

  const exp = Math.floor(Date.now() / 1000) + SESSION_TTL_SECONDS;
  const cookieValue = await signSession(
    { sub: user.id, email: user.email, role: user.role, exp },
    env.SESSION_SECRET
  );

  return json(
    200,
    {
      ok: true,
      user: {
        id: user.id,
        email: user.email,
        full_name: user.full_name || '',
        role: user.role,
      },
    },
    { 'Set-Cookie': serializeSessionCookie(cookieValue, { maxAge: SESSION_TTL_SECONDS }) }
  );
}
