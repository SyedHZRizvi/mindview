#!/usr/bin/env python3
"""R3 — Add a "Communication Practice" extended-response item to every
AS practice-quiz file in the 25 humanities / English / business / GCE
courses + ENG4U (since ENG4U is in the baseline 10 that go to production).

The extended-response prompt is course-and-chapter-specific: it
references the chapter topic in the prompt so students write about THIS
unit's material. The accompanying rubric is the standard 4-level
Communication rubric, wrapped in `<details class="instructor-only">`
so students don't see the rubric while writing.

Per Ontario's Growing Success (2010): Communication is one of four
equally-weighted Achievement Chart categories (25%). Practice quizzes
(AS = Assessment AS Learning) were previously 100% multiple-choice,
which is K/U-heavy. This adds a Communication-category opportunity to
every AS quiz.

Idempotent: re-running on a file that already has Communication
Practice skips it.

Owner-approved 2026-06-01.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
ASSESSMENTS = ROOT / 'assessments'

# 25 courses where Communication is the dominant or co-dominant
# Achievement-Chart category. Includes ENG4U so the baseline-prod course
# gets the upgrade too.
COMM_HEAVY_COURSES = sorted([
    'eng2d', 'eng3u', 'eng4u',                          # English
    'chc2d', 'chw3m', 'chy4u',                          # History
    'chv2o', 'cpc3o', 'cpw4u',                          # Civics / Politics
    'clu3m', 'cln4u',                                   # Law
    'cgf3m', 'cgw4u',                                   # Geography
    'hsc4m',                                            # World Cultures
    'baf3m', 'bat4m', 'bbb4m', 'boh4m',                 # Business
    'hfn3m', 'hfa4m',                                   # Food & Nutrition
    'glc2o', 'gwl3o', 'gpp3o', 'gle3o', 'gle4o',        # GCE
])

MARKER = 'Communication Practice'


def chapter_topic_from_filename(filename: str) -> str:
    """Convert "Chapter1_Issues_That_Matter_AS.html" → "Issues That Matter"
    or "Unit2_The_Essay_AS.html" → "The Essay".
    """
    name = filename.rsplit('.', 1)[0]
    name = re.sub(r'_AS$', '', name)
    parts = name.split('_')
    # Drop leading "Chapter1" / "Unit3" prefix
    if parts and (parts[0].lower().startswith('chapter') or parts[0].lower().startswith('unit')):
        parts = parts[1:]
    return ' '.join(parts).strip() or 'this unit\'s content'


def build_item_html(item_number: int, item_id: str, topic: str) -> str:
    """Build the new extended-response item HTML to append to an AS quiz."""
    return f'''
<div class="q comm-practice" style="margin-top:32px;padding:20px 22px;background:#eff6ff;border:1px dashed #93c5fd;border-radius:10px;">
  <div style="font-size:11px;font-weight:800;color:#1e40af;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px;">📝 Communication Practice · Extended Response</div>
  <p style="font-weight:600;margin-bottom:6px;">Q{item_number}. In 100–150 words, explain <em>{topic}</em> in your own words.</p>
  <p style="font-size:13px;color:#475569;margin-bottom:10px;">Pay attention to clarity, organisation of ideas, use of discipline-specific vocabulary, and grammatical conventions. This question evaluates the <strong>Communication</strong> category of Ontario\'s Achievement Chart (25%). There is no single correct answer — your teacher will assess your response against the rubric below.</p>
  <textarea id="{item_id}" name="{item_id}" rows="6" style="width:100%;padding:10px 12px;border:1px solid #cbd5e1;border-radius:6px;font-family:inherit;font-size:14px;line-height:1.5;" placeholder="Write your response here (100–150 words)…"></textarea>

  <details class="instructor-only" style="margin-top:12px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;">
    <summary style="cursor:pointer;padding:10px 14px;font-weight:700;font-size:13px;color:#1e40af;">🔒 Communication Rubric (instructor-graded)</summary>
    <div style="padding:12px 16px;font-size:12.5px;line-height:1.5;">
      <strong>Level 1 — Limited (50–59%):</strong> Ideas expressed with limited clarity; frequent errors in conventions; little discipline-specific vocabulary.<br>
      <strong>Level 2 — Some (60–69%):</strong> Ideas expressed with some clarity; some errors that occasionally impede meaning; emerging discipline-specific vocabulary.<br>
      <strong>Level 3 — Considerable (70–79%) [Provincial Standard]:</strong> Ideas expressed clearly and organised effectively; few errors; consistent use of discipline-specific vocabulary.<br>
      <strong>Level 4 — Thorough (80–100%):</strong> Ideas expressed with clarity and precision; virtually error-free; precise and varied use of discipline-specific vocabulary; sense of voice / audience awareness.
    </div>
  </details>
</div>'''


def patch_as_file(path: Path) -> str:
    text = path.read_text()
    if MARKER in text:
        return f"  ⇢ {path.relative_to(ROOT)} — already has Communication Practice, skipped"

    # Figure out the next question number. We can count existing
    # `class="sol"` blocks (one per current question) as a proxy.
    n_existing = len(re.findall(r'class="sol(?:\s+instructor-only)?"', text))
    next_q_num = n_existing + 1
    item_id = f'q{next_q_num}-comm'
    topic = chapter_topic_from_filename(path.name)

    new_item = build_item_html(next_q_num, item_id, topic)

    # Place it before any aggregate-key / footer / closing </body>. Same
    # strategy as R2: insert immediately before </body>.
    if '</body>' in text:
        new_text = text.replace('</body>', new_item + '\n</body>', 1)
    else:
        new_text = text + new_item

    path.write_text(new_text)
    return f"  ✓ {path.relative_to(ROOT)} — added Q{next_q_num} Communication Practice"


def main():
    print("R3 — adding Communication Practice extended-response item to AS quizzes")
    print(f"     ({len(COMM_HEAVY_COURSES)} courses, humanities / English / business / GCE)")
    print()
    total = 0
    skipped = 0
    for code in COMM_HEAVY_COURSES:
        files_to_patch = []
        # Pattern 1 — directory layout
        d = ASSESSMENTS / code
        if d.exists() and d.is_dir():
            files_to_patch.extend(sorted(d.glob('*_AS.html')))
        # Pattern 2 — flat layout: assessments/{code}_ch{N}_as.html
        for path in sorted(ASSESSMENTS.glob(f'{code}_ch*_as.html')):
            files_to_patch.append(path)
        if not files_to_patch:
            print(f"  (no AS files found for {code} — skipped)")
            continue
        for path in files_to_patch:
            result = patch_as_file(path)
            if '⇢' in result:
                skipped += 1
            else:
                total += 1
    print(f"\n  total patched: {total}")
    print(f"  total skipped (already present): {skipped}")


if __name__ == '__main__':
    main()
