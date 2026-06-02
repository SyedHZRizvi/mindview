// functions/_middleware.js
// Runs for every request handled by Pages Functions (i.e. every HTML page
// AND every /api/* call — static-asset requests served directly from the
// edge cache also pass through here on cache miss).
//
// Behavior:
//   - Pass-through (no auth gate) for: /login, /api/login, /api/logout,
//     /api/bootstrap, /api/me, /logo.png, and any path with a static-asset
//     extension (.css .js .png .jpg .jpeg .gif .svg .webp .ico .woff .woff2
//     .ttf .map). Note that /js/content-protection.js is covered by the .js
//     extension rule, so the login page can fetch it unauthenticated (the
//     script self-skips on the login pages anyway).
//   - For everything else: require a valid mv_session cookie. If missing/
//     invalid, 302 to /login?next=<encoded original URL>.
//   - If SESSION_SECRET is unset, return 500 with a clear error so the owner
//     notices in dev/prod instead of silently allowing traffic through.
//   - For HTML responses (content-type starts with text/html) on any path
//     other than the login pages, inject
//       <script src="/js/content-protection.js" defer></script>
//       <script src="/js/role-gated.js" defer></script>
//     at the end of <head> via HTMLRewriter. This applies to public paths
//     too (e.g. the index page), so both scripts are always loaded. The two
//     scripts are independent and complementary: content-protection disables
//     copy/paste/etc for non-superusers; role-gated hides .instructor-only
//     content (answer keys, solutions, rubrics) from students.

import { readSessionFromRequest } from './lib/session.js';

// Paths that are always allowed through without a valid session.
// Note: trailing slashes are normalized away before matching.
const PUBLIC_EXACT = new Set([
  '/login',
  '/admin/login',       // Cloudflare Pages strips .html — destination of the /login rewrite
  '/admin/login.html',  // direct hit (if anyone links to it explicitly)
  '/api/login',
  '/api/logout',
  '/api/bootstrap',
  '/api/me',
  '/logo.png',
  // Public policy pages — referenced from the home-page footer, intended
  // to be readable without a login (legal compliance + prospective-
  // student transparency).
  '/video-policy',
  '/video-policy.html',
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

// Paths where we deliberately do NOT inject the content-protection script.
// The script self-skips on these too, but skipping the inject avoids a
// pointless network fetch on the login screen.
const NO_INJECT_PATHS = new Set([
  '/login',
  '/admin/login',
  '/admin/login.html',
]);

function shouldInject(pathname) {
  let p = pathname;
  if (p.length > 1 && p.endsWith('/')) p = p.slice(0, -1);
  return !NO_INJECT_PATHS.has(p);
}

// Wrap a downstream Response: if it's an HTML response, inject the
// content-protection AND role-gated script tags at the end of <head> via
// HTMLRewriter. Non-HTML responses (JSON, CSS, JS, images, redirects, 401s,
// etc.) are returned unchanged.
//
// The two scripts are independent and complementary:
//   - content-protection.js disables copy/paste/right-click/etc for
//     non-superusers (educational integrity for the lesson notes).
//   - role-gated.js hides .instructor-only content (answer keys, solutions,
//     rubrics) from students — only teachers / admins / superusers can see
//     it. Loaded together so both apply on every page.
function withProtectionInjected(response, pathname) {
  if (!response) return response;
  if (!shouldInject(pathname)) return response;
  const ct = response.headers.get('content-type') || '';
  if (!ct.toLowerCase().includes('text/html')) return response;
  return new HTMLRewriter()
    .on('head', {
      element(el) {
        el.append(
          '<script src="/js/content-protection.js" defer></script>',
          { html: true }
        );
        el.append(
          '<script src="/js/role-gated.js" defer></script>',
          { html: true }
        );
      },
    })
    .transform(response);
}

// Friendly "you're not enrolled in this course yet" landing page. Rendered
// by the middleware (NOT by an HTML file in /enrolment/) so it works for
// every blocked URL without needing per-course redirects. Course display
// names are kept in sync with the home-page layout — when adding a new
// course, update this map AND scripts/_rebuild_index_grid.py's LAYOUT.
const COURSE_DISPLAY_NAMES = {
  mcr3u: 'MCR3U — Functions (Grade 11)',
  mhf4u: 'MHF4U — Advanced Functions (Grade 12)',
  mcv4u: 'MCV4U — Calculus and Vectors (Grade 12)',
  mdm4u: 'MDM4U — Mathematics of Data Management (Grade 12)',
  mct3m: 'MCT3M — Mathematics for College Technology (Grade 11)',
  mct4m: 'MCT4M — Mathematics for College Technology (Grade 12)',
  snc2d: 'SNC2D — Science Academic (Grade 10)',
  sbi3u: 'SBI3U — Biology (Grade 11)',
  sbi4u: 'SBI4U — Biology (Grade 12)',
  sch3u: 'SCH3U — Chemistry (Grade 11)',
  sch4u: 'SCH4U — Chemistry (Grade 12)',
  sph3u: 'SPH3U — Physics (Grade 11)',
  sph4u: 'SPH4U — Physics (Grade 12)',
  eng2d: 'ENG2D — English Academic (Grade 10)',
  eng3u: 'ENG3U — English (Grade 11)',
  eng4u: 'ENG4U — English (Grade 12)',
  ics3u: 'ICS3U — Introduction to Computer Science (Grade 11)',
  ics4u: 'ICS4U — Computer Science (Grade 12)',
  chv2o: 'CHV2O — Civics and Citizenship (Grade 10)',
  cpc3o: 'CPC3O — Politics in Action: Making Change (Grade 11)',
  cpw4u: 'CPW4U — Canadian and World Politics (Grade 12)',
  chc2d: 'CHC2D — Canadian History since World War I (Grade 10)',
  chw3m: 'CHW3M — World History to the Sixteenth Century (Grade 11)',
  chy4u: 'CHY4U — World History since the Fifteenth Century (Grade 12)',
  clu3m: 'CLU3M — Understanding Canadian Law (Grade 11)',
  cln4u: 'CLN4U — Canadian and International Law (Grade 12)',
  cgf3m: 'CGF3M — Physical Geography (Grade 11)',
  cgw4u: 'CGW4U — World Issues: A Geographic Analysis (Grade 12)',
  baf3m: 'BAF3M — Financial Accounting Fundamentals (Grade 11)',
  bat4m: 'BAT4M — Financial Accounting Principles (Grade 12)',
  bbb4m: 'BBB4M — International Business Fundamentals (Grade 12)',
  boh4m: 'BOH4M — Business Leadership: Management Fundamentals (Grade 12)',
  hfn3m: 'HFN3M — Nutrition and Health (Grade 11)',
  hfa4m: 'HFA4M — Nutrition and Health Issues (Grade 12)',
  hsc4m: 'HSC4M — World Cultures (Grade 12)',
  glc2o: 'GLC2O — Career Studies (Grade 10)',
  gwl3o: 'GWL3O — Designing Your Future (Grade 11)',
  gpp3o: 'GPP3O — Leadership and Peer Support (Grade 11)',
  gle3o: 'GLE3O — Advanced Learning Strategies (Grade 11)',
  gle4o: 'GLE4O — Advanced Learning Strategies: After Secondary School (Grade 12)',
};

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}

function renderEnrolmentRequiredHTML(courseCode, studentEmail) {
  const displayName = COURSE_DISPLAY_NAMES[courseCode]
    || courseCode.toUpperCase();
  const landingHref = `/courses/${encodeURIComponent(courseCode)}.html`;
  const safeName = escapeHtml(displayName);
  const safeEmail = escapeHtml(studentEmail || '');
  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Enrolment required — ${safeName}</title>
<style>
*{margin:0;padding:0;box-sizing:border-box;}
body{font-family:'Segoe UI',system-ui,sans-serif;background:#f8fafc;color:#1e293b;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:24px;}
.card{background:#fff;border:1px solid #e2e8f0;border-radius:14px;max-width:560px;width:100%;padding:42px 36px;box-shadow:0 4px 18px rgba(15,23,42,0.06);}
.icon{font-size:48px;margin-bottom:14px;}
h1{font-size:24px;font-weight:800;margin-bottom:10px;color:#0f172a;}
.course-line{display:inline-block;background:#fef3c7;color:#78350f;padding:6px 12px;border-radius:8px;font-weight:700;font-size:14px;margin-bottom:18px;}
p{color:#475569;line-height:1.6;margin-bottom:14px;}
.steps{background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:18px 22px;margin:18px 0;}
.steps ol{padding-left:22px;}
.steps li{margin-bottom:6px;color:#334155;}
.actions{display:flex;gap:10px;margin-top:22px;flex-wrap:wrap;}
.btn{display:inline-block;padding:10px 18px;border-radius:8px;font-size:14px;font-weight:600;text-decoration:none;border:1px solid transparent;}
.btn.primary{background:#2563eb;color:#fff;}
.btn.primary:hover{background:#1d4ed8;}
.btn.ghost{background:#fff;color:#475569;border-color:#e2e8f0;}
.btn.ghost:hover{border-color:#94a3b8;}
.email-note{font-size:13px;color:#64748b;margin-top:18px;border-top:1px solid #e2e8f0;padding-top:14px;}
.email-note a{color:#2563eb;font-weight:600;text-decoration:none;}
</style>
</head>
<body>
<div class="card">
  <div class="icon">🔒</div>
  <h1>Enrolment required to view this content</h1>
  <div class="course-line">${safeName}</div>
  <p>You're signed in, but you haven't been enrolled in this course yet. The lessons, videos, and assessments for this course are reserved for enrolled students.</p>
  <div class="steps">
    <strong style="display:block;margin-bottom:8px;color:#0f172a;">To get access:</strong>
    <ol>
      <li>Decide which courses you'd like to add.</li>
      <li>Email an administrator with your name, account email, and the courses you want to enrol in.</li>
      <li>An admin will update your account; refresh this page once you're enrolled.</li>
    </ol>
  </div>
  <div class="actions">
    <a class="btn ghost" href="${landingHref}">← Back to course overview</a>
    <a class="btn ghost" href="/">All courses</a>
  </div>
  <p class="email-note">Signed in as <a href="/api/logout">${safeEmail}</a>. See the home page <a href="/#enrolment">Enrolment &amp; Tuition</a> section for fees and contact information.</p>
</div>
</body>
</html>`;
}

export async function onRequest(context) {
  const { request, env, next } = context;
  const url = new URL(request.url);

  // Always allow CORS preflights through unscathed.
  if (request.method === 'OPTIONS') return next();

  if (isPublic(url.pathname)) {
    // Public path (login page, /api/me, static assets, index, etc.) — still
    // inject the protection script if the response turns out to be HTML.
    const res = await next();
    return withProtectionInjected(res, url.pathname);
  }

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
    // Per-student course-enrolment gate. If the requester is a student AND
    // they're trying to access content INSIDE a course folder (chapters,
    // lessons, assessments — but NOT the landing page /courses/{code}.html),
    // verify they're enrolled in that course. Other roles bypass this check.
    if (payload.role === 'student') {
      const m = url.pathname.match(/^\/courses\/([a-z0-9]+)\/(.+)$/i);
      if (m) {
        const courseCode = m[1].toLowerCase();
        let enrolled = [];
        if (env.USERS_KV) {
          try {
            const rec = await env.USERS_KV.get(payload.sub, { type: 'json' });
            if (rec && Array.isArray(rec.enrolled_courses)) {
              enrolled = rec.enrolled_courses;
            }
          } catch {
            // KV error → fail closed: treat as not enrolled.
          }
        }
        if (!enrolled.includes(courseCode)) {
          return new Response(
            renderEnrolmentRequiredHTML(courseCode, payload.email),
            {
              status: 200,  // 200 so the user sees the page; the body explains
              headers: {
                'Content-Type': 'text/html; charset=utf-8',
                'Cache-Control': 'no-store',
              },
            }
          );
        }
      }
    }
    // Authenticated (and, for students, enrolled in this course's content
    // OR not browsing course content). Let downstream handler / static asset
    // serve, then inject the protection script into any HTML response.
    const res = await next();
    return withProtectionInjected(res, url.pathname);
  }

  // Not authenticated. For HTML / page navigations, redirect to /login with
  // a `next` param so the login page can bounce back. For API calls, return
  // 401 JSON so XHR / fetch callers can react without a confusing 302.
  // (Neither of these is an HTML body, so no injection here.)
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
