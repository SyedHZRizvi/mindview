#!/usr/bin/env python3
"""R2 — Insert a Communication-category rubric block into every
OF unit-test file AND every Final_Exam.html across all 40 courses.

The rubric is wrapped in `<details class="instructor-only">` so it's
visible to teachers/admins/superusers but hidden from students (per
role-gating in functions/_middleware.js + js/role-gated.js).

Idempotent: re-running on a file that already has the rubric skips it.

Owner-approved 2026-06-01.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
ASSESSMENTS = ROOT / 'assessments'

# All 40 course codes — kept in sync with VALID_COURSE_CODES.
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

# The rubric block — the same template applied to every OF + Final.
# instructor-only ensures students never see this; teachers grade with it.
RUBRIC_MARKER = 'Communication Category Rubric'

RUBRIC_HTML = '''
<details class="instructor-only" style="margin-top:24px;border:1px solid #e2e8f0;border-radius:10px;background:#f8fafc;">
<summary style="cursor:pointer;padding:14px 18px;font-weight:800;font-size:15px;color:#1e40af;background:#dbeafe;border-radius:10px;">📝 Communication Category Rubric (instructor-graded)</summary>
<div style="padding:16px 22px 22px;">
<p style="font-size:13px;color:#475569;margin-bottom:12px;">Per Ontario's <em>Growing Success</em> (2010) Achievement Chart, Communication is one of the four equally-weighted categories (25% of the course mark). This rubric is applied to every student-written response (short-answer, extended-response, essay, lab report, deputation, etc.) on this assessment.</p>

<table style="width:100%;border-collapse:collapse;font-size:13px;">
  <thead>
    <tr style="background:#1e40af;color:#fff;">
      <th style="padding:8px 10px;text-align:left;width:22%;border:1px solid #cbd5e1;">Criterion</th>
      <th style="padding:8px 10px;text-align:left;width:19%;border:1px solid #cbd5e1;">Level 1 — Limited (50–59%)</th>
      <th style="padding:8px 10px;text-align:left;width:19%;border:1px solid #cbd5e1;">Level 2 — Some (60–69%)</th>
      <th style="padding:8px 10px;text-align:left;width:20%;border:1px solid #cbd5e1;">Level 3 — Considerable (70–79%)</th>
      <th style="padding:8px 10px;text-align:left;width:20%;border:1px solid #cbd5e1;">Level 4 — Thorough (80–100%)</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td style="padding:8px 10px;border:1px solid #cbd5e1;background:#f1f5f9;"><strong>Expression and organisation of ideas</strong></td>
      <td style="padding:8px 10px;border:1px solid #cbd5e1;">Ideas expressed with limited clarity; little organisation.</td>
      <td style="padding:8px 10px;border:1px solid #cbd5e1;">Ideas expressed with some clarity; some organisation.</td>
      <td style="padding:8px 10px;border:1px solid #cbd5e1;">Ideas expressed clearly and organised effectively.</td>
      <td style="padding:8px 10px;border:1px solid #cbd5e1;">Ideas expressed with clarity, precision, and a high degree of organisation.</td>
    </tr>
    <tr>
      <td style="padding:8px 10px;border:1px solid #cbd5e1;background:#f1f5f9;"><strong>Communication for different audiences and purposes</strong></td>
      <td style="padding:8px 10px;border:1px solid #cbd5e1;">Limited awareness of audience/purpose; tone often inappropriate.</td>
      <td style="padding:8px 10px;border:1px solid #cbd5e1;">Some awareness of audience/purpose; tone occasionally inappropriate.</td>
      <td style="padding:8px 10px;border:1px solid #cbd5e1;">Consistently appropriate tone, register, and address to audience.</td>
      <td style="padding:8px 10px;border:1px solid #cbd5e1;">Tone, register, voice, and address are precisely matched to audience and purpose.</td>
    </tr>
    <tr>
      <td style="padding:8px 10px;border:1px solid #cbd5e1;background:#f1f5f9;"><strong>Use of conventions, vocabulary, terminology</strong></td>
      <td style="padding:8px 10px;border:1px solid #cbd5e1;">Frequent errors in grammar, spelling, punctuation; little discipline-specific vocabulary.</td>
      <td style="padding:8px 10px;border:1px solid #cbd5e1;">Some errors that occasionally impede meaning; emerging use of discipline-specific vocabulary.</td>
      <td style="padding:8px 10px;border:1px solid #cbd5e1;">Few errors; consistent use of discipline-specific vocabulary.</td>
      <td style="padding:8px 10px;border:1px solid #cbd5e1;">Virtually error-free; precise and varied use of discipline-specific vocabulary.</td>
    </tr>
  </tbody>
</table>

<p style="font-size:12px;color:#64748b;margin-top:14px;font-style:italic;">Level 3 represents the Provincial Standard. Use the most-recent and most-consistent evidence across multiple Communication tasks (this assessment, prior FOR work, written responses on AS quizzes, oral presentations) when assigning a course-level Communication mark. <em>Growing Success</em>, 2010, p. 17.</p>
</div>
</details>
'''


def patch_assessment(path: Path) -> str:
    text = path.read_text()
    if RUBRIC_MARKER in text:
        return f"  ⇢ {path.relative_to(ROOT)} — already has Communication rubric, skipped"

    # Insert just BEFORE the closing </body> tag if the file has one,
    # otherwise just before the final aggregate answer-key block.
    # The aggregate answer key (instructor-only details) is typically at the
    # end of the file. We want the rubric AFTER all the questions but with
    # the same role-gating treatment.
    if '</body>' in text:
        new_text = text.replace('</body>', RUBRIC_HTML + '\n</body>', 1)
    else:
        new_text = text + RUBRIC_HTML

    path.write_text(new_text)
    return f"  ✓ {path.relative_to(ROOT)} — Communication rubric added"


def main():
    print("R2 — adding Communication Category Rubric to every OF + Final Exam")
    print()
    total = 0
    skipped = 0
    for code in COURSES:
        # Pattern 1 — directory layout: assessments/{code}/Unit{N}_{Name}_OF.html
        #             and assessments/{code}/Final_Exam.html
        d = ASSESSMENTS / code
        files_to_patch = []
        if d.exists() and d.is_dir():
            for path in sorted(d.glob('*.html')):
                name = path.name
                if '_OF.html' in name or name == 'Final_Exam.html':
                    files_to_patch.append(path)
        # Pattern 2 — flat layout: assessments/{code}_ch{N}_of.html
        #             and assessments/{code}_final_exam.html
        for path in sorted(ASSESSMENTS.glob(f'{code}_*.html')):
            name = path.name
            if name.endswith('_of.html') or name == f'{code}_final_exam.html':
                files_to_patch.append(path)
        if not files_to_patch:
            print(f"  (no OF/Final files found for {code} — skipped)")
            continue
        for path in files_to_patch:
            result = patch_assessment(path)
            if '⇢' in result:
                skipped += 1
            else:
                total += 1
    print(f"\n  total patched: {total}")
    print(f"  total skipped (already present): {skipped}")


if __name__ == '__main__':
    main()
