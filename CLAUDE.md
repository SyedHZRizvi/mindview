# MindView Virtual Classroom — Baseline & Guardrails

**Frozen baseline:** commit `afe04b2` / git tag `baseline-2026-05-20`.
**Live URL:** https://mindview.pages.dev/
**Owner role for full access:** `superuser` (email-allowlisted in `USERS_KV`).

This file is read automatically by Claude Code at the start of every session
in this repo. **Future agents and humans must read this before changing
anything.** Its purpose is to lock the *state, structure, and visibility* of
the program as of today so that incremental work blends in without disturbing
what already works.

If a request would require breaking one of the rules below, **stop and ask
the owner first** — do not silently override.

---

## 1. Architecture (do not change without explicit approval)

The site is a **Cloudflare Pages** project deployed via **Direct Upload**
(not Git-connected; updates ship via `wrangler pages deploy`).

| Layer | Where | What it does |
|---|---|---|
| Auth | `functions/_middleware.js` | Gates every HTML request; 302 → `/login` if no valid session cookie |
| Auth | `functions/lib/session.js` | HMAC-SHA256 signed `mv_session` cookie helpers |
| Auth | `functions/api/login.js` | Email+password → cookie |
| Auth | `functions/api/logout.js` | Clear cookie |
| Auth | `functions/api/me.js` | Returns `{authenticated, user:{id,email,full_name,role,role_label,can_manage_users}}` |
| Auth | `functions/api/bootstrap.js` | One-shot seeder when KV is empty (locked after first user) |
| Admin | `functions/api/users.js` | CRUD over `USERS_KV` (admin+ only) |
| Content protection | `js/content-protection.js` | Injected via middleware into every HTML response; disables copy/paste/right-click/print for non-superusers |
| Auth UI | `admin/login.html` | Custom email+password form |
| Admin UI | `admin/dashboard.html`, `admin/users.html` | Role-based admin pages |
| Course pages | `courses/*.html` | 10 course landing pages |
| Curriculum cards | `courses/*_curriculum.html` | Ministry curriculum overview pages |
| Assessments | `assessments/{course}/Unit*_{AS,FOR,OF}.html` for science / vectors / English / CS; flat `{course}_chN_*.html` for MCR3U, MHF4U, MDM4U | Practice quizzes, diagnostics, unit tests |

### Cloudflare Pages bindings (DO NOT remove)
- `USERS_KV` — Workers KV namespace, holds user records
- `SESSION_SECRET` — Pages environment variable (Production + Preview),
  HMAC key for `mv_session` cookies. **If unset, middleware returns 500.**

### Pages env vars must contain at minimum
- `SESSION_SECRET` (Secret, encrypted)

---

## 2. Frozen UX patterns (additive changes only)

These are the visual conventions that have been deliberately settled. **Add
new things alongside; do not reorder, restyle, or remove the existing ones.**

### 2a. Header / nav
- Nav shows: brand logo on left, page links in centre, **user name + Logout**
  on the right.
- **No role pill** in the nav — role chip was deliberately removed.

### 2b. Course landing pages — fixed layout order
1. Top hero gradient with course code + title.
2. Chapter-pill quick-nav row.
3. **"Course Resources & Final Evaluation" block** — dark gradient header,
   two cards: 📋 Curriculum Document (left) + 🎓 Final Exam (right).
   **This block MUST appear before the first chapter section.**
4. Chapter sections (`<div class="unit-section">` each).
5. Inside each chapter section, **at the bottom**, a `<div class="assessment-strip">`
   with title "📊 Chapter N Assessments" and a 3-card grid in **THIS exact
   order**:
   - 🔄 **Practice Quiz — Assessment AS Learning** (cyan gradient)
   - 📋 **Diagnostic — Assessment FOR Learning** (amber gradient)
   - ✅ **Unit Test — Assessment OF Learning** (purple gradient)
6. Lesson-notes (`<details class="lesson-notes">`) inside each `topic-block`
   between the summary card and the video card.

### 2c. Manage Users page (`admin/users.html`)
- Top: user table with per-row Edit (self can edit) and Delete (not self).
- Bottom: **Role Reference matrix** — capabilities in rows, roles as
  columns in order **Super User → Administrator → Teacher → Student**.
- Rows grouped into 4 tiers (everyone / admin+ / superuser-only / nobody),
  separated by slate-300 dividers. Green ✓ on light-green, red ✗ on
  light-red.

### 2d. Authentication-related rules
- **Lock-out protection:** no user can change their own role; no user can
  delete their own account. The Edit modal disables the role field when
  `isMe`.
- **Bootstrap endpoint is single-use:** must return 403 once KV has any
  user. Do not re-enable `force_reset` or any other rescue flag in
  steady-state code.
- **Login page exemptions:** `/login`, `/admin/login`, `/admin/login.html`
  must always remain in `PUBLIC_EXACT` in `functions/_middleware.js`, and
  in `NO_INJECT_PATHS` for the content-protection script.

### 2e. Curriculum lesson notes (course pages)
- Every `topic-block` has a `<details class="lesson-notes">` block.
- Block contains: 600–1000 words including concept paragraphs, vocabulary
  list, 1-2 `<div class="worked-example">`, common-mistakes list, and a
  `<p class="curriculum-link">` citation.
- MathJax `\( \)` and `\[ \]` for math (NOT `\\(`).
- For CS pages, `<pre><code>` blocks (Python).

### 2f. Content protection
- Non-superusers cannot copy, select, right-click, drag-save, print, or use
  view-source shortcuts.
- Superusers retain full browser interactivity.
- The script self-skips on login pages (form fields must always accept paste).

---

## 3. Rules for future changes

### "Additive only" by default
- New features add **new** files, **new** blocks, **new** rows. Never rename
  existing files, never delete fields, never reorder UI without an explicit
  request from the owner naming the thing being reordered.
- Test new pages against the auth gate. They will be 302'd unless added to
  `PUBLIC_EXACT` (rare) or the user is signed in.

### Before modifying any of the following, ask first:
- `functions/_middleware.js` exempt lists
- `functions/api/users.js` permission checks
- `functions/api/bootstrap.js` lock condition
- The assessment-strip card order (AS → FOR → OF)
- The Role Reference matrix structure
- The Course Resources block position
- `js/content-protection.js` (security implication)
- `_redirects` rules
- Cookie attributes (`HttpOnly`, `Secure`, `SameSite`, `Path`, `Max-Age`)

### Safe-to-change without prior approval
- Adding a new course (follow the existing course-HTML template)
- Adding a new chapter to an existing course (must include AS/FOR/OF strip
  in the correct order)
- Adding lesson-notes to a topic that lacks them (use the existing
  `<details class="lesson-notes">` template)
- Replacing a broken YouTube video (verify via oEmbed before writing)
- Editing typos, fixing curriculum-citation phrasing
- Adding new admin pages (must include `/api/me` auth check)
- Adding new env vars in Pages settings

### Deploy procedure
```
# From repo root:
wrangler pages deploy . --project-name=mindview --branch=main --commit-dirty=true
```
Functions get bundled automatically when wrangler is run **from inside the
project directory** (`wrangler pages deploy .`). Running it with a path
argument from outside (`wrangler pages deploy /path/to/dir`) skips Functions
bundling — *don't do that*.

After every deploy, run `scripts/verify-baseline.py` to confirm invariants
hold.

### Database safety
- `USERS_KV` is the only source of truth for user identity. Don't wipe it
  without owner approval — there is no version history.
- Password hashes are SHA-256 (no salt) for legacy compatibility. There is
  an outstanding TODO to migrate to PBKDF2-with-salt on next login. Do that
  only when explicitly requested.

---

## 4. Verifying the baseline holds

Run `python3 scripts/verify-baseline.py` from the repo root. It asserts:

- `functions/_middleware.js`, `functions/lib/session.js`, all API endpoints exist
- `js/content-protection.js` exists
- `admin/login.html`, `admin/dashboard.html`, `admin/users.html` exist
- Every course HTML has a "Course Resources" block ABOVE the first `unit-section`
- Every chapter has an assessment strip in **AS → FOR → OF** order
- The Role Reference matrix order is **Super User → Administrator → Teacher → Student**
- The role pill `<span id="user-role">` is **NOT** present in nav chips
- Logout links point to `/api/logout` (not `/cdn-cgi/access/logout`)
- No Netlify Identity script tags remain
- All chapter-assessment hrefs resolve to files that exist
- MathJax delimiters use single backslash, not `\\(`

If any assertion fails, the script exits non-zero. **Do not deploy a state
that fails the baseline check** without explicit owner approval.

---

## 5. Locked content

- Curriculum lesson notes (~331 blocks across 10 courses): subject-matter
  accuracy was audited; do not rewrite without retaining the structure
  (concept paragraphs → vocabulary → worked examples → mistakes →
  curriculum citation).
- Role Reference matrix: 13 capability rows. Don't reorder columns. Do add
  new rows if new capabilities ship — but new rows must follow the
  existing tier-grouping convention (everyone / admin+ / superuser-only / nobody).
- 49 video replacements made on 2026-05-20: every replacement was oEmbed-verified.
  If a video breaks again, find another working replacement; don't restore
  the old (broken) ID.

---

## 6. Where to find prior decisions

Commit messages on `main` are the canonical record. Recent ones to consult
before structural changes:

- `afe04b2` — chapter strip order set to AS → FOR → OF
- `4c1350c` — curriculum-to-top + AS/FOR/OF strips + 49 video fixes
- `e7a2b12` — MCV4U lesson notes expanded to per-topic
- `bf61f34` — Lesson notes added for 9 courses
- `b684a7e` — MCR3U lesson notes pilot
- `6e1dcc6` — Content protection script + middleware injection
- `94f3975` — Role-reference matrix added to Manage Users
- `e113e66` — Custom email+password auth built
- `fc00324` — Removed Netlify Identity
- `b08c19bf` — Cloudflare Access removed (was the wrong product)

**End of baseline. Last updated 2026-05-20 by the curriculum-shipping session.**
