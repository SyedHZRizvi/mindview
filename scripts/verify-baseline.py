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

COURSES = [
    "mcr3u", "mhf4u", "mcv4u", "mdm4u",
    "sph3u", "sph4u", "sch4u", "sbi4u",
    "ics4u", "eng4u",
]

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


def check_required_files() -> None:
    """All security-critical & UX-critical files must exist."""
    for f in REQUIRED_FILES:
        if not (ROOT / f).is_file():
            fail(f"missing required file: {f}")


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


def check_no_netlify_identity() -> None:
    """No Netlify Identity widget tags should remain anywhere."""
    for course in COURSES:
        text = (ROOT / f"courses/{course}.html").read_text()
        if "netlify-identity-widget" in text or "netlifyIdentity." in text:
            fail(f"{course}: contains Netlify Identity remnants")
    for f in ["index.html", "admin/login.html",
              "admin/dashboard.html", "admin/users.html"]:
        text = (ROOT / f).read_text()
        if "netlify-identity-widget" in text or "netlifyIdentity." in text:
            fail(f"{f}: contains Netlify Identity remnants")


def check_no_cloudflare_access() -> None:
    """No cdn-cgi/access references should remain (was the wrong product)."""
    for f in ["index.html", "admin/dashboard.html", "admin/users.html"]:
        text = (ROOT / f).read_text()
        if "/cdn-cgi/access/" in text:
            fail(f"{f}: contains Cloudflare-Access logout/login link "
                 "(should be /api/logout)")


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
        # The role pill carried id="user-role" in a span. It must be gone.
        if re.search(r'<span\s+id="user-role"', text):
            fail(f"{f}: nav still contains <span id=\"user-role\"> "
                 "(role badge was deliberately removed)")


def check_course_resources_block_at_top() -> None:
    """Course Resources block must appear BEFORE the first chapter section."""
    for course in COURSES:
        text = (ROOT / f"courses/{course}.html").read_text()
        # The block contains the text "Course Resources" (header) and links
        # to the curriculum overview.
        m_block = re.search(r"Course Resources", text)
        m_first_unit = re.search(r'<div class="unit-section"', text)
        if not m_block or not m_first_unit:
            # Some courses may not have either — flag if expected to.
            if not m_block:
                fail(f"{course}: missing 'Course Resources' block")
            if not m_first_unit:
                fail(f"{course}: missing 'unit-section' divs")
            continue
        if m_block.start() > m_first_unit.start():
            fail(f"{course}: 'Course Resources' block appears AFTER the first "
                 f"unit-section (must be ABOVE)")


def check_assessment_strip_order() -> None:
    """Every chapter assessment strip must be AS → FOR → OF.

    Walks the assessment-strip-{for|as|of} class names in document order
    and asserts they appear in repeating AS→FOR→OF triples. Avoids
    fragile <div> nesting since each card is an <a> with inner <div>s.
    """
    card_pat = re.compile(r'assessment-strip-(for|as|of)\b')
    for course in COURSES:
        text = (ROOT / f"courses/{course}.html").read_text()
        order = card_pat.findall(text)
        # Drop CSS-rule occurrences (anything before <body>)
        body_start = text.find('<body')
        if body_start >= 0:
            pre_body = text[:body_start]
            pre_count = len(card_pat.findall(pre_body))
            order = order[pre_count:]
        if not order:
            fail(f"{course}: no assessment-strip cards found in <body>")
            continue
        if len(order) % 3 != 0:
            fail(f"{course}: assessment-strip card count {len(order)} "
                 "not a multiple of 3")
            continue
        triples = [order[i:i+3] for i in range(0, len(order), 3)]
        for i, t in enumerate(triples, 1):
            if t != ["as", "for", "of"]:
                fail(f"{course} strip #{i}: card order is "
                     f"{'->'.join(c.upper() for c in t)}, expected AS->FOR->OF")


def check_role_matrix_columns() -> None:
    """Manage Users role matrix columns must be Super User → Admin → Teacher → Student."""
    text = (ROOT / "admin/users.html").read_text()
    m = re.search(r'<table class="role-matrix">[\s\S]*?<thead>([\s\S]*?)</thead>', text)
    if not m:
        fail("admin/users.html: role-matrix <thead> not found")
        return
    header = m.group(1)
    order = re.findall(r'class="role-pill (\w+)"', header)
    expected = ["superuser", "admin", "teacher", "student"]
    if order != expected:
        fail(f"role matrix columns are {order}, expected {expected}")


def check_mathjax_delimiters() -> None:
    """No double-backslash MathJax delimiters anywhere in course pages."""
    bad_delims = [r"\\(", r"\\)", r"\\[", r"\\]"]
    for course in COURSES:
        text = (ROOT / f"courses/{course}.html").read_text()
        for d in bad_delims:
            if d in text:
                count = text.count(d)
                fail(f"{course}: {count}× double-backslash math delimiter "
                     f"{d!r} (use single backslash)")


def check_assessment_links_resolve() -> None:
    """Every chapter assessment href must resolve to a real file."""
    for course in COURSES:
        text = (ROOT / f"courses/{course}.html").read_text()
        for href in re.findall(r'href="\.\./assessments/([^"]+)"', text):
            target = ROOT / "assessments" / href
            if not target.is_file():
                fail(f"{course}: assessment link points to missing file "
                     f"assessments/{href}")


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


def main() -> int:
    print("Verifying MindView baseline (CLAUDE.md invariants)…")
    checks = [
        ("required files exist",           check_required_files),
        ("middleware exempt list intact",  check_middleware_exempt_list),
        ("no Netlify Identity remnants",   check_no_netlify_identity),
        ("no Cloudflare Access remnants",  check_no_cloudflare_access),
        ("logout links use /api/logout",   check_logout_links),
        ("no role pill in nav",            check_no_role_pill_in_nav),
        ("Course Resources block at top",  check_course_resources_block_at_top),
        ("assessment strips AS→FOR→OF",    check_assessment_strip_order),
        ("role matrix column order",       check_role_matrix_columns),
        ("MathJax delimiters single-backslash", check_mathjax_delimiters),
        ("assessment links resolve",       check_assessment_links_resolve),
        ("session cookie attributes",      check_session_cookie_attributes),
        ("bootstrap stays locked",         check_bootstrap_locked_when_kv_nonempty),
    ]
    initial = len(failures)
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
