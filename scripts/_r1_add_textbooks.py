#!/usr/bin/env python3
"""R1 — Insert a "Required Learning Resources" block into every
courses/{code}_curriculum.html, citing the standard / Trillium-aligned
textbook for that course. Idempotent: re-running on a file that already
has the section is a no-op.

Owner-approved 2026-06-01.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent

# (publisher · title · edition · note) per Ontario course.
# Where Ontario does NOT have a standard / Trillium-listed text, we name the
# closest available commercial resource AND Ministry documents that
# substitute. "ISBN to be confirmed" — we deliberately omit ISBNs since
# editions change frequently; the school administrator should confirm the
# current edition before purchasing.
TEXTBOOKS = {
    # ──── Mathematics (Nelson dominant) ────
    'mcr3u': {
        'primary':   'Nelson Education — <em>Functions 11</em> (Erdman, Mendelson, Speijer et al.)',
        'alt':       'McGraw-Hill Ryerson — <em>Functions 11</em>',
        'reference': 'Ontario Ministry of Education — <em>The Ontario Curriculum, Grades 11 &amp; 12: Mathematics</em> (2007, Revised)',
    },
    'mhf4u': {
        'primary':   'Nelson Education — <em>Advanced Functions 12</em> (Erdman, Mendelson et al.)',
        'alt':       'McGraw-Hill Ryerson — <em>Advanced Functions 12</em>',
        'reference': 'Ministry of Education — Mathematics 2007 (Revised)',
    },
    'mcv4u': {
        'primary':   'Nelson Education — <em>Calculus and Vectors 12</em> (McAskill, Watt, Hamilton et al.)',
        'alt':       'McGraw-Hill Ryerson — <em>Calculus and Vectors 12</em>',
        'reference': 'Ministry of Education — Mathematics 2007 (Revised)',
    },
    'mdm4u': {
        'primary':   'Nelson Education — <em>Mathematics of Data Management 12</em> (Stewart, Davis et al.)',
        'alt':       'McGraw-Hill Ryerson — <em>Mathematics of Data Management</em>',
        'reference': 'Ministry of Education — Mathematics 2007 (Revised)',
    },
    'mct3m': {
        'primary':   'Nelson Education — <em>Mathematics for College Technology 11</em>',
        'alt':       'McGraw-Hill Ryerson — <em>Mathematics for College Technology 11</em>',
        'reference': 'Ministry of Education — Mathematics 2007 (Revised), college-pathway strand',
    },
    'mct4m': {
        'primary':   'Nelson Education — <em>Mathematics for College Technology 12</em>',
        'alt':       'McGraw-Hill Ryerson — <em>Mathematics for College Technology 12</em>',
        'reference': 'Ministry of Education — Mathematics 2007 (Revised), college-pathway strand',
    },

    # ──── Sciences ────
    'snc2d': {
        'primary':   'Nelson Education — <em>Science Perspectives 10</em> (Ritter, Plumb, Lacy et al.)',
        'alt':       'McGraw-Hill Ryerson — <em>On Science 10</em>',
        'reference': 'Ministry of Education — <em>The Ontario Curriculum, Grades 9 &amp; 10: Science</em> (2008, Revised)',
    },
    'sbi3u': {
        'primary':   'Nelson Education — <em>Biology 11</em> (Ritter, Ritter, Heads et al.)',
        'alt':       'McGraw-Hill Ryerson — <em>Biology 11</em>',
        'reference': 'Ministry of Education — Science 2008 (Revised)',
    },
    'sbi4u': {
        'primary':   'Nelson Education — <em>Biology 12</em> (Ritter, Ritter, Heads et al.)',
        'alt':       'McGraw-Hill Ryerson — <em>Biology 12</em>',
        'reference': 'Ministry of Education — Science 2008 (Revised)',
    },
    'sch3u': {
        'primary':   'Nelson Education — <em>Chemistry 11</em> (Lalonde, Mendelson et al.)',
        'alt':       'McGraw-Hill Ryerson — <em>Chemistry 11</em>',
        'reference': 'Ministry of Education — Science 2008 (Revised)',
    },
    'sch4u': {
        'primary':   'Nelson Education — <em>Chemistry 12</em> (Lalonde et al.)',
        'alt':       'McGraw-Hill Ryerson — <em>Chemistry 12</em>',
        'reference': 'Ministry of Education — Science 2008 (Revised)',
    },
    'sph3u': {
        'primary':   'Nelson Education — <em>Physics 11</em>',
        'alt':       'Pearson Canada — <em>Physics 11</em>',
        'reference': 'Ministry of Education — Science 2008 (Revised)',
    },
    'sph4u': {
        'primary':   'Nelson Education — <em>Physics 12</em>',
        'alt':       'Pearson Canada — <em>Physics 12</em>',
        'reference': 'Ministry of Education — Science 2008 (Revised)',
    },

    # ──── English ────
    'eng2d': {
        'primary':   'Nelson Education — <em>Echoes 10: Fiction, Media, and Non-fiction</em> (anthology)',
        'alt':       'Pearson Canada — <em>Reference Points</em>',
        'reference': 'Ministry of Education — <em>The Ontario Curriculum, Grades 9 &amp; 10: English</em> (2007, Revised)',
        'novels':    [
            'William Shakespeare — <em>Romeo and Juliet</em>',
            'Harper Lee — <em>To Kill a Mockingbird</em> &nbsp;OR&nbsp; William Golding — <em>Lord of the Flies</em>',
            'Indigenous-voice anthology selection (e.g., excerpts from <em>An Anthology of Canadian Native Literature in English</em>, Moses &amp; Goldie, eds.)',
        ],
    },
    'eng3u': {
        'primary':   'Nelson Education — <em>Reference Points: Reading and Writing for Success</em> (Grade 11 anthology)',
        'alt':       'Pearson Canada — <em>ResourceLines 11</em>',
        'reference': 'Ministry of Education — <em>The Ontario Curriculum, Grades 11 &amp; 12: English</em> (2007, Revised)',
        'novels':    [
            'William Shakespeare — <em>Macbeth</em>',
            'F. Scott Fitzgerald — <em>The Great Gatsby</em> &nbsp;OR&nbsp; Yann Martel — <em>Life of Pi</em>',
            'Richard Wagamese — <em>Indian Horse</em> (Indigenous-voice required reading)',
            'Short-story / poetry anthology drawn from the primary text',
        ],
    },
    'eng4u': {
        'primary':   'Nelson Education — <em>Echoes 12: Fiction, Media, and Non-fiction</em> (anthology)',
        'alt':       'Pearson Canada — <em>Inquiry into Life and Language</em>',
        'reference': 'Ministry of Education — English 2007 (Revised)',
        'novels':    [
            'William Shakespeare — <em>Hamlet</em>',
            'Margaret Atwood — <em>The Handmaid\'s Tale</em>',
            'Chinua Achebe — <em>Things Fall Apart</em> &nbsp;OR&nbsp; Toni Morrison — <em>Beloved</em>',
            'Canadian poetry anthology (Atwood, Birney, Page, Purdy, Ondaatje, Brand, etc.)',
        ],
    },

    # ──── Computer Studies (no Trillium-listed standard) ────
    'ics3u': {
        'primary':   'Warren Sande &amp; Carter Sande — <em>Hello World! Computer Programming for Kids and Other Beginners</em> (Manning, 3rd ed.) — open companion materials at <a href="https://helloworldbook.com/" target="_blank" rel="noopener">helloworldbook.com</a>',
        'alt':       'Allen Downey — <em>Think Python (2nd ed.)</em> (free at greenteapress.com/wp/think-python-2e/)',
        'reference': 'Ministry of Education — <em>The Ontario Curriculum, Grades 10 to 12: Computer Studies</em> (2008, Revised); official Python 3 docs at <a href="https://docs.python.org/3/" target="_blank" rel="noopener">docs.python.org/3</a>',
    },
    'ics4u': {
        'primary':   'Mark Lutz — <em>Learning Python</em> (O\'Reilly, 5th ed.) — companion code on the publisher\'s site',
        'alt':       'Allen Downey — <em>Think Python</em> + Brad Miller &amp; David Ranum — <em>Problem Solving with Algorithms and Data Structures Using Python</em> (free at runestone.academy)',
        'reference': 'Ministry of Education — Computer Studies 2008 (Revised); CS Circles free curriculum at <a href="https://cscircles.cemc.uwaterloo.ca/" target="_blank" rel="noopener">cscircles.cemc.uwaterloo.ca</a>',
    },

    # ──── Canadian and World Studies ────
    'chv2o': {
        'primary':   'Nelson Education — <em>Civics Today</em> (Hutchinson, Eaton et al.)',
        'alt':       'Pearson Canada — <em>Canadian Civics</em>',
        'reference': 'Ministry of Education — <em>The Ontario Curriculum, Grades 9 &amp; 10: Canadian and World Studies</em> (2018, Revised)',
    },
    'cpc3o': {
        'primary':   'No Trillium-listed standard for CPC3O. Recommended: Pearson Canada — <em>Politics in Action: Making Change</em> (custom anthology)',
        'alt':       'Ministry of Education curriculum policy document plus current-events sources (CBC, the Globe and Mail, Toronto Star, parliamentary Hansard)',
        'reference': 'Ministry of Education — <em>The Ontario Curriculum, Grades 9 to 12: Canadian and World Studies</em> (2018, Revised), Politics strand',
    },
    'cpw4u': {
        'primary':   'Pearson Canada — <em>Canadian and World Politics</em> (Coppen)',
        'alt':       'Nelson Education — <em>Politics and You</em>',
        'reference': 'Ministry of Education — CWS 2018 (Revised), Politics strand',
    },
    'chc2d': {
        'primary':   'McGraw-Hill Ryerson — <em>Canada: Face of a Nation</em> (Hundey, Magarrey, Pettit et al.)',
        'alt':       'Nelson Education — <em>Canadian History since World War I</em>',
        'reference': 'Ministry of Education — <em>Canadian and World Studies</em> (2018, Revised), History strand',
    },
    'chw3m': {
        'primary':   'Pearson Canada — <em>Worlds of History: A Comparative Reader</em> (Reilly)',
        'alt':       'Nelson Education — <em>Crossroads: A Meeting of Nations</em>',
        'reference': 'Ministry of Education — CWS 2018 (Revised), History strand',
    },
    # chy4u already has a textbook section — script is idempotent and will skip it.
    'chy4u': {
        'primary':   'Pearson Canada — <em>Legacy: The West and the World</em> (Cranny)',
        'alt':       'Nelson Education — <em>Pathways: Civilizations Through Time</em>',
        'reference': 'Ministry of Education — CWS 2018 (Revised), History strand',
    },
    'clu3m': {
        'primary':   'Emond Publishing — <em>Understanding Canadian Law</em> (Roberts, Schwartz et al.)',
        'alt':       'Pearson Canada — <em>All About Law</em> (Liepner, Boyko)',
        'reference': 'Ministry of Education — CWS 2018 (Revised), Law strand',
    },
    'cln4u': {
        'primary':   'Emond Publishing — <em>Canadian and International Law</em>',
        'alt':       'Pearson Canada — <em>Dimensions of Law: Canadian and International Law in the 21st Century</em>',
        'reference': 'Ministry of Education — CWS 2018 (Revised), Law strand',
    },
    'cgf3m': {
        'primary':   'Pearson Canada — <em>Physical Geography of Canada and the World</em> (Quinlan, Bain et al.)',
        'alt':       'Nelson Education — <em>Physical Geography</em>',
        'reference': 'Ministry of Education — CWS 2018 (Revised), Geography strand',
    },
    'cgw4u': {
        'primary':   'Pearson Canada — <em>World Issues</em> (Earle, Clarke et al.)',
        'alt':       'Nelson Education — <em>Global Connections: Geographic Perspectives on World Issues</em>',
        'reference': 'Ministry of Education — CWS 2018 (Revised), Geography strand',
    },

    # ──── Business Studies ────
    'baf3m': {
        'primary':   'McGraw-Hill Ryerson — <em>Accounting 1</em> (Syme, Mitchell et al.)',
        'alt':       'Pearson Canada — <em>Accounting Fundamentals</em>',
        'reference': 'Ministry of Education — <em>The Ontario Curriculum, Grades 11 &amp; 12: Business Studies</em> (2006, Revised), Accounting strand',
    },
    'bat4m': {
        'primary':   'McGraw-Hill Ryerson — <em>Accounting 2</em> (Syme, Mitchell et al.)',
        'alt':       'Pearson Canada — <em>Accounting Principles</em>',
        'reference': 'Ministry of Education — Business Studies 2006 (Revised), Accounting strand',
    },
    'bbb4m': {
        'primary':   'Nelson Education — <em>International Business: Trade and Production</em>',
        'alt':       'Pearson Canada — <em>International Business: Trade and Production</em>',
        'reference': 'Ministry of Education — Business Studies 2006 (Revised), International Business strand',
    },
    'boh4m': {
        'primary':   'Nelson Education — <em>Management Fundamentals: A Canadian Approach</em>',
        'alt':       'Pearson Canada — <em>Business Leadership: Management Fundamentals</em>',
        'reference': 'Ministry of Education — Business Studies 2006 (Revised), Management strand',
    },

    # ──── Social Sciences and Humanities ────
    'hfn3m': {
        'primary':   'Pearson Canada — <em>Food for Today</em> (Kowtaluk, Kopan-Johnson)',
        'alt':       'Nelson Education — <em>Nutrition and You</em>',
        'reference': 'Ministry of Education — <em>The Ontario Curriculum, Grades 9 to 12: Social Sciences and Humanities</em> (2013, Revised), Family Studies discipline, Food &amp; Nutrition strand',
    },
    'hfa4m': {
        'primary':   'Nelson Education — <em>Nutrition for Health</em>',
        'alt':       'Pearson Canada — <em>Foods and Nutrition: A Canadian Approach</em>',
        'reference': 'Ministry of Education — SSH 2013 (Revised), Family Studies discipline',
    },
    'hsc4m': {
        'primary':   'Pearson Canada — <em>World Cultures</em> (Lehr, Karras)',
        'alt':       'Nelson Education — <em>Many Faces, Many Voices</em>',
        'reference': 'Ministry of Education — SSH 2013 (Revised), Equity Studies discipline',
    },

    # ──── Guidance and Career Education ────
    'glc2o': {
        'primary':   'Ministry of Education — <em>Creating Pathways to Success: An Education and Career/Life Planning Program for Ontario Schools</em> (2013)',
        'alt':       'Pearson Canada — <em>Career Studies</em> (workbook)',
        'reference': 'Ministry of Education — <em>The Ontario Curriculum, Grades 9 to 12: Guidance and Career Education</em> (2006, Revised)',
    },
    'gwl3o': {
        'primary':   'Pearson Canada — <em>Pathways: Career Studies</em>',
        'alt':       'Ministry of Education — <em>Creating Pathways to Success</em> (2013)',
        'reference': 'Ministry of Education — GCE 2006 (Revised)',
    },
    'gpp3o': {
        'primary':   'Pearson Canada — <em>Leadership and Peer Support</em>',
        'alt':       'Nelson Education — <em>Leadership: An Open Approach</em>',
        'reference': 'Ministry of Education — GCE 2006 (Revised)',
    },
    'gle3o': {
        'primary':   'Pearson Canada — <em>Learning Strategies: Skills for Success in Secondary School</em>',
        'alt':       'Ministry of Education — <em>Achieving Excellence</em> + supplementary study-skills materials',
        'reference': 'Ministry of Education — GCE 2006 (Revised)',
    },
    'gle4o': {
        'primary':   'Pearson Canada — <em>Adult Learning Strategies: Skills for Success After Secondary School</em>',
        'alt':       'CMEC / Ministry of Education resources on lifelong-learning skills',
        'reference': 'Ministry of Education — GCE 2006 (Revised); Ministry — <em>Creating Pathways to Success</em> (2013)',
    },
}


def build_resources_block(code, data):
    """Construct the HTML for the Required Learning Resources block."""
    parts = ['<h2>2. Required Learning Resources</h2>',
             '<p>Recommended primary text and supplementary resources, aligned with the Ontario Ministry of Education\'s policy document and reflective of texts that have historically appeared on the Trillium List for this course. The school administrator should confirm the current edition before purchase.</p>',
             '<table>',
             '<tr><th style="width:24%;">Type</th><th>Resource</th></tr>',
             f'<tr><td><strong>Primary text</strong></td><td>{data["primary"]}</td></tr>',
             f'<tr><td><strong>Alternative / supplementary</strong></td><td>{data["alt"]}</td></tr>',
             f'<tr><td><strong>Curriculum policy &amp; reference</strong></td><td>{data["reference"]}</td></tr>',
             '</table>']

    if 'novels' in data:
        parts.append('<h3>Required novels &amp; anchor texts</h3>')
        parts.append('<ul>')
        for n in data['novels']:
            parts.append(f'  <li>{n}</li>')
        parts.append('</ul>')

    parts.append('<div class="callout"><strong>Inspection note.</strong> Per Ontario\'s policy for private inspected schools (PIS Memorandum 2022B): the primary text listed above is the resource an Inspector should expect to see on a student\'s desk or device when reviewing this course. The "alternative / supplementary" entry is acceptable as a substitute. Online-only resources are acceptable for courses without a Trillium-listed text (Computer Studies, GCE).</div>')
    return '\n'.join(parts)


def patch_curriculum_page(code):
    path = ROOT / 'courses' / f'{code}_curriculum.html'
    if not path.exists():
        return f"  ✗ {code}: curriculum sub-page missing"
    text = path.read_text()
    if 'Required Learning Resources' in text:
        return f"  ⇢ {code}: already has Required Learning Resources — skipped"
    if code not in TEXTBOOKS:
        return f"  ⚠ {code}: no TEXTBOOKS data — skipped"

    # Flexible insertion across three known curriculum-page formats:
    #   (a) "<h2>1. Course Description</h2>" — Wave-2/3 humanities-style
    #   (b) "<h2>1. Course Identification</h2>" — Math/Sciences/Business flat
    #   (c) "<h2>Course Description</h2>" / "<h2>Course Overview</h2>" —
    #       MCV4U + SCH3U/4U pages (no number prefix)
    # In every case the insertion strategy is: place the new block right
    # before the SECOND <h2> in the document, since the first <h2> is
    # always the Course Description / Course Overview.
    headings = list(re.finditer(r'<h2[^>]*>', text))
    if len(headings) < 2:
        return f"  ✗ {code}: couldn't locate insertion point (fewer than 2 <h2>s)"
    # Find the start of the second <h2> — that's our insertion point.
    second_h2_start = headings[1].start()
    # Class is a closure; build a small Match-like object for the rest of
    # the function. Since we only use m.end(1) below, define a placeholder.

    class _M:
        def end(self, _): return second_h2_start
    m = _M()

    block = build_resources_block(code, TEXTBOOKS[code])
    new_text = text[:m.end(1)] + '\n\n' + block + '\n\n' + text[m.end(1):]

    # Now renumber the existing <h2>2., <h2>3., ... by +1 since we inserted
    # a new <h2>2.
    def shift(match):
        n = int(match.group(1))
        return f'<h2>{n + 1}. '
    # Be careful — only renumber the headings AFTER our insertion point
    insertion_marker = '<h2>2. Required Learning Resources</h2>'
    head_idx = new_text.index(insertion_marker) + len(insertion_marker)
    before = new_text[:head_idx]
    after = new_text[head_idx:]
    after = re.sub(r'<h2>(\d+)\. ', shift, after)
    new_text = before + after

    path.write_text(new_text)
    return f"  ✓ {code}: inserted Required Learning Resources + renumbered sections"


def main():
    print("R1 — adding Required Learning Resources to curriculum sub-pages")
    print()
    for code in sorted(TEXTBOOKS):
        print(patch_curriculum_page(code))


if __name__ == '__main__':
    main()
