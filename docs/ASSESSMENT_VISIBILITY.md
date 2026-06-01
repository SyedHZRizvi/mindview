# Assessment Visibility Policy

**Owner-approved policy. Future contributors MUST read this before adding
or editing any assessment HTML file.**

This document defines the role-gated visibility rules for answer keys,
worked solutions, and marking rubrics across every assessment file under
`/assessments/`. It is paired with the runtime gate at
`js/role-gated.js` + `css/role-gated.css` and the one-shot patcher at
`scripts/_apply_role_gating.py`.

---

## 1. Policy

| Audience                                    | Sees                                            | Does not see                              |
|---------------------------------------------|-------------------------------------------------|-------------------------------------------|
| Student or unauthenticated visitor          | Questions, per-question "Correct / Try again" instant feedback (from `chkMC` / `cN`) | Aggregate answer keys, worked solutions, marking rubrics |
| Teacher / Admin / Super User                | Everything, with a "🔒 Instructor-only content below" banner above each gated block | n/a (full visibility) |

Roles are read from `/api/me`. The instructor set is
`teacher`, `admin`, `superuser`. All other states (including the
unauthenticated `{ authenticated: false }` response) are treated as
**student** for visibility purposes — fail-closed.

The Ontario assessment-integrity expectation is the basis for this policy:
students must encounter assessments as tasks to attempt, not as
pre-revealed answer banks.

---

## 2. What counts as "instructor-only" content

The patcher script stamps `class="instructor-only"` onto every element
matching any of:

1. `<details>` blocks whose `<summary>` text contains any of: "Answer Key",
   "Complete Answer Key", "Answer Click", "Solution" / "Show solution",
   "Marking", "Rubric", "Reveal expected answer", "Reveal".
2. `<div class="solution">` blocks (worked solutions used by AS practice
   quizzes).
3. `<div class="rubric">` blocks (marking rubrics on OF unit tests and
   final exams).
4. `<details class="answer-key">` and `<div class="answer-key">` blocks
   (aggregate answer-key panels on the math final-exam files).

The patcher is idempotent: it leaves elements that already carry
`instructor-only` alone, so it is safe to re-run.

---

## 3. What stays visible to students

By explicit design, the following remain visible so students retain
**formative feedback** on their own attempts (Assessment AS Learning is
fundamentally about self-checking):

- The `Check` button (`<button onclick="chkMC(...)">`) and the JS
  `chkMC` / `cN` / `chkNum` helpers themselves.
- The `correct` / `wrong` visual class changes on each `.qcard` /
  `.question-card` when the student clicks Check.
- The "✅ Correct!" / "❌ Not quite. See the solution below." feedback
  banner inside each `.fb` / `.feedback` element.
- `<div class="sol">` per-question feedback blocks (the short-name
  variant — see Section 6 for the deliberate choice not to gate these).
- Any `data-answer="..."` attributes on form inputs.

---

## 4. Implementation

### 4.1 Runtime gate (every HTML page)

The middleware at `functions/_middleware.js` injects two complementary
scripts at the end of `<head>` on every HTML response:

```html
<script src="/js/content-protection.js" defer></script>
<script src="/js/role-gated.js" defer></script>
```

`js/role-gated.js`:

1. On parse, immediately adds `class="role-unknown"` to `<html>`.
2. Injects CSS that hides `.instructor-only` while
   `html.role-unknown` or `html.role-student` is set.
3. Fetches `/api/me` (which is allow-listed in the middleware's
   `PUBLIC_EXACT` so it never 401s during the role check) and:
   - If the response says `authenticated: true` and `user.role` is
     `teacher`, `admin`, or `superuser`: replaces `role-unknown`
     with `role-instructor`. CSS then reveals the gated content
     with a "🔒 Instructor-only content below" banner.
   - Otherwise (student, unauthenticated, fetch failure, or JSON
     parse error): replaces `role-unknown` with `role-student`,
     removes every `<details class="instructor-only">` from the DOM
     entirely, and clears `.innerHTML` on every other
     `.instructor-only` container so a determined student cannot
     view-source the page to see the answers.

`css/role-gated.css` is a standalone copy of the same CSS rules for
documentation / override; the script does not depend on it.

### 4.2 One-shot patcher

`scripts/_apply_role_gating.py` walks every assessment file (both
subdirectory and flat patterns) and stamps the `instructor-only`
class onto matching elements. Run modes:

```bash
python3 scripts/_apply_role_gating.py --dry-run   # report only
python3 scripts/_apply_role_gating.py             # apply changes
```

The script is pure stdlib, idempotent, and preserves existing classes
and attribute order. It does NOT modify `data-answer` attributes or
any `chkMC` / `cN` JavaScript.

---

## 5. Defense in depth

For students the script does not merely *hide* gated content with CSS:
the `.instructor-only` DOM nodes are physically removed (`<details>`)
or scrubbed (other containers) from the DOM after `/api/me` returns
a non-instructor role. The savvy student who tries "View Source" or
opens devtools (where content-protection.js does not block them) will
find an empty container rather than the answer text.

The gate is **fail-closed**:

| Scenario                                  | Outcome     |
|-------------------------------------------|-------------|
| `/api/me` returns student role            | hidden      |
| `/api/me` returns `authenticated: false`  | hidden      |
| `/api/me` 5xx / network error             | hidden      |
| `/api/me` malformed JSON                  | hidden      |
| `fetch` itself unavailable                | hidden      |
| `/api/me` returns instructor role         | revealed    |

---

## 6. Deliberate scope decisions

- **`<div class="sol">` (short-name) blocks are NOT gated.** These are
  used uniformly on OF unit tests for per-question feedback driven by
  `chkMC` / `chkNum`. The same blocks in AS practice quizzes use the
  full-word `<div class="solution">` class and ARE gated. The split
  preserves per-question formative feedback on graded tests while
  removing it from practice quizzes (where worked solutions are the
  primary "answer key").
- **`<details><summary>Answer Key</summary>` per question** appears on
  many OF tests and is unconditionally gated, including in OF tests.
- **Final-exam aggregate answer keys** (`<details class="answer-key">`)
  are unconditionally gated.
- **Per-question instant-check buttons** (the `Check` button + `chkMC`)
  remain functional for students; they only lose the worked-solution
  display, not the correct/wrong indicator.

---

## 7. Future work (out of scope for this commit)

The current implementation provides a strict "hide from students,
reveal to instructors" gate. The next phase (tracked as a separate
task) will add a richer workflow:

- **Student submissions:** an `/api/submissions` endpoint that captures
  a student's answers when they click `Submit` on an OF / Final exam.
- **Teacher feedback:** an `admin/submissions.html` dashboard where a
  teacher can review submissions, mark them, and return marks/comments
  to the student.
- **Per-assignment release:** an instructor toggle to release the
  answer key to a specific student or class section AFTER submission
  (rather than the current binary "instructor / student" gate).

None of that is implemented yet; this commit is scoped to the binary
visibility gate.

---

## 8. Verifier

A future revision of `scripts/verify-baseline.py` should assert:

- `js/role-gated.js` and `css/role-gated.css` exist.
- `functions/_middleware.js` injects both `content-protection.js` and
  `role-gated.js` into the head element.
- Every OF / Final assessment file under `/assessments/` carries at
  least one element with `class="instructor-only"`.

That check is intentionally additive; the present commit does not
update the verifier so the baseline tag holds during staging review.

---

## 9. Where the policy lives

| File                                         | Purpose                                          |
|----------------------------------------------|--------------------------------------------------|
| `js/role-gated.js`                           | Runtime gate (loaded on every HTML page).        |
| `css/role-gated.css`                         | Standalone CSS (also embedded in the JS).        |
| `functions/_middleware.js`                   | Injects the script tags into every HTML response.|
| `scripts/_apply_role_gating.py`              | One-shot patcher that stamps the class.          |
| `docs/ASSESSMENT_VISIBILITY.md` (this file)  | Policy + invariants.                             |

If you change any of the above, update this document in the same
commit. **Future agents and humans must read this before modifying
anything.**
