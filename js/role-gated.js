// js/role-gated.js
// Role-gated visibility for instructor-only content (answer keys, solutions,
// rubrics) inside assessment HTML files.
//
// Default state on parse: HIDDEN (fail-closed). The IIFE adds class
// `role-unknown` to <html> the moment this script is parsed (deferred at end
// of <head>, before <body> elements paint), so any `.instructor-only`
// elements are already hidden by CSS when the page renders.
//
// After /api/me confirms an instructor (teacher / admin / superuser), we
// remove `role-unknown` and add `role-instructor` to <html>, which reveals
// the gated content. Otherwise (student or unauthenticated, or any fetch
// error), we add `role-student` and scrub the gated content out of the DOM
// entirely so that view-source / devtools (where allowed by content-
// protection.js) won't reveal answers either.
//
// This script is independent of content-protection.js. It self-skips on the
// login pages so admin/login forms aren't affected.
//
// Required server contract: /api/me responds 200 with JSON
//   { authenticated: true,  user: { role: "student"|"teacher"|"admin"|"superuser", ... } }
//   { authenticated: false }
// on auth failure (it's allow-listed in the middleware so it never returns
// 401 during this check).

(function () {
  'use strict';

  // ---- 1. Self-skip on login pages -----------------------------------------
  var LOGIN_PATHS = ['/login', '/admin/login', '/admin/login.html'];
  var pathname = (location && location.pathname) || '';
  var normPath = pathname;
  if (normPath.length > 1 && normPath.charAt(normPath.length - 1) === '/') {
    normPath = normPath.slice(0, -1);
  }
  if (LOGIN_PATHS.indexOf(normPath) !== -1) {
    return;
  }

  // ---- 2. Inject the gating CSS as early as possible -----------------------
  // Rules:
  //   html.role-unknown    .instructor-only { display: none !important; }
  //   html.role-student    .instructor-only { display: none !important; }
  //   html.role-instructor .instructor-only::before { (banner) }
  function injectStyle() {
    if (document.getElementById('mv-role-gated-style')) return;
    var style = document.createElement('style');
    style.id = 'mv-role-gated-style';
    style.textContent = [
      '/* While role is unknown, hide instructor-only content so it does not flash on slow networks */',
      'html.role-unknown .instructor-only { display: none !important; }',
      '/* Permanently hide from students */',
      'html.role-student .instructor-only { display: none !important; }',
      '/* Instructor sees a small banner indicating elevated visibility */',
      'html.role-instructor .instructor-only::before {',
      '  content: "🔒 Instructor-only content below";',
      '  display: block;',
      '  font-size: 12px;',
      '  color: #b91c1c;',
      '  font-weight: 700;',
      '  padding: 4px 10px;',
      '  background: #fee2e2;',
      '  border-radius: 6px;',
      '  margin-bottom: 8px;',
      '}'
    ].join('\n');
    (document.head || document.documentElement).appendChild(style);
  }
  if (document.head || document.documentElement) {
    injectStyle();
  } else {
    document.addEventListener('DOMContentLoaded', injectStyle, { once: true });
  }

  // ---- 3. Tag <html> with role-unknown ASAP -------------------------------
  function setRoleClass(cls) {
    var html = document.documentElement;
    if (!html) return;
    html.classList.remove('role-unknown');
    html.classList.remove('role-student');
    html.classList.remove('role-instructor');
    html.classList.add(cls);
  }
  // Default to role-unknown immediately so CSS hides instructor-only content
  // even before /api/me resolves.
  if (document.documentElement) {
    document.documentElement.classList.add('role-unknown');
  } else {
    document.addEventListener('DOMContentLoaded', function () {
      document.documentElement.classList.add('role-unknown');
    }, { once: true });
  }

  // ---- 4. DOM scrub for students (defense in depth) -----------------------
  // Remove the actual answer-key content from the DOM so a student can't
  // view-source the page to see the answers. We do this only for the student
  // (or unauthenticated) case.
  function scrubInstructorContent() {
    try {
      var nodes = document.querySelectorAll('.instructor-only');
      for (var i = 0; i < nodes.length; i++) {
        var n = nodes[i];
        // For <details class="instructor-only">: remove the element entirely.
        if (n.tagName && n.tagName.toLowerCase() === 'details') {
          if (n.parentNode) n.parentNode.removeChild(n);
        } else {
          // For other containers: clear innerHTML so the wrapper stays for
          // any layout consequences but the actual answer text is gone.
          n.innerHTML = '';
        }
      }
    } catch (_) {
      // Best effort. If DOM isn't ready, we run again at DOMContentLoaded.
    }
  }

  function applyStudent() {
    setRoleClass('role-student');
    if (document.body) {
      scrubInstructorContent();
    } else {
      document.addEventListener('DOMContentLoaded', scrubInstructorContent, { once: true });
    }
  }

  function applyInstructor() {
    setRoleClass('role-instructor');
    // No DOM scrub; the CSS rule plus the banner pseudo-element reveals
    // the content for instructors.
  }

  // ---- 5. Fetch /api/me and decide role -----------------------------------
  function isInstructorRole(role) {
    return role === 'teacher' || role === 'admin' || role === 'superuser';
  }

  try {
    fetch('/api/me', { credentials: 'same-origin', cache: 'no-store' })
      .then(function (resp) {
        if (!resp || !resp.ok) return null;
        return resp.json().catch(function () { return null; });
      })
      .then(function (data) {
        if (!data) {
          // No JSON / network error — fail closed.
          applyStudent();
          return;
        }
        if (data.authenticated === true &&
            data.user &&
            isInstructorRole(data.user.role)) {
          applyInstructor();
        } else {
          applyStudent();
        }
      })
      .catch(function () {
        // Network / parse error — fail closed.
        applyStudent();
      });
  } catch (_) {
    // fetch unavailable — fail closed.
    applyStudent();
  }
})();
