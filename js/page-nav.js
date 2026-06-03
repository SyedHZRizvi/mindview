// js/page-nav.js
// Universal page-nav widget. Injects a sticky button bar just below the
// main navbar on every HTML page (auto-injected by functions/_middleware.js
// HTMLRewriter alongside content-protection.js and role-gated.js).
//
// Three buttons:
//   1. "← Back"      — browser history.back() (returns to whatever page
//                      brought the user here)
//   2. "Back to course" — context-aware. If the current URL is inside a
//                      course context (course landing, chapter page,
//                      curriculum sub-page, or any /assessments/{code}/…
//                      flat or directory layout), links to the course's
//                      main landing page. Otherwise hidden.
//   3. "Forward →"   — browser history.forward() (advance one step)
//
// Owner-approved 2026-06-01.

(function () {
  'use strict';

  // Skip injection on login pages and any small-chrome contexts where the
  // page-nav would be inappropriate. Login pages already block the rest of
  // the chrome too.
  var SKIP_PATHS = [
    '/login',
    '/admin/login',
    '/admin/login.html',
  ];
  var here = location.pathname.replace(/\/$/, '') || '/';
  if (SKIP_PATHS.indexOf(here) !== -1) return;

  // Detect "course context" — what should the "Back to course" button do?
  // Returns null if no course context, or { code: 'mcr3u', href: '/courses/mcr3u.html' }
  function detectCourseContext(pathname) {
    var patterns = [
      // /courses/{code}/ch{N}.html or /courses/{code}/...
      // (chapter pages, anything inside the course folder — EXCLUDES the
      // landing page itself which lives at /courses/{code}.html)
      /^\/courses\/([a-z0-9]+)\/.+$/i,
      // /courses/{code}_curriculum.html
      /^\/courses\/([a-z0-9]+)_curriculum\.html$/i,
      // /assessments/{code}/...  (directory layout)
      /^\/assessments\/([a-z0-9]+)\/.+$/i,
      // /assessments/{code}_ch{N}_{as|for|of}.html  (flat layout)
      /^\/assessments\/([a-z0-9]+)_ch\d+_(?:as|for|of)\.html$/i,
      // /assessments/{code}_final_exam.html  (flat layout)
      /^\/assessments\/([a-z0-9]+)_final_exam\.html$/i,
    ];
    for (var i = 0; i < patterns.length; i++) {
      var m = pathname.match(patterns[i]);
      if (m) {
        var code = m[1].toLowerCase();
        return { code: code, href: '/courses/' + code + '.html' };
      }
    }
    return null;
  }

  function createPageNav() {
    var ctx = detectCourseContext(location.pathname);

    var nav = document.createElement('div');
    nav.className = 'page-nav';
    nav.setAttribute('role', 'navigation');
    nav.setAttribute('aria-label', 'Page navigation');

    // Inline-style fallback in case style.css hasn't loaded yet
    nav.style.cssText = [
      'background:#fff',
      'border-bottom:1px solid #e2e8f0',
      'padding:10px 18px',
      'display:flex',
      'gap:10px',
      'align-items:center',
      'justify-content:center',
      'position:sticky',
      'top:0',
      'z-index:90',
      'box-shadow:0 1px 4px rgba(15,23,42,0.05)',
    ].join(';');

    // Back button — history.back()
    var back = document.createElement('button');
    back.type = 'button';
    back.className = 'page-nav-btn page-nav-back';
    back.title = 'Go back to the previous page';
    back.setAttribute('aria-label', 'Back');
    back.innerHTML = '<span aria-hidden="true">←</span>&nbsp;Back';
    back.onclick = function () {
      if (window.history.length > 1) {
        window.history.back();
      } else {
        location.href = '/';
      }
    };

    // Context-aware "Back to course" link (hidden when no course context)
    var course = document.createElement('a');
    course.className = 'page-nav-btn page-nav-course';
    course.title = ctx ? 'Back to ' + ctx.code.toUpperCase() + ' main page' : '';
    if (ctx) {
      course.href = ctx.href;
      course.innerHTML = '📘&nbsp;Back to ' + ctx.code.toUpperCase();
    } else {
      // Hide gracefully when there's no course context (home, catalog,
      // enrolment, resources, admin pages, etc.)
      course.style.display = 'none';
    }

    // Forward button — history.forward()
    var fwd = document.createElement('button');
    fwd.type = 'button';
    fwd.className = 'page-nav-btn page-nav-forward';
    fwd.title = 'Go forward one step';
    fwd.setAttribute('aria-label', 'Forward');
    fwd.innerHTML = 'Forward&nbsp;<span aria-hidden="true">→</span>';
    fwd.onclick = function () {
      window.history.forward();
    };

    nav.appendChild(back);
    if (ctx) nav.appendChild(course);
    nav.appendChild(fwd);
    return nav;
  }

  function insertPageNav() {
    if (document.querySelector('.page-nav')) return;  // idempotent

    var nav = createPageNav();

    // ── Always-visible strategy ────────────────────────────────────────
    // Use position:fixed so the bar is pinned to the viewport and NEVER
    // scrolls away, no matter how far down the page the user goes.
    // We dynamically set `top` to the navbar's bottom edge so the bar
    // sits flush underneath it. A ResizeObserver keeps it correct if the
    // navbar ever changes height (e.g. on mobile breakpoints).
    // A matching padding-top is applied to <body> so no page content is
    // hidden behind the combined navbar + page-nav strip.

    var topNav = document.querySelector('nav.navbar');

    function pinBelowNavbar() {
      var navH = topNav ? topNav.getBoundingClientRect().height : 0;
      nav.style.top = navH + 'px';
      // Keep body padding so content doesn't hide under the two fixed bars
      var pageNavH = nav.getBoundingClientRect().height || 46;
      document.body.style.paddingTop = (navH + pageNavH) + 'px';
    }

    // Append to <body> so fixed positioning is relative to the viewport
    document.body.appendChild(nav);
    pinBelowNavbar();

    // Stay correct if the window is resized
    window.addEventListener('resize', pinBelowNavbar);

    // Use ResizeObserver if available (modern browsers) for accuracy
    if (window.ResizeObserver && topNav) {
      new ResizeObserver(pinBelowNavbar).observe(topNav);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', insertPageNav);
  } else {
    insertPageNav();
  }
})();
