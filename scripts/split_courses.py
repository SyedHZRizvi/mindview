#!/usr/bin/env python3
"""Split monolithic course pages into per-chapter pages.

For each course HTML at courses/{code}.html:
  1. Find every <div class="unit-section" id="unitN">…</div> block.
  2. Write courses/{code}/ch{N}.html — preserving the unit-section content
     byte-for-byte (only adjusting relative paths from ../ to ../../) and
     wrapping it in:
        same <head> as the landing page (with css path bumped one level)
        same nav (paths bumped)
        breadcrumb + chapter hero (color/title from the original unit-header)
        the unit-section content (lesson-notes, videos, AS→FOR→OF strip)
        prev/next chapter nav
        same footer
  3. Rewrite courses/{code}.html with:
        same <head>, nav, hero, chapter-pill nav (links updated to ch{N}.html)
        Course Resources block (preserved at top)
        chapter-cards grid (one card per chapter)
        footer
        (all <div class="unit-section"> blocks removed)

Run from anywhere:
    python3 scripts/split_courses.py
"""
from __future__ import annotations

import re
import sys
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

COURSES = {
    # course_code: (display_name, subject_emoji, grade_label, course_title_for_breadcrumb)
    "mcr3u": ("MCR3U", "📐", "Mathematics — Grade 11 University Preparation", "MCR3U Functions"),
    "mhf4u": ("MHF4U", "📐", "Mathematics — Grade 12 University Preparation", "MHF4U Advanced Functions"),
    "mcv4u": ("MCV4U", "∫",  "Mathematics — Grade 12 University Preparation", "MCV4U Calculus and Vectors"),
    "mdm4u": ("MDM4U", "📊", "Mathematics — Grade 12 University Preparation", "MDM4U Mathematics of Data Management"),
    "sph3u": ("SPH3U", "⚡", "Science — Grade 11 University Preparation",     "SPH3U Physics"),
    "sph4u": ("SPH4U", "⚡", "Science — Grade 12 University Preparation",     "SPH4U Physics"),
    "sch4u": ("SCH4U", "🧪", "Science — Grade 12 University Preparation",     "SCH4U Chemistry"),
    "sbi4u": ("SBI4U", "🧬", "Science — Grade 12 University Preparation",     "SBI4U Biology"),
    "ics4u": ("ICS4U", "💻", "Computer Studies — Grade 12 University Preparation", "ICS4U Computer Science"),
    "eng4u": ("ENG4U", "📚", "English — Grade 12 University Preparation",     "ENG4U English"),
}


# ---------- HTML helpers (regex-based, but boundary-aware) ----------

DIV_OPEN_RE  = re.compile(r"<div\b[^>]*>", re.IGNORECASE)
DIV_CLOSE_RE = re.compile(r"</div\s*>",   re.IGNORECASE)
DIV_ANY_RE   = re.compile(r"<div\b[^>]*>|</div\s*>", re.IGNORECASE)

def find_matching_div_end(text: str, open_start: int) -> int:
    """Given the index in `text` where a <div ...> tag starts, return the index
    just AFTER the matching </div>. Counts nested divs."""
    depth = 0
    i = open_start
    for m in DIV_ANY_RE.finditer(text, open_start):
        tok = m.group(0)
        if tok.startswith("</"):
            depth -= 1
            if depth == 0:
                return m.end()
        else:
            depth += 1
    raise ValueError(f"no matching </div> for <div at byte {open_start}")


def find_unit_sections(text: str):
    """Return a list of (n, start_index, end_index, raw_slab) for each unit-section."""
    pat = re.compile(r'<div class="unit-section"[^>]*id="unit(\d+)"[^>]*>', re.IGNORECASE)
    out = []
    for m in pat.finditer(text):
        n = int(m.group(1))
        s = m.start()
        e = find_matching_div_end(text, s)
        slab = text[s:e]
        out.append((n, s, e, slab))
    return out


def parse_unit_header(slab: str):
    """Pull title, subtitle, gradient style from the first .unit-header inside the slab."""
    h = re.search(r'<div class="unit-header"[^>]*style="([^"]*)"[^>]*>([\s\S]*?)</div>', slab, re.I)
    title = subtitle = ""
    gradient = "linear-gradient(135deg,#475569,#1e293b)"
    accent_color = "#475569"
    if h:
        gradient = h.group(1).split("background:", 1)[-1].strip().strip(";")
        if not gradient or gradient == h.group(1):
            gradient = h.group(1)
        # extract first hex color from gradient for the accent
        ms = re.search(r"#[0-9a-fA-F]{3,8}", gradient)
        if ms:
            accent_color = ms.group(0)
        inner = h.group(2)
        h2 = re.search(r"<h2[^>]*>(.*?)</h2>", inner, re.I | re.S)
        if h2:
            title = re.sub(r"<[^>]+>", "", h2.group(1)).strip()
        p = re.search(r"<p[^>]*>(.*?)</p>", inner, re.I | re.S)
        if p:
            subtitle = re.sub(r"<[^>]+>", "", p.group(1)).strip()
    # Try sub*-header label patterns used by some non-mathematics courses
    if not title:
        sl = re.search(r'<div class="subsection-label"[^>]*>([\s\S]*?)</div>', slab, re.I)
        if sl:
            title = re.sub(r"<[^>]+>", "", sl.group(1)).strip()
    return title, subtitle, gradient, accent_color


def extract_head_and_nav(text: str) -> tuple[str, str]:
    """Return (head_open_through_body_open, nav_block)."""
    m_head_end = re.search(r"</head>\s*", text, re.I)
    if not m_head_end:
        raise ValueError("no </head>")
    head_end = m_head_end.end()
    m_body = re.search(r"<body[^>]*>\s*", text[head_end:], re.I)
    if not m_body:
        raise ValueError("no <body>")
    body_open_end = head_end + m_body.end()
    head_block = text[:body_open_end]

    # Nav is the first <nav>…</nav> or first <div class="navbar">…</div>
    m_nav = re.search(r"<nav\b[\s\S]*?</nav>\s*", text, re.I)
    if m_nav:
        nav_block = m_nav.group(0)
    else:
        nav_block = ""
    return head_block, nav_block


def adjust_paths_for_chapter(html: str) -> str:
    """Bump one directory level for relative links inside chapter pages."""
    out = html
    # CSS/asset/anchor link adjustments
    out = out.replace('href="../css/', 'href="../../css/')
    out = out.replace('src="../css/',  'src="../../css/')
    out = out.replace('src="../logo.png', 'src="../../logo.png')
    out = out.replace('href="../logo.png', 'href="../../logo.png')
    out = out.replace('href="../#', 'href="../../#')
    out = out.replace('href="../assessments/', 'href="../../assessments/')
    out = out.replace('src="../assessments/',  'src="../../assessments/')
    # nav brand link "../" → "../../" (absolute href="/" untouched)
    out = re.sub(r'href="\.\./(?![\./])', 'href="../../', out)
    return out


def find_resources_block(text: str) -> tuple[int, int, str] | None:
    """Locate the 'Course Resources & Final Evaluation' block (a top-level <div>).
    Returns (start, end, slab) or None."""
    # Look for the literal heading text — robust across courses.
    m = re.search(r'Course Resources\s*&(?:amp;)?\s*Final Evaluation', text, re.I)
    if not m:
        return None
    # Walk backward to find the enclosing top-level <div ...> opening
    open_starts = [d.start() for d in DIV_OPEN_RE.finditer(text, 0, m.start())]
    # Find the deepest div that's still open at m.start()
    # We use the matching-div-end logic for each candidate
    block_start = None
    block_end = None
    for cand in reversed(open_starts):
        try:
            cand_end = find_matching_div_end(text, cand)
        except ValueError:
            continue
        if cand_end > m.start():
            block_start = cand
            block_end = cand_end
            break
    if block_start is None:
        return None
    return block_start, block_end, text[block_start:block_end]


def find_pill_nav(text: str) -> tuple[int, int, str] | None:
    """Locate the chapter-pill quick-nav row containing href="#unitN" links.
    Returns (start, end, slab) or None.
    """
    # Search for the wrapper div containing at least one #unitN link
    pill_link = re.search(r'href="#unit\d+"', text)
    if not pill_link:
        return None
    open_starts = [d.start() for d in DIV_OPEN_RE.finditer(text, 0, pill_link.start())]
    for cand in reversed(open_starts):
        try:
            cand_end = find_matching_div_end(text, cand)
        except ValueError:
            continue
        if cand_end > pill_link.end():
            slab = text[cand:cand_end]
            if slab.count('href="#unit') >= 2:  # quick-nav row has multiple pills
                return cand, cand_end, slab
    return None


def find_hero(text: str) -> tuple[int, int, str] | None:
    m = re.search(r'<div class="chapter-hero"[^>]*>', text, re.I)
    if not m:
        return None
    e = find_matching_div_end(text, m.start())
    return m.start(), e, text[m.start():e]


def find_footer(text: str) -> tuple[int, int, str] | None:
    m = re.search(r'<footer\b[\s\S]*?</footer>', text, re.I)
    if not m:
        return None
    return m.start(), m.end(), m.group(0)


def find_body_close_segment(text: str) -> str:
    """Return everything from <footer …  to end-of-file (footer + </body></html>)."""
    f = find_footer(text)
    if f:
        return text[f[0]:]
    # Fallback — just </body></html>
    return "\n</body>\n</html>\n"


# ---------- Build chapter page ----------

def build_chapter_page(*, course_code: str, course_title: str, n: int, total_chapters: int,
                      gradient: str, title: str, subtitle: str, strand_tag: str,
                      head_block: str, nav_block: str, footer_tail: str,
                      content_slab: str, emoji: str) -> str:
    head_ch = adjust_paths_for_chapter(head_block)
    nav_ch  = adjust_paths_for_chapter(nav_block)
    content_ch = content_slab.replace('href="../assessments/', 'href="../../assessments/')

    if n == 1:
        prev_html = f'<a href="../{course_code}.html" class="chnav-btn chnav-back">← Back to course</a>'
    else:
        prev_html = f'<a href="ch{n-1}.html" class="chnav-btn chnav-prev">← Chapter {n-1}</a>'

    if n == total_chapters:
        next_html = f'<a href="../{course_code}.html" class="chnav-btn chnav-next chnav-finish">↑ Back to course</a>'
    else:
        next_html = f'<a href="ch{n+1}.html" class="chnav-btn chnav-next">Chapter {n+1} →</a>'

    # Use the existing class .chapter-hero from the course CSS for visual continuity
    hero = (
        f'<div class="chapter-hero" style="background:{gradient};">\n'
        f'  <div class="container">\n'
        f'    <div style="margin-bottom:10px;"><a href="../{course_code}.html" style="color:#fff;opacity:0.85;font-size:13px;text-decoration:none;">← Back to course ({course_title})</a></div>\n'
        f'    <div class="strand-tag">{strand_tag}</div>\n'
        f'    <h1>{emoji} {course_code.upper()}: {title}</h1>\n'
        f'    <p>{subtitle}</p>\n'
        f'  </div>\n'
        f'</div>\n'
    )

    nav_strip = (
        '<div class="chapter-nav" style="display:flex;justify-content:space-between;align-items:center;gap:12px;margin-top:32px;padding-top:24px;border-top:1px solid #e2e8f0;">\n'
        f'  {prev_html}\n'
        f'  {next_html}\n'
        '</div>\n'
    )

    nav_css = (
        '<style>\n'
        '.chnav-btn { padding: 10px 18px; border-radius: 8px; font-size: 14px; font-weight: 600; text-decoration: none; display: inline-flex; align-items: center; gap: 6px; transition: transform .15s, box-shadow .15s; }\n'
        '.chnav-back, .chnav-prev { background: #f1f5f9; color: #1e293b; border: 1px solid #e2e8f0; }\n'
        '.chnav-back:hover, .chnav-prev:hover { background: #e2e8f0; }\n'
        '.chnav-next { background: #2563eb; color: #fff; }\n'
        '.chnav-next:hover { background: #1d4ed8; }\n'
        '.chnav-finish { background: #16a34a; }\n'
        '.chnav-finish:hover { background: #15803d; }\n'
        '</style>\n'
    )

    return (
        head_ch
        + nav_ch
        + '\n'
        + nav_css
        + hero
        + '\n<div class="container" style="padding-top:32px;padding-bottom:64px;">\n'
        + content_ch
        + '\n'
        + nav_strip
        + '</div>\n'
        + '\n'
        + footer_tail
    )


# ---------- Build landing page ----------

def build_landing_page(*, course_code: str, head_block: str, nav_block: str,
                       hero_block: str, resources_slab: str | None,
                       chapter_meta: list, footer_tail: str,
                       course_title: str, emoji: str, strand_tag: str) -> str:
    # Chapter cards
    cards = []
    for n, title, subtitle, gradient, color in chapter_meta:
        short = re.sub(r"^Chapter \d+\s*[:\-—]\s*", "", title)
        cards.append(
            f'    <a href="{course_code}/ch{n}.html" class="chapter-card" '
            f'style="display:block;background:#fff;border:1px solid #e2e8f0;'
            f'border-left:6px solid {color};border-radius:12px;padding:20px 22px;'
            f'text-decoration:none;color:#1e293b;box-shadow:0 1px 2px rgba(15,23,42,.04);'
            f'transition:transform .15s,box-shadow .15s;">\n'
            f'      <div style="font-size:12px;color:{color};font-weight:800;'
            f'text-transform:uppercase;letter-spacing:1.2px;margin-bottom:6px;">Chapter {n}</div>\n'
            f'      <div style="font-size:17px;font-weight:700;margin-bottom:6px;">{short}</div>\n'
            f'      <div style="font-size:13px;color:#64748b;line-height:1.45;">{subtitle}</div>\n'
            f'    </a>\n'
        )

    cards_block = (
        '    <h2 style="font-size:20px;margin:36px 0 16px;color:#1e293b;">Chapters</h2>\n'
        '    <div class="chapter-cards-grid" style="display:grid;'
        'grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px;'
        'margin-bottom:48px;">\n'
        + "".join(cards)
        + '    </div>\n'
    )

    resources_block = (resources_slab or '') + '\n'

    return (
        head_block
        + nav_block
        + '\n'
        + hero_block
        + '\n<div class="container" style="padding-top:32px;padding-bottom:64px;">\n'
        + resources_block
        + cards_block
        + '</div>\n'
        + '\n'
        + footer_tail
    )


# ---------- Per-course pipeline ----------

def process_course(code: str) -> dict:
    course_label, emoji, strand_tag, course_title = COURSES[code]
    src_path = ROOT / "courses" / f"{code}.html"
    out_dir = ROOT / "courses" / code
    out_dir.mkdir(parents=True, exist_ok=True)

    raw = src_path.read_text()
    before_size = len(raw)

    units = find_unit_sections(raw)
    if not units:
        return {"code": code, "skipped": True, "reason": "no unit-sections"}

    head_block, nav_block = extract_head_and_nav(raw)

    # Footer + scripts tail (everything from <footer> to end-of-file)
    footer_tail = find_body_close_segment(raw)

    # Resources block (we'll re-place it in the landing page)
    rb = find_resources_block(raw)
    resources_slab = rb[2] if rb else None

    # Hero block (already on the landing page before unit-sections)
    hero = find_hero(raw)
    hero_slab = hero[2] if hero else ""

    # Per-chapter metadata + page generation
    chapter_meta = []
    chapter_results = []
    total = len(units)
    for n, _s, _e, slab in units:
        title, subtitle, gradient, color = parse_unit_header(slab)
        chapter_meta.append((n, title or f"Chapter {n}", subtitle, gradient, color))

    for (n, _s, _e, slab), (mN, title, subtitle, gradient, color) in zip(units, chapter_meta):
        page = build_chapter_page(
            course_code=code, course_title=course_title, n=n,
            total_chapters=total, gradient=gradient, title=title,
            subtitle=subtitle, strand_tag=strand_tag,
            head_block=head_block, nav_block=nav_block, footer_tail=footer_tail,
            content_slab=slab, emoji=emoji,
        )
        out_path = out_dir / f"ch{n}.html"
        out_path.write_text(page)
        chapter_results.append({
            "n": n, "title": title, "bytes": out_path.stat().st_size,
            "lesson_notes_count": page.count('<details class="lesson-notes">'),
            "has_strip": ('assessment-strip' in page) or ('assessments/' in page),
            "has_nav": 'chapter-nav' in page,
        })

    # Landing page rewrite
    landing = build_landing_page(
        course_code=code,
        head_block=head_block, nav_block=nav_block,
        hero_block=hero_slab, resources_slab=resources_slab,
        chapter_meta=chapter_meta, footer_tail=footer_tail,
        course_title=course_title, emoji=emoji, strand_tag=strand_tag,
    )
    src_path.write_text(landing)

    return {
        "code": code,
        "chapters": chapter_results,
        "landing_before": before_size,
        "landing_after": src_path.stat().st_size,
    }


def main():
    # Skip MHF4U because its agent already produced the per-chapter pages.
    # (We'll re-process it too, to ensure all 10 are consistent.)
    print("Splitting course pages…\n")
    summary = []
    for code in COURSES:
        try:
            r = process_course(code)
            summary.append(r)
            if r.get("skipped"):
                print(f"  [SKIP] {code}: {r.get('reason')}")
                continue
            n_chapters = len(r["chapters"])
            ln_total = sum(c["lesson_notes_count"] for c in r["chapters"])
            print(f"  {code}: {n_chapters} chapter pages, {ln_total} lesson-notes preserved, "
                  f"landing {r['landing_before']}B → {r['landing_after']}B")
        except Exception as e:
            print(f"  [FAIL] {code}: {type(e).__name__}: {e}")
            summary.append({"code": code, "error": str(e)})

    print("\n==== Per-course detail ====")
    for r in summary:
        if r.get("skipped") or r.get("error"):
            continue
        print(f"\n## {r['code']}")
        print(f"  landing: {r['landing_before']}B → {r['landing_after']}B")
        for c in r["chapters"]:
            print(f"  ch{c['n']:>2}: {c['bytes']:>7}B  notes={c['lesson_notes_count']:>2}  "
                  f"strip={'✓' if c['has_strip'] else '✗'}  nav={'✓' if c['has_nav'] else '✗'}  "
                  f"{c['title'][:60]}")


if __name__ == "__main__":
    main()
