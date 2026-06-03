#!/usr/bin/env python3
"""R1c — Add explicit, visible "📚 Required Reading" entry points so the
5-tier linked reading list is easy to find from any course-related page.

Three insertions per course:

  1. Course LANDING page (courses/{code}.html)
     → adds a 3rd card "📚 Required Reading & Resources" to the
        Course Resources & Final Evaluation block. The existing 2
        cards (Curriculum Document + Final Exam) stay; the new card
        sits between them. Links direct to
        {code}_curriculum.html#required-learning-resources

  2. CHAPTER pages (courses/{code}/ch{N}.html — all of them)
     → adds a small "📚 Reading Resources" badge in the chapter hero,
        next to the existing "← Back to course" breadcrumb.

  3. CURRICULUM SUB-PAGE (courses/{code}_curriculum.html)
     → adds id="required-learning-resources" to the
        "<h2>… Required Learning Resources</h2>" heading so the anchor
        links from (1) and (2) jump straight to that section.

Idempotent on all three. Owner-approved 2026-06-01.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent

COURSES = sorted([
    'mcr3u', 'mhf4u', 'mcv4u', 'mdm4u', 'mct3m', 'mct4m',
    'snc2d', 'sbi3u', 'sbi4u', 'sch3u', 'sch4u', 'sph3u', 'sph4u',
    'eng2d', 'eng3u', 'eng4u',
    'ics3u', 'ics4u',
    'chv2o', 'cpc3o', 'cpw4u',
    'chc2d', 'chw3m', 'chy4u',
    'clu3m', 'cln4u',
    'cgf3m', 'cgw4u',
    'baf3m', 'bat4m', 'bbb4m', 'boh4m',
    'hfn3m', 'hfa4m', 'hsc4m',
    'glc2o', 'gwl3o', 'gpp3o', 'gle3o', 'gle4o',
])


# ─────────── Step 1 — curriculum sub-page anchor ───────────

def add_anchor_to_curriculum(code):
    """Add id='required-learning-resources' to the heading so anchor
    links from the landing + chapter pages jump straight there."""
    p = ROOT / 'courses' / f'{code}_curriculum.html'
    if not p.exists():
        return f"  ✗ {code}: curriculum page missing"
    text = p.read_text()
    if 'id="required-learning-resources"' in text:
        return f"  ⇢ {code}: curriculum anchor already present"
    # Match the Section-2 heading variants:
    #   <h2>2. Required Learning Resources</h2>
    #   <h2>Required Learning Resources</h2>  (no number prefix)
    pattern = re.compile(r'<h2>(\s*(?:\d+\.\s+)?Required Learning Resources\s*)</h2>')
    m = pattern.search(text)
    if not m:
        return f"  ⚠ {code}: Required Learning Resources heading not found"
    replacement = f'<h2 id="required-learning-resources">{m.group(1)}</h2>'
    text = text[:m.start()] + replacement + text[m.end():]
    p.write_text(text)
    return f"  ✓ {code}: anchor added to curriculum heading"


# ─────────── Step 2 — landing-page 3rd card ───────────

LANDING_CARD_TEMPLATE = (
    '<a href="{code}_curriculum.html#required-learning-resources" '
    'style="display:block;background:#fff;border:1px solid #e2e8f0;'
    'border-left:5px solid #16a34a;border-radius:10px;padding:18px 20px;'
    'text-decoration:none;color:#1e293b;box-shadow:0 1px 2px rgba(15,23,42,0.04);">\n'
    '<div style="font-size:13px;color:#16a34a;font-weight:700;text-transform:uppercase;'
    'letter-spacing:1px;margin-bottom:6px;">📚 Required Reading &amp; Resources</div>\n'
    '<div style="font-size:16px;font-weight:700;margin-bottom:4px;">'
    'Books · Articles · Novels · Online Resources</div>\n'
    '<div style="font-size:13px;color:#475569;">5-tier linked reading list — '
    'Ontario Ministry curriculum, primary textbooks, free supplementary resources, '
    'novels (English), and primary sources / archives.</div>\n'
    '</a>'
)


def add_landing_card(code):
    p = ROOT / 'courses' / f'{code}.html'
    if not p.exists():
        return f"  ✗ {code}: landing page missing"
    text = p.read_text()
    if 'Required Reading &amp; Resources' in text:
        return f"  ⇢ {code}: landing card already present"

    # Find the existing curriculum-document card; insert the new reading
    # card RIGHT AFTER it.
    curriculum_card_pattern = re.compile(
        r'(<a href="' + re.escape(code) + r'_curriculum\.html"[\s\S]*?</a>)',
        re.I
    )
    m = curriculum_card_pattern.search(text)
    if not m:
        return f"  ✗ {code}: couldn't find curriculum-card insertion anchor"

    new_card = LANDING_CARD_TEMPLATE.format(code=code)
    insertion = m.group(1) + '\n' + new_card
    text = text[:m.start()] + insertion + text[m.end():]
    p.write_text(text)
    return f"  ✓ {code}: added 'Required Reading' card to landing"


# ─────────── Step 3 — chapter-page hero badge ───────────

# A small green pill-style link, sits inline with the existing "← Back to
# course" breadcrumb in the chapter hero. We piggyback on the same
# div, appending an extra <a> separated by a middle dot.
CHAPTER_BADGE_TEMPLATE = (
    ' &nbsp;·&nbsp; '
    '<a href="../{code}_curriculum.html#required-learning-resources" '
    'style="color:#fff;background:rgba(255,255,255,0.18);padding:3px 10px;'
    'border-radius:10px;font-size:12px;font-weight:700;text-decoration:none;'
    'border:1px solid rgba(255,255,255,0.35);">📚 Required Reading</a>'
)


def add_chapter_badges(code):
    """Add the 📚 Required Reading badge to every chapter page in
    courses/{code}/ch*.html. The badge sits next to the breadcrumb."""
    course_dir = ROOT / 'courses' / code
    if not course_dir.is_dir():
        return f"  (no chapter dir for {code})"

    n_patched, n_skipped = 0, 0
    for chap_path in sorted(course_dir.glob('ch*.html')):
        text = chap_path.read_text()
        if '📚 Required Reading' in text:
            n_skipped += 1
            continue
        # Find the breadcrumb: <a href="../{code}.html" ...>← Back to course
        breadcrumb_re = re.compile(
            r'(<a\s+href="\.\./' + re.escape(code) +
            r'\.html"[^>]*>← Back to course[^<]*</a>)',
            re.I
        )
        m = breadcrumb_re.search(text)
        if not m:
            # Some chapter pages might use a slightly different breadcrumb
            # phrasing; try a looser match
            breadcrumb_re2 = re.compile(
                r'(<a\s+href="\.\./' + re.escape(code) + r'\.html"[^>]*>[^<]*</a>)',
                re.I
            )
            m = breadcrumb_re2.search(text)
            if not m:
                n_skipped += 1
                continue
        badge = CHAPTER_BADGE_TEMPLATE.format(code=code)
        text = text[:m.end()] + badge + text[m.end():]
        chap_path.write_text(text)
        n_patched += 1
    return f"  ✓ {code}: chapter badges → patched {n_patched}, skipped {n_skipped}"


def main():
    print("R1c — adding visible Required Reading entry points")
    print()
    print("Step 1 — curriculum-page anchors")
    for code in COURSES:
        print(add_anchor_to_curriculum(code))
    print()
    print("Step 2 — course-landing-page cards")
    for code in COURSES:
        print(add_landing_card(code))
    print()
    print("Step 3 — chapter-page badges")
    for code in COURSES:
        print(add_chapter_badges(code))


if __name__ == '__main__':
    main()
