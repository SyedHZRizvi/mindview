// functions/api/users.js
// Admin CRUD for users stored in USERS_KV.
//
// Auth: reads identity from the mv_session HttpOnly cookie via the shared
// session lib. Only admin and superuser may call this endpoint; admins may
// only manage student/teacher accounts, superusers may manage anyone.
//
// User-record shape (DO NOT change — preserved for KV compatibility):
//   { id, email, full_name, role, passwordHash, created_at }
// passwordHash = hex SHA-256 of password (no salt).
//
// TODO: Migrate passwordHash to PBKDF2-with-salt on next successful login.
// TODO: Add an "email:<lower>" -> id secondary index on create/update so login
//       no longer needs to scan the namespace.

import { readSessionFromRequest } from '../lib/session.js';

const ROLE_RANK = { student: 0, teacher: 1, admin: 2, superuser: 3 };
const ALL_ROLES = ['student', 'teacher', 'admin', 'superuser'];
const MIN_PW_LENGTH = 8;

function json(status, body) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' },
  });
}

function canManageRole(actorRole, targetRole) {
  if (actorRole === 'superuser') return true;
  if (actorRole === 'admin') return targetRole === 'teacher' || targetRole === 'student';
  return false;
}

async function sha256Hex(str) {
  const buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(str));
  return Array.from(new Uint8Array(buf))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

export async function onRequest(context) {
  const { request, env } = context;

  if (!env.SESSION_SECRET) {
    return json(500, {
      error: 'SESSION_SECRET is not configured. Set it as a Pages environment variable.',
    });
  }
  if (!env.USERS_KV) {
    return json(503, {
      error:
        'User store not configured. Bind a KV namespace named USERS_KV in Cloudflare Pages settings.',
    });
  }

  const session = await readSessionFromRequest(request, env.SESSION_SECRET);
  if (!session) return json(401, { error: 'Authentication required' });

  const actorRole = session.role;
  if (actorRole !== 'admin' && actorRole !== 'superuser') {
    return json(403, { error: 'Insufficient permissions' });
  }

  const url = new URL(request.url);
  const targetId = url.searchParams.get('id');
  const method = request.method;

  // ---------- LIST ----------
  if (method === 'GET' && !targetId) {
    const list = await env.USERS_KV.list();
    const users = await Promise.all(list.keys.map((k) => env.USERS_KV.get(k.name, 'json')));
    let filtered = users.filter(Boolean).map((u) => {
      // Never leak passwordHash to the client.
      const { passwordHash, ...safe } = u;
      return safe;
    });
    if (actorRole === 'admin') {
      filtered = filtered.filter((u) => u.role === 'teacher' || u.role === 'student');
    }
    return json(200, { users: filtered, actor_role: actorRole });
  }

  // ---------- CREATE ----------
  if (method === 'POST' && !targetId) {
    let body;
    try {
      body = await request.json();
    } catch {
      return json(400, { error: 'Invalid JSON body' });
    }
    const { email, password, full_name, role } = body || {};
    if (!email || !password || !role) {
      return json(400, { error: 'email, password, role are required' });
    }
    if (!ALL_ROLES.includes(role)) return json(400, { error: 'Invalid role' });
    if (typeof password !== 'string' || password.length < MIN_PW_LENGTH) {
      return json(400, { error: `Password must be at least ${MIN_PW_LENGTH} characters` });
    }
    if (!canManageRole(actorRole, role)) {
      return json(403, { error: `Your role cannot create ${role} users` });
    }
    const id = crypto.randomUUID();
    const passwordHash = await sha256Hex(password); // TODO: upgrade to PBKDF2+salt
    const user = {
      id,
      email,
      full_name: full_name || '',
      role,
      passwordHash,
      created_at: new Date().toISOString(),
    };
    await env.USERS_KV.put(id, JSON.stringify(user));
    return json(201, { ok: true, id });
  }

  // ---------- UPDATE / DELETE require ?id= ----------
  if (!targetId) return json(400, { error: 'User id required (?id=<uuid>)' });
  const target = await env.USERS_KV.get(targetId, 'json');
  if (!target) return json(404, { error: 'User not found' });
  if (!canManageRole(actorRole, target.role)) {
    return json(403, { error: `Cannot manage ${target.role} users` });
  }

  if (method === 'PUT') {
    let body;
    try {
      body = await request.json();
    } catch {
      return json(400, { error: 'Invalid JSON body' });
    }
    if (body.role && !ALL_ROLES.includes(body.role)) return json(400, { error: 'Invalid role' });
    if (body.role && !canManageRole(actorRole, body.role)) {
      return json(403, { error: `Cannot promote to ${body.role}` });
    }
    // If the caller is changing the password, hash it; otherwise keep existing.
    let updates = { ...body };
    if (typeof body.password === 'string' && body.password.length > 0) {
      if (body.password.length < MIN_PW_LENGTH) {
        return json(400, { error: `Password must be at least ${MIN_PW_LENGTH} characters` });
      }
      updates.passwordHash = await sha256Hex(body.password); // TODO: PBKDF2+salt
    }
    delete updates.password;
    // Never let the caller overwrite the immutable id from the body.
    await env.USERS_KV.put(targetId, JSON.stringify({ ...target, ...updates, id: targetId }));
    return json(200, { ok: true });
  }

  if (method === 'DELETE') {
    await env.USERS_KV.delete(targetId);
    return json(200, { ok: true });
  }

  return json(405, { error: 'Method not allowed' });
}
