// functions/lib/session.js
//
// Shared cookie/session utilities for the mv_session HttpOnly auth cookie.
// Format: base64url(JSON({sub, email, role, exp})) + "." + base64url(HMAC-SHA256(payload, SESSION_SECRET))
//
// All cryptographic operations use WebCrypto SubtleCrypto, which is available
// natively in Cloudflare Workers / Pages Functions — no external dependencies.

// ---------- base64url helpers ----------

function bytesToBase64Url(bytes) {
  let binary = '';
  for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
  // btoa produces standard base64; convert to URL-safe variant and strip padding.
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

function base64UrlToBytes(b64url) {
  // Restore standard base64 padding before decoding.
  let s = String(b64url).replace(/-/g, '+').replace(/_/g, '/');
  while (s.length % 4) s += '=';
  const binary = atob(s);
  const out = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) out[i] = binary.charCodeAt(i);
  return out;
}

function encodeText(str) {
  return new TextEncoder().encode(str);
}

function decodeText(bytes) {
  return new TextDecoder().decode(bytes);
}

// ---------- HMAC ----------

async function importHmacKey(secret) {
  return crypto.subtle.importKey(
    'raw',
    encodeText(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign', 'verify']
  );
}

async function hmacSign(secret, dataBytes) {
  const key = await importHmacKey(secret);
  const sig = await crypto.subtle.sign('HMAC', key, dataBytes);
  return new Uint8Array(sig);
}

// Constant-time compare of two Uint8Arrays. Returns false on length mismatch.
function timingSafeEqual(a, b) {
  if (!(a instanceof Uint8Array) || !(b instanceof Uint8Array)) return false;
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a[i] ^ b[i];
  return diff === 0;
}

// ---------- Public API ----------

/**
 * Sign a session payload and return the cookie value
 *   "<base64url(payload)>.<base64url(hmac)>"
 *
 * The caller is expected to pre-populate `exp` (seconds since epoch).
 * The minimum payload is {sub, email, role, exp}.
 */
export async function signSession(payload, secret) {
  if (!secret) throw new Error('SESSION_SECRET is not configured');
  const payloadJson = JSON.stringify(payload);
  const payloadB64 = bytesToBase64Url(encodeText(payloadJson));
  const sig = await hmacSign(secret, encodeText(payloadB64));
  const sigB64 = bytesToBase64Url(sig);
  return `${payloadB64}.${sigB64}`;
}

/**
 * Verify a signed cookie value. Returns the payload object on success,
 * or null on any failure (bad format, bad signature, expired, etc.).
 *
 * Signature comparison is constant-time.
 */
export async function verifySession(cookieValue, secret) {
  if (!secret || typeof cookieValue !== 'string') return null;
  const dot = cookieValue.indexOf('.');
  if (dot < 1 || dot === cookieValue.length - 1) return null;
  const payloadB64 = cookieValue.slice(0, dot);
  const sigB64 = cookieValue.slice(dot + 1);

  let providedSig;
  try {
    providedSig = base64UrlToBytes(sigB64);
  } catch {
    return null;
  }

  let expectedSig;
  try {
    expectedSig = await hmacSign(secret, encodeText(payloadB64));
  } catch {
    return null;
  }

  if (!timingSafeEqual(expectedSig, providedSig)) return null;

  let payload;
  try {
    payload = JSON.parse(decodeText(base64UrlToBytes(payloadB64)));
  } catch {
    return null;
  }

  if (!payload || typeof payload !== 'object') return null;
  if (typeof payload.exp !== 'number') return null;
  const nowSec = Math.floor(Date.now() / 1000);
  if (payload.exp <= nowSec) return null;

  return payload;
}

/**
 * Parse a Cookie header into a plain object. Returns {} for null/empty.
 * Values are URL-decoded the same way browsers send them (we use
 * decodeURIComponent and silently fall back to the raw value on bad input).
 */
export function parseCookies(cookieHeader) {
  const out = {};
  if (!cookieHeader || typeof cookieHeader !== 'string') return out;
  const parts = cookieHeader.split(';');
  for (const part of parts) {
    const eq = part.indexOf('=');
    if (eq < 0) continue;
    const name = part.slice(0, eq).trim();
    if (!name) continue;
    let value = part.slice(eq + 1).trim();
    // Strip surrounding quotes if present.
    if (value.length >= 2 && value.startsWith('"') && value.endsWith('"')) {
      value = value.slice(1, -1);
    }
    try {
      out[name] = decodeURIComponent(value);
    } catch {
      out[name] = value;
    }
  }
  return out;
}

/**
 * Build a Set-Cookie value for the session cookie.
 * opts.maxAge defaults to 7 days.
 */
export function serializeSessionCookie(value, opts = {}) {
  const maxAge = typeof opts.maxAge === 'number' ? opts.maxAge : 60 * 60 * 24 * 7;
  // Note: We do not URL-encode the value because our cookie value only contains
  // base64url chars and a dot — all safe per RFC 6265 cookie-octet rules.
  return [
    `mv_session=${value}`,
    'Path=/',
    'HttpOnly',
    'Secure',
    'SameSite=Lax',
    `Max-Age=${maxAge}`,
  ].join('; ');
}

/**
 * Build a Set-Cookie value that immediately clears the session cookie.
 * All non-value attributes must match how the cookie was set so the browser
 * actually overwrites it.
 */
export function serializeClearCookie() {
  return [
    'mv_session=',
    'Path=/',
    'HttpOnly',
    'Secure',
    'SameSite=Lax',
    'Max-Age=0',
    'Expires=Thu, 01 Jan 1970 00:00:00 GMT',
  ].join('; ');
}

/**
 * Convenience: extract & verify the session payload from a Request, given the
 * secret. Returns the payload object on success or null on failure.
 * (Returns null silently when the cookie is missing — callers decide how to
 * react. This helper does NOT throw on a missing secret because the middleware
 * already handles that case with a 500.)
 */
export async function readSessionFromRequest(request, secret) {
  if (!secret) return null;
  const cookies = parseCookies(request.headers.get('Cookie'));
  const raw = cookies['mv_session'];
  if (!raw) return null;
  return verifySession(raw, secret);
}
