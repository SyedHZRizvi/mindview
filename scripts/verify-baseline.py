#!/usr/bin/env python3
"""Verify that the locked baseline of the MindView site is intact.

Run from repo root:
    python3 scripts/verify-baseline.py

Exits 0 if everything checks out, non-zero (and prints what failed) otherwise.
Failures should block deployment unless the owner has explicitly approved
the change.

This is a guardrail script — it complements CLAUDE.md by *executably*
asserting the same invariants. If you intend to break one of these
invariants, update both this script and CLAUDE.md in the same commit
so the new baseline is documented and re-verifiable.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# (code, expected number of chapters)
COURSES_AND_CHAPTERS = [
    ("mcr3u", 8), ("mhf4u", 8), ("mcv4u", 9), ("mdm4u", 8),
    ("sph3u", 5), ("sph4u", 5), ("sch4u", 5), ("sbi4u", 5),
    ("ics4u", 5), ("eng4u", 6),
]
COURSES = [c for c, _ in COURSES_AND_CHAPTERS]

REQUIRED_FILES = [
    "functions/_middleware.js",
    "functions/lib/session.js",
    "functions/api/login.js",
    "functions/api/logout.js",
    "functions/api/me.js",
    "functions/api/users.js",
    "functions/api/bootstrap.js",
    "js/content-protection.js",
    "admin/login.html",
    "admin/dashboard.html",
    "admin/users.html",
    "_redirects",
    "_headers",
    "index.html",
    "CLAUDE.md",
]

failures: list[str] = []


def fail(msg: str) -> None:
    failures.append(msg)


# ---------- Existence checks ----------

def check_required_files() -> None:
    """All security-critical & UX-critical files must exist."""
    for f in REQUIRED_FILES:
        if not (ROOT / f).is_file():
            fail(f"missing required file: {f}")


def check_chapter_pages_exist() -> None:
    """Every course must have exactly the expected count of chapter pages."""
    for code, expected in COURSES_AND_CHAPTERS:
        d = ROOT / "courses" / code
        if not d.is_dir():
            fail(f"{code}: missing courses/{code}/ chapter directory")
            continue
        pages = sorted(d.glob("ch*.html"))
        if len(pages) != expected:
            fail(f"{code}: found {len(pages)} chapter pages, expected {expected}")
        # Verify ch1.html..chN.html sequence
        nums = sorted(int(re.search(r'ch(\d+)\.html', p.name).group(1)) for p in pages)
        for i, n in enumerate(nums, 1):
            if i != n:
                fail(f"{code}: chapter numbering not contiguous starting at 1 "
                     f"(saw {nums})")
                break


# ---------- Auth invariants ----------

def check_middleware_exempt_list() -> None:
    """Login pages and auth APIs must remain in PUBLIC_EXACT."""
    text = (ROOT / "functions/_middleware.js").read_text()
    must_have = ["'/login'", "'/admin/login'", "'/admin/login.html'",
                 "'/api/login'", "'/api/logout'", "'/api/me'",
                 "'/api/bootstrap'"]
    for entry in must_have:
        if entry not in text:
            fail(f"middleware missing PUBLIC_EXACT entry: {entry}")
    if "env.SESSION_SECRET" not in text:
        fail("middleware no longer checks env.SESSION_SECRET")


def check_session_cookie_attributes() -> None:
    """mv_session cookie must keep HttpOnly + Secure + SameSite=Lax + Path=/."""
    sess = (ROOT / "functions/lib/session.js").read_text()
    must = ["HttpOnly", "Secure", "SameSite=Lax", "Path=/", "mv_session"]
    for m in must:
        if m not in sess:
            fail(f"functions/lib/session.js: missing cookie attribute {m}")


def check_bootstrap_locked_when_kv_nonempty() -> None:
    """bootstrap.js must return 403 once KV has any user (no rescue flag)."""
    text = (ROOT / "functions/api/bootstrap.js").read_text()
    if "force_reset" in text or "__wipedCount" in text:
        fail("functions/api/bootstrap.js: contains rescue-mode code "
             "(force_reset / __wipedCount). This should have been removed.")
    if "Bootstrap already complete" not in text:
        fail("functions/api/bootstrap.js: missing 'Bootstrap already complete' "
             "lock-out message")


# ---------- Legacy-tech remnant checks ----------

def _all_html_files() -> list[Path]:
    out = []
    for f in ["index.html", "admin/login.html", "admin/dashboard.html",
              "admin/users.html"]:
        out.append(ROOT / f)
    for code in COURSES:
        out.append(ROOT / f"courses/{code}.html")
        out.extend(sorted((ROOT / f"courses/{code}").glob("ch*.html")))
    return [p for p in out if p.exists()]


def check_no_netlify_identity() -> None:
    """No Netlify Identity widget tags should remain anywhere."""
    for p in _all_html_files():
        text = p.read_text()
        if "netlify-identity-widget" in text or "netlifyIdentity." in text:
            fail(f"{p.relative_to(ROOT)}: contains Netlify Identity remnants")


def check_no_cloudflare_access() -> None:
    """No cdn-cgi/access references should remain (was the wrong product)."""
    for p in [ROOT / "index.html",
              ROOT / "admin/dashboard.html",
              ROOT / "admin/users.html"]:
        text = p.read_text()
        if "/cdn-cgi/access/" in text:
            fail(f"{p.relative_to(ROOT)}: contains Cloudflare-Access "
                 "logout/login link (should be /api/logout)")


def check_logout_links() -> None:
    """Logout links across pages must point to /api/logout."""
    for f in ["index.html", "admin/dashboard.html", "admin/users.html"]:
        text = (ROOT / f).read_text()
        if "/api/logout" not in text:
            fail(f"{f}: missing /api/logout link")


def check_no_role_pill_in_nav() -> None:
    """Per UX baseline, the role badge was removed from nav chips."""
    for f in ["index.html", "admin/dashboard.html", "admin/users.html"]:
        text = (ROOT / f).read_text()
        if re.search(r'<span\s+id="user-role"', text):
            fail(f"{f}: nav still contains <span id=\"user-role\"> "
                 "(role badge was deliberately removed)")


# ---------- Landing-page invariants ----------

def check_landing_has_resources_and_cards() -> None:
    """Every course landing page must have a Course Resources block AND
    a chapter-cards grid AND no inline unit-section chapter content."""
    for code in COURSES:
        text = (ROOT / f"courses/{code}.html").read_text()
        if "Course Resources" not in text:
            fail(f"{code}.html: missing 'Course Resources' block on landing")
        if "chapter-cards-grid" not in text and "chapter-card" not in text:
            fail(f"{code}.html: missing chapter-cards grid on landing")
        # No inline unit-section chapter content (resources / strandA /
        # bridge are explicitly allowed)
        for m in re.finditer(r'<div class="unit-section"[^>]*id="([^"]+)"',
                             text, re.I):
            uid = m.group(1)
            if uid.lower() not in ("resources", "stranda", "bridge"):
                fail(f"{code}.html: still contains inline unit-section id="
                     f'"{uid}" on landing (should be in a chapter page)')


# ---------- Chapter-page invariants ----------

ASSESSMENT_CARD_RE = re.compile(r'assessment-strip-(for|as|of)\b', re.I)


def check_chapter_pages_well_formed() -> None:
    """Every chapter page must have: breadcrumb, hero, AS→FOR→OF strip,
    prev/next nav, at least one lesson-notes block.

    The first chapter has no "previous chapter" link (just back-to-course),
    the last has no "next chapter" link (back-to-course again); both still
    have a chapter-nav container.
    """
    for code in COURSES:
        for p in sorted((ROOT / f"courses/{code}").glob("ch*.html")):
            text = p.read_text()
            rel = p.relative_to(ROOT)

            # Breadcrumb / back-to-course
            if 'Back to course' not in text:
                fail(f"{rel}: missing 'Back to course' breadcrumb")

            # Hero — accept either `chapter-hero` (most courses) or
            # `unit-header` (the original class kept by MCR3U). Both render
            # an identical gradient header at the top of the chapter.
            if 'class="chapter-hero"' not in text and 'class="unit-header"' not in text:
                fail(f"{rel}: missing chapter-hero / unit-header")

            # Prev/Next nav
            if 'chapter-nav' not in text:
                fail(f"{rel}: missing chapter-nav strip at the bottom")

            # AS → FOR → OF strip
            order = ASSESSMENT_CARD_RE.findall(text)
            # Drop occurrences inside <style> rules (before <body>)
            body_pos = text.find("<body")
            if body_pos >= 0:
                pre = text[:body_pos]
                pre_count = len(ASSESSMENT_CARD_RE.findall(pre))
                order = order[pre_count:]
            if len(order) < 3:
                fail(f"{rel}: assessment-strip cards missing "
                     f"(found {len(order)} card class occurrences)")
            elif order[:3] != ["as", "for", "of"]:
                fail(f"{rel}: assessment-strip order is "
                     f"{'→'.join(c.upper() for c in order[:3])}, "
                     "expected AS→FOR→OF")

            # Lesson notes — at least one (some short chapters may have
            # only one note; we just require non-zero)
            if 'class="lesson-notes"' not in text:
                fail(f"{rel}: no <details class=\"lesson-notes\"> block found")


def check_chapter_assessment_links_resolve() -> None:
    """Every assessment href on every chapter page must resolve to a real file."""
    for code in COURSES:
        for p in sorted((ROOT / f"courses/{code}").glob("ch*.html")):
            text = p.read_text()
            rel = p.relative_to(ROOT)
            for href in re.findall(r'href="\.\./\.\./assessments/([^"]+)"', text):
                target = ROOT / "assessments" / href
                if not target.is_file():
                    fail(f"{rel}: assessment link to missing file "
                         f"assessments/{href}")


def check_no_double_backslash_mathjax() -> None:
    """No double-backslash MathJax delimiters OR macros anywhere in course
    or chapter HTML. MathJax 3 wants `\X` (single backslash). `\\X` is a
    literal backslash followed by X — does NOT trigger the macro.

    Catches both the wrapper-delimiter form (e.g. ``\\(``, ``\\[``) and the
    in-span macro form (e.g. ``\\frac``, ``\\Delta``, ``\\rightarrow``).
    The macro form is detected only inside ``\(...\)`` and ``\[...\]``
    spans so unrelated `\\foo` in regular prose doesn't false-positive.
    """
    bad_delims = [r"\\(", r"\\)", r"\\[", r"\\]"]
    # Anything starting with two backslashes followed by 1+ letters
    # (commands like \frac, \Delta, \text, \rightarrow), or backslash-comma
    # (\, thin space) is a doubled backslash inside a math span.
    bad_macro_re = re.compile(r"\\\\([A-Za-z]+|,)")
    span_re = re.compile(r"\\\([\s\S]*?\\\)|\\\[[\s\S]*?\\\]")

    for code in COURSES:
        candidates = [ROOT / f"courses/{code}.html"]
        candidates.extend(sorted((ROOT / f"courses/{code}").glob("ch*.html")))
        for p in candidates:
            text = p.read_text()
            # 1) delimiter brackets anywhere
            for d in bad_delims:
                if d in text:
                    count = text.count(d)
                    fail(f"{p.relative_to(ROOT)}: {count}× double-backslash "
                         f"math delimiter {d!r} (use single backslash)")
            # 2) double-backslash macros INSIDE \( … \) and \[ … \] spans
            macros_in_span = 0
            for span in span_re.findall(text):
                macros_in_span += len(bad_macro_re.findall(span))
            if macros_in_span:
                fail(f"{p.relative_to(ROOT)}: {macros_in_span}× double-"
                     f"backslash MathJax macro (e.g. \\\\frac, \\\\Delta) "
                     "inside \\(…\\) or \\[…\\] — use single backslash")


def check_eng4u_citation_consistency() -> None:
    """ENG4U citations had a class of bugs where the strand letter and the
    expectation code's leading letter didn't match (e.g. 'Strand B,
    Expectation A3'). Catch that going forward.
    """
    pat = re.compile(r'Strand\s+([A-D]),\s+Expectation\s+([A-Z])')
    for p in sorted((ROOT / "courses/eng4u").glob("ch*.html")):
        text = p.read_text()
        for m in pat.finditer(text):
            strand, code_letter = m.group(1), m.group(2)
            if strand != code_letter:
                fail(f"{p.relative_to(ROOT)}: citation 'Strand {strand}, "
                     f"Expectation {code_letter}…' — strand letter and "
                     "expectation code's first letter must match")


# ---------- Manage Users invariants ----------

def check_role_matrix_columns() -> None:
    """Manage Users role matrix columns must be Super User → Admin → Teacher → Student."""
    text = (ROOT / "admin/users.html").read_text()
    m = re.search(
        r'<table class="role-matrix">[\s\S]*?<thead>([\s\S]*?)</thead>',
        text,
    )
    if not m:
        fail("admin/users.html: role-matrix <thead> not found")
        return
    header = m.group(1)
    order = re.findall(r'class="role-pill (\w+)"', header)
    expected = ["superuser", "admin", "teacher", "student"]
    if order != expected:
        fail(f"role matrix columns are {order}, expected {expected}")


# ---------- Runner ----------

def main() -> int:
    print("Verifying MindView baseline (CLAUDE.md invariants)…")
    checks = [
        ("required files exist",                check_required_files),
        ("chapter directories + counts",        check_chapter_pages_exist),
        ("middleware exempt list intact",       check_middleware_exempt_list),
        ("session cookie attributes",           check_session_cookie_attributes),
        ("bootstrap stays locked",              check_bootstrap_locked_when_kv_nonempty),
        ("no Netlify Identity remnants",        check_no_netlify_identity),
        ("no Cloudflare Access remnants",       check_no_cloudflare_access),
        ("logout links use /api/logout",        check_logout_links),
        ("no role pill in nav",                 check_no_role_pill_in_nav),
        ("landing pages: resources + cards, no inline chapters",
         check_landing_has_resources_and_cards),
        ("chapter pages well-formed",           check_chapter_pages_well_formed),
        ("chapter assessment links resolve",    check_chapter_assessment_links_resolve),
        ("MathJax delimiters & macros single-backslash", check_no_double_backslash_mathjax),
        ("ENG4U citation strand/code letters match",   check_eng4u_citation_consistency),
        ("role matrix column order",            check_role_matrix_columns),
    ]
    for label, fn in checks:
        before = len(failures)
        fn()
        after = len(failures)
        status = "OK" if before == after else f"{after - before} FAIL"
        print(f"  [{status:>7}] {label}")

    print()
    if not failures:
        print("✅ baseline intact — safe to deploy.")
        return 0
    print(f"❌ {len(failures)} baseline check(s) failed:")
    for f in failures:
        print(f"   • {f}")
    print()
    print("Refer to CLAUDE.md for what each invariant guards. Get explicit")
    print("owner approval before changing the baseline.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
