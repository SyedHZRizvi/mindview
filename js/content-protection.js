// js/content-protection.js
// Casual content-protection for non-superuser visitors.
//
// Default state on parse: PROTECTED (fail-closed). After /api/me confirms the
// current user has role === 'superuser', we flip an `unlocked` flag and remove
// the body.mv-protected class so selection/copy/etc. work normally. If /api/me
// errors or returns anything else, we stay protected.
//
// Skips entirely on the login pages so users can paste their password.
// Inside form fields (<input>, <textarea>, [contenteditable]), text input,
// selection, and paste are ALWAYS allowed so login + admin forms keep working.
// We still block Cmd/Ctrl+P and Cmd/Ctrl+S inside form fields (no point letting
// a savvy user print/save the page from a focused input).

(function () {
  'use strict';

  // ---- 1. Self-skip on login pages -----------------------------------------
  var LOGIN_PATHS = ['/login', '/admin/login', '/admin/login.html'];
  var pathname = (location && location.pathname) || '';
  // Normalize trailing slash (except root).
  var normPath = pathname;
  if (normPath.length > 1 && normPath.charAt(normPath.length - 1) === '/') {
    normPath = normPath.slice(0, -1);
  }
  if (LOGIN_PATHS.indexOf(normPath) !== -1) {
    return;
  }

  // ---- 2. Closure-scoped lock flag (every handler reads this) --------------
  var unlocked = false;

  // ---- 3. Inject the CSS rules --------------------------------------------
  function injectStyle() {
    if (document.getElementById('mv-protection-style')) return;
    var style = document.createElement('style');
    style.id = 'mv-protection-style';
    style.textContent = [
      'body.mv-protected, body.mv-protected * {',
      '  -webkit-user-select: none !important;',
      '  -moz-user-select: none !important;',
      '  -ms-user-select: none !important;',
      '  user-select: none !important;',
      '  -webkit-touch-callout: none !important;',
      '}',
      'body.mv-protected input,',
      'body.mv-protected textarea,',
      'body.mv-protected select,',
      'body.mv-protected [contenteditable],',
      'body.mv-protected [contenteditable] * {',
      '  -webkit-user-select: text !important;',
      '  -moz-user-select: text !important;',
      '  -ms-user-select: text !important;',
      '  user-select: text !important;',
      '  -webkit-touch-callout: default !important;',
      '}',
      'body.mv-protected img {',
      '  -webkit-user-drag: none !important;',
      '  user-drag: none !important;',
      '  -webkit-touch-callout: none !important;',
      '}',
      '@media print {',
      '  body.mv-protected { display: none !important; }',
      '}'
    ].join('\n');
    // Try head first; if not parsed yet, fall back to documentElement.
    (document.head || document.documentElement).appendChild(style);
  }

  if (document.head || document.documentElement) {
    injectStyle();
  } else {
    document.addEventListener('DOMContentLoaded', injectStyle, { once: true });
  }

  // ---- 4. Add body.mv-protected ASAP --------------------------------------
  function applyProtectedClass() {
    if (document.body && !document.body.classList.contains('mv-protected')) {
      document.body.classList.add('mv-protected');
    }
  }
  if (document.body) {
    applyProtectedClass();
  } else {
    document.addEventListener('DOMContentLoaded', applyProtectedClass, { once: true });
  }

  // ---- 5. Helpers ----------------------------------------------------------
  function isFormField(el) {
    if (!el || el.nodeType !== 1) return false;
    var tag = (el.tagName || '').toUpperCase();
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return true;
    // contenteditable can be 'true' or '' or inherited; closest() catches the tree.
    if (typeof el.closest === 'function') {
      if (el.closest('input,textarea,select,[contenteditable=""],[contenteditable="true"]')) {
        return true;
      }
    }
    // Fallback for older browsers.
    var node = el;
    while (node && node.nodeType === 1) {
      if (node.isContentEditable) return true;
      node = node.parentNode;
    }
    return false;
  }

  function eventTarget(e) {
    // composedPath() picks up shadow DOM; fall back to target.
    if (typeof e.composedPath === 'function') {
      var path = e.composedPath();
      if (path && path.length) return path[0];
    }
    return e.target;
  }

  // ---- 6. Block events (capture-phase so we beat page handlers) ----------
  function blockIfLocked(e) {
    if (unlocked) return;
    if (isFormField(eventTarget(e))) return;
    e.preventDefault();
    e.stopPropagation();
  }

  // contextmenu / copy / cut / dragstart / selectstart — block outside form fields.
  ['contextmenu', 'copy', 'cut', 'dragstart', 'selectstart'].forEach(function (type) {
    document.addEventListener(type, blockIfLocked, true);
  });

  // paste — block outside form fields (so login password paste still works).
  document.addEventListener('paste', function (e) {
    if (unlocked) return;
    if (isFormField(eventTarget(e))) return;
    e.preventDefault();
    e.stopPropagation();
  }, true);

  // keydown — devtools / view-source / print / save / copy shortcuts.
  document.addEventListener('keydown', function (e) {
    if (unlocked) return;

    var inField = isFormField(eventTarget(e));
    var mod = e.ctrlKey || e.metaKey;
    var key = (e.key || '').toLowerCase();

    // Inside form fields we ONLY block Cmd/Ctrl+P and Cmd/Ctrl+S, so that
    // typing, paste, select-all, etc. continue to work in the login form.
    if (inField) {
      if (mod && !e.shiftKey && !e.altKey && (key === 'p' || key === 's')) {
        e.preventDefault();
        e.stopPropagation();
      }
      return;
    }

    // F12 — devtools.
    if (key === 'f12') {
      e.preventDefault();
      e.stopPropagation();
      return;
    }

    // Cmd/Ctrl + Shift + I/J/C — devtools / inspect.
    if (mod && e.shiftKey && (key === 'i' || key === 'j' || key === 'c')) {
      e.preventDefault();
      e.stopPropagation();
      return;
    }

    // Cmd/Ctrl + (C, X, V, A, P, S, U) — copy/cut/paste/select-all/print/save/view-source.
    if (mod && !e.shiftKey && !e.altKey) {
      if (key === 'c' || key === 'x' || key === 'v' ||
          key === 'a' || key === 'p' || key === 's' || key === 'u') {
        e.preventDefault();
        e.stopPropagation();
        return;
      }
    }
  }, true);

  // ---- 7. Neuter window.print while protected ----------------------------
  try {
    var nativePrint = window.print;
    window.print = function () {
      if (unlocked && typeof nativePrint === 'function') {
        return nativePrint.apply(window, arguments);
      }
      // no-op while protected
    };
  } catch (_) {
    // Some browsers may not let us reassign; ignore.
  }

  // ---- 8. Check /api/me; unlock for superuser only -----------------------
  function unlock() {
    unlocked = true;
    if (document.body) {
      document.body.classList.remove('mv-protected');
    }
  }

  try {
    fetch('/api/me', { credentials: 'same-origin', cache: 'no-store' })
      .then(function (resp) {
        if (!resp || !resp.ok) return null;
        return resp.json().catch(function () { return null; });
      })
      .then(function (data) {
        if (!data) return; // stay protected
        if (data.authenticated === true &&
            data.user &&
            data.user.role === 'superuser') {
          unlock();
        }
        // else: stay protected (default).
      })
      .catch(function () {
        // Network/parse error — fail closed, stay protected.
      });
  } catch (_) {
    // fetch unavailable — stay protected.
  }
})();
