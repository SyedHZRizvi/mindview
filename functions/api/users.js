const ROLE_RANK = { student: 0, teacher: 1, admin: 2, superuser: 3 };
const ALL_ROLES = ['student', 'teacher', 'admin', 'superuser'];

function json(status, body) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}

function highestRole(rolesArr) {
  const roles = Array.isArray(rolesArr) ? rolesArr : [];
  if (roles.length === 0) return 'student';
  return roles.reduce((best, r) => ((ROLE_RANK[r] ?? -1) > (ROLE_RANK[best] ?? -1) ? r : best), 'student');
}

function canManageRole(actorRole, targetRole) {
  if (actorRole === 'superuser') return true;
  if (actorRole === 'admin') return targetRole === 'teacher' || targetRole === 'student';
  return false;
}

function getActorFromRequest(request) {
  const jwt = request.headers.get('Cf-Access-Jwt-Assertion');
  if (!jwt) return null;
  try {
    const [, payloadB64] = jwt.split('.');
    const payload = JSON.parse(atob(payloadB64));
    const roles = payload.roles || payload['custom:roles'] || [];
    const roleArr = Array.isArray(roles) ? roles : [roles];
    return { sub: payload.sub, email: payload.email, role: highestRole(roleArr) };
  } catch { return null; }
}

export async function onRequest(context) {
  const { request, env } = context;
  const actor = getActorFromRequest(request);
  if (!actor) return json(401, { error: 'Authentication required' });
  if (actor.role !== 'admin' && actor.role !== 'superuser') return json(403, { error: 'Insufficient permissions' });
  if (!env.USERS_KV) return json(503, { error: 'User store not configured. Bind a KV namespace named USERS_KV in Cloudflare Pages settings.' });

  const url = new URL(request.url);
  const targetId = url.searchParams.get('id');
  const method = request.method;

  if (method === 'GET' && !targetId) {
    const list = await env.USERS_KV.list();
    const users = await Promise.all(list.keys.map(async (k) => env.USERS_KV.get(k.name, 'json')));
    let filtered = users.filter(Boolean);
    if (actor.role === 'admin') filtered = filtered.filter(u => u.role === 'teacher' || u.role === 'student');
    return json(200, { users: filtered, actor_role: actor.role });
  }

  if (method === 'POST' && !targetId) {
    const body = await request.json();
    const { email, password, full_name, role } = body;
    if (!email || !password || !role) return json(400, { error: 'email, password, role are required' });
    if (!ALL_ROLES.includes(role)) return json(400, { error: 'Invalid role' });
    if (password.length < 8) return json(400, { error: 'Password must be at least 8 characters' });
    if (!canManageRole(actor.role, role)) return json(403, { error: `Your role cannot create ${role} users` });
    const id = crypto.randomUUID();
    const encoder = new TextEncoder();
    const hashBuffer = await crypto.subtle.digest('SHA-256', encoder.encode(password));
    const passwordHash = Array.from(new Uint8Array(hashBuffer)).map(b => b.toString(16).padStart(2, '0')).join('');
    const user = { id, email, full_name: full_name || '', role, passwordHash, created_at: new Date().toISOString() };
    await env.USERS_KV.put(id, JSON.stringify(user));
    return json(201, { ok: true, id });
  }

  if (!targetId) return json(400, { error: 'User id required (?id=<uuid>)' });
  const target = await env.USERS_KV.get(targetId, 'json');
  if (!target) return json(404, { error: 'User not found' });
  if (!canManageRole(actor.role, target.role)) return json(403, { error: `Cannot manage ${target.role} users` });

  if (method === 'PUT') {
    const body = await request.json();
    if (body.role && !ALL_ROLES.includes(body.role)) return json(400, { error: 'Invalid role' });
    if (body.role && !canManageRole(actor.role, body.role)) return json(403, { error: `Cannot promote to ${body.role}` });
    await env.USERS_KV.put(targetId, JSON.stringify({ ...target, ...body, id: targetId }));
    return json(200, { ok: true });
  }

  if (method === 'DELETE') {
    await env.USERS_KV.delete(targetId);
    return json(200, { ok: true });
  }

  return json(405, { error: 'Method not allowed' });
}
