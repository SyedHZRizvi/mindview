// Cloudflare Pages Function — /api/me
const ROLE_RANK = { student: 0, teacher: 1, admin: 2, superuser: 3 };
const ROLE_LABELS = { student: 'Student', teacher: 'Teacher', admin: 'Administrator', superuser: 'Super User' };

function highestRole(rolesArr) {
  const roles = Array.isArray(rolesArr) ? rolesArr : [];
  if (roles.length === 0) return 'student';
  return roles.reduce((best, r) => ((ROLE_RANK[r] ?? -1) > (ROLE_RANK[best] ?? -1) ? r : best), 'student');
}

export async function onRequest(context) {
  const headers = { 'Content-Type': 'application/json' };
  const jwt = context.request.headers.get('Cf-Access-Jwt-Assertion');
  if (!jwt) return new Response(JSON.stringify({ authenticated: false }), { headers });
  try {
    const [, payloadB64] = jwt.split('.');
    const payload = JSON.parse(atob(payloadB64));
    const roles = payload.roles || payload['custom:roles'] || [];
    const roleArr = Array.isArray(roles) ? roles : [roles];
    const role = highestRole(roleArr);
    return new Response(JSON.stringify({
      authenticated: true,
      user: { id: payload.sub, email: payload.email, full_name: payload.name || payload.email, role, role_label: ROLE_LABELS[role] || role, can_manage_users: role === 'admin' || role === 'superuser' }
    }), { headers });
  } catch {
    return new Response(JSON.stringify({ authenticated: false }), { headers });
  }
}
