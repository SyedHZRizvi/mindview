#!/usr/bin/env python3
"""R1b — REPLACE the (text-only) Required Learning Resources block on
every courses/{code}_curriculum.html with a comprehensive LINKED
resources section.

Five tiers per course:
  1. Ontario Ministry curriculum page  (always linked, free, authoritative)
  2. Primary text                       (Trillium-aligned, publisher link)
  3. Free supplementary online textbooks (OpenStax, CK-12, Khan, etc.)
  4. Required novels & anchor texts      (English / Humanities — linked
                                          to Folger, Gutenberg, CBC Books,
                                          publisher pages where useful)
  5. Articles, primary sources, current-events  (Civics, Law, History,
                                          Geography, Business, GCE)

Idempotent: deletes any prior "Required Learning Resources" block and
re-inserts the new one. Re-running is safe.

Owner-approved 2026-06-01.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent

# Ontario DCP discipline-level URLs (every URL below was the published
# DCP path at last review; the discipline-level pages are stable.
# Per-course pages exist for most disciplines but URL slugs can shift,
# so we link to the stable discipline page).
DCP = {
    'math':     ('Ontario Ministry — Mathematics (2007, Revised)',
                 'https://www.dcp.edu.gov.on.ca/en/curriculum/secondary-mathematics'),
    'science':  ('Ontario Ministry — Science (2008, Revised)',
                 'https://www.dcp.edu.gov.on.ca/en/curriculum/secondary-science'),
    'english':  ('Ontario Ministry — English (2007, Revised)',
                 'https://www.dcp.edu.gov.on.ca/en/curriculum/secondary-english'),
    'compsci':  ('Ontario Ministry — Computer Studies (2008, Revised)',
                 'https://www.dcp.edu.gov.on.ca/en/curriculum/secondary-computer-studies'),
    'cws':      ('Ontario Ministry — Canadian and World Studies (2018, Revised)',
                 'https://www.dcp.edu.gov.on.ca/en/curriculum/secondary-canadian-and-world-studies'),
    'business': ('Ontario Ministry — Business Studies (2006, Revised)',
                 'https://www.dcp.edu.gov.on.ca/en/curriculum/secondary-business-studies'),
    'ssh':      ('Ontario Ministry — Social Sciences and Humanities (2013, Revised)',
                 'https://www.dcp.edu.gov.on.ca/en/curriculum/secondary-social-sciences-and-humanities'),
    'gce':      ('Ontario Ministry — Guidance and Career Education (2006, Revised)',
                 'https://www.dcp.edu.gov.on.ca/en/curriculum/secondary-guidance-and-career-education'),
}

GROWING_SUCCESS = ('Growing Success (2010) — Ontario assessment, evaluation &amp; reporting policy',
                   'http://www.edu.gov.on.ca/eng/policyfunding/growSuccess.pdf')

CPS = ('Creating Pathways to Success (2013) — Ontario education &amp; career/life-planning framework',
       'http://www.edu.gov.on.ca/eng/document/policy/cps/CreatingPathwaysSuccess.pdf')

# Free / open online resources reused across multiple courses. These are
# free for any student to access; we use the canonical landing pages.
KHAN = lambda subj_url, label: (f'Khan Academy — {label}', subj_url)

# Per-course resource data. Each entry has:
#   ministry      → ['key' from DCP, plus optional per-course Ontario page]
#   primary       → (label, url) for Trillium-aligned primary text
#   alt           → (label, url) — secondary recommendation
#   free_online   → list of (label, url) for free supplementary materials
#   novels        → list of (label, url) for required novels & anchor texts
#                   (most useful for English; humanities may have a few too)
#   primary_sources → list of (label, url) for articles / archives / Hansard
#                   etc. — most useful for History / Civics / Law / Geography
COURSES_DATA = {
    # ──────────── Mathematics ────────────
    'mcr3u': {
        'ministry': ['math'],
        'primary':  ('Nelson Education — Functions 11', 'https://www.nelson.com/secondary/mathematics/functions-11/'),
        'alt':      ('McGraw-Hill Ryerson — Functions 11', 'https://www.mheducation.ca/'),
        'free_online': [
            ('Khan Academy — Algebra II (functions, exponentials, sequences)',
             'https://www.khanacademy.org/math/algebra2'),
            ('OpenStax — College Algebra (free PDF + interactive)',
             'https://openstax.org/details/books/college-algebra-2e'),
            ('CK-12 Flexbook — Algebra II',
             'https://flexbooks.ck12.org/cbook/ck-12-cbse-maths-class-11/'),
        ],
        'novels': [],
        'primary_sources': [],
    },
    'mhf4u': {
        'ministry': ['math'],
        'primary':  ('Nelson Education — Advanced Functions 12', 'https://www.nelson.com/secondary/mathematics/'),
        'alt':      ('McGraw-Hill Ryerson — Advanced Functions 12', 'https://www.mheducation.ca/'),
        'free_online': [
            ('Khan Academy — Precalculus (polynomial, rational, trig, log)',
             'https://www.khanacademy.org/math/precalculus'),
            ('OpenStax — Precalculus 2e (free PDF)',
             'https://openstax.org/details/books/precalculus-2e'),
        ],
        'novels': [], 'primary_sources': [],
    },
    'mcv4u': {
        'ministry': ['math'],
        'primary':  ('Nelson Education — Calculus and Vectors 12', 'https://www.nelson.com/secondary/mathematics/'),
        'alt':      ('McGraw-Hill Ryerson — Calculus and Vectors 12', 'https://www.mheducation.ca/'),
        'free_online': [
            ('Khan Academy — Differential Calculus',
             'https://www.khanacademy.org/math/differential-calculus'),
            ('Paul\'s Online Math Notes — Calculus I (free)',
             'https://tutorial.math.lamar.edu/Classes/CalcI/CalcI.aspx'),
            ('MIT OpenCourseWare — 18.01 Single Variable Calculus',
             'https://ocw.mit.edu/courses/18-01-single-variable-calculus-fall-2006/'),
        ],
        'novels': [], 'primary_sources': [],
    },
    'mdm4u': {
        'ministry': ['math'],
        'primary':  ('Nelson Education — Mathematics of Data Management 12', 'https://www.nelson.com/secondary/mathematics/'),
        'alt':      ('McGraw-Hill Ryerson — Mathematics of Data Management', 'https://www.mheducation.ca/'),
        'free_online': [
            ('Khan Academy — Statistics &amp; Probability',
             'https://www.khanacademy.org/math/statistics-probability'),
            ('OpenIntro Statistics (free PDF, 4th ed.)',
             'https://www.openintro.org/book/os/'),
        ],
        'novels': [],
        'primary_sources': [
            ('Statistics Canada — open Canadian datasets',
             'https://www.statcan.gc.ca/en/start'),
            ('Bank of Canada — historical financial data',
             'https://www.bankofcanada.ca/rates/'),
        ],
    },
    'mct3m': {
        'ministry': ['math'],
        'primary':  ('Nelson Education — Mathematics for College Technology 11', 'https://www.nelson.com/secondary/mathematics/'),
        'alt':      ('McGraw-Hill Ryerson — Mathematics for College Technology 11', 'https://www.mheducation.ca/'),
        'free_online': [
            ('Khan Academy — Algebra II',
             'https://www.khanacademy.org/math/algebra2'),
        ],
        'novels': [], 'primary_sources': [],
    },
    'mct4m': {
        'ministry': ['math'],
        'primary':  ('Nelson Education — Mathematics for College Technology 12', 'https://www.nelson.com/secondary/mathematics/'),
        'alt':      ('McGraw-Hill Ryerson — Mathematics for College Technology 12', 'https://www.mheducation.ca/'),
        'free_online': [
            ('Khan Academy — Precalculus',
             'https://www.khanacademy.org/math/precalculus'),
        ],
        'novels': [], 'primary_sources': [],
    },

    # ──────────── Sciences ────────────
    'snc2d': {
        'ministry': ['science'],
        'primary':  ('Nelson Education — Science Perspectives 10', 'https://www.nelson.com/secondary/science/'),
        'alt':      ('McGraw-Hill Ryerson — On Science 10', 'https://www.mheducation.ca/'),
        'free_online': [
            ('Khan Academy — High School Biology / Chemistry / Physics',
             'https://www.khanacademy.org/science'),
            ('OpenStax — Concepts of Biology (free)',
             'https://openstax.org/details/books/concepts-biology'),
            ('PhET Simulations — Sciences interactive labs',
             'https://phet.colorado.edu/'),
        ],
        'novels': [], 'primary_sources': [],
    },
    'sbi3u': {
        'ministry': ['science'],
        'primary':  ('Nelson Education — Biology 11', 'https://www.nelson.com/secondary/science/'),
        'alt':      ('McGraw-Hill Ryerson — Biology 11', 'https://www.mheducation.ca/'),
        'free_online': [
            ('Khan Academy — High School Biology',
             'https://www.khanacademy.org/science/high-school-biology'),
            ('OpenStax — Biology 2e (free, full textbook)',
             'https://openstax.org/details/books/biology-2e'),
            ('CK-12 Flexbook — Biology',
             'https://flexbooks.ck12.org/cbook/ck-12-biology-flexbook-2.0/'),
        ],
        'novels': [], 'primary_sources': [],
    },
    'sbi4u': {
        'ministry': ['science'],
        'primary':  ('Nelson Education — Biology 12', 'https://www.nelson.com/secondary/science/'),
        'alt':      ('McGraw-Hill Ryerson — Biology 12', 'https://www.mheducation.ca/'),
        'free_online': [
            ('Khan Academy — AP/College Biology',
             'https://www.khanacademy.org/science/ap-biology'),
            ('OpenStax — Biology 2e',
             'https://openstax.org/details/books/biology-2e'),
            ('NCBI — gene/protein/literature database (molecular genetics)',
             'https://www.ncbi.nlm.nih.gov/'),
        ],
        'novels': [], 'primary_sources': [],
    },
    'sch3u': {
        'ministry': ['science'],
        'primary':  ('Nelson Education — Chemistry 11', 'https://www.nelson.com/secondary/science/'),
        'alt':      ('McGraw-Hill Ryerson — Chemistry 11', 'https://www.mheducation.ca/'),
        'free_online': [
            ('Khan Academy — Chemistry',
             'https://www.khanacademy.org/science/chemistry'),
            ('OpenStax — Chemistry 2e (free)',
             'https://openstax.org/details/books/chemistry-2e'),
            ('Periodic Table of Elements (Ptable, interactive)',
             'https://ptable.com/'),
        ],
        'novels': [], 'primary_sources': [],
    },
    'sch4u': {
        'ministry': ['science'],
        'primary':  ('Nelson Education — Chemistry 12', 'https://www.nelson.com/secondary/science/'),
        'alt':      ('McGraw-Hill Ryerson — Chemistry 12', 'https://www.mheducation.ca/'),
        'free_online': [
            ('Khan Academy — Organic Chemistry',
             'https://www.khanacademy.org/science/organic-chemistry'),
            ('MIT OCW — 5.111 Principles of Chemical Science',
             'https://ocw.mit.edu/courses/5-111sc-principles-of-chemical-science-fall-2014/'),
        ],
        'novels': [], 'primary_sources': [],
    },
    'sph3u': {
        'ministry': ['science'],
        'primary':  ('Nelson Education — Physics 11', 'https://www.nelson.com/secondary/science/'),
        'alt':      ('Pearson Canada — Physics 11', 'https://www.pearsoncanada.ca/'),
        'free_online': [
            ('Khan Academy — High School Physics',
             'https://www.khanacademy.org/science/high-school-physics'),
            ('OpenStax — College Physics 2e (free)',
             'https://openstax.org/details/books/college-physics-2e'),
            ('PhET Physics Simulations',
             'https://phet.colorado.edu/en/simulations/category/physics'),
        ],
        'novels': [], 'primary_sources': [],
    },
    'sph4u': {
        'ministry': ['science'],
        'primary':  ('Nelson Education — Physics 12', 'https://www.nelson.com/secondary/science/'),
        'alt':      ('Pearson Canada — Physics 12', 'https://www.pearsoncanada.ca/'),
        'free_online': [
            ('Khan Academy — AP/College Physics',
             'https://www.khanacademy.org/science/ap-college-physics-1'),
            ('OpenStax — University Physics (free, 3 volumes)',
             'https://openstax.org/details/books/university-physics-volume-1'),
            ('MIT OCW — 8.01 Classical Mechanics',
             'https://ocw.mit.edu/courses/8-01sc-classical-mechanics-fall-2016/'),
        ],
        'novels': [], 'primary_sources': [],
    },

    # ──────────── English (most reading-rich subject) ────────────
    'eng2d': {
        'ministry': ['english'],
        'primary':  ('Nelson Education — Echoes 10 anthology', 'https://www.nelson.com/secondary/english/'),
        'alt':      ('Pearson Canada — Reference Points anthology', 'https://www.pearsoncanada.ca/'),
        'free_online': [
            ('Purdue OWL — academic writing &amp; citation guide',
             'https://owl.purdue.edu/'),
            ('CBC Books — Canadian literature reviews &amp; author interviews',
             'https://www.cbc.ca/books'),
        ],
        'novels': [
            ('William Shakespeare — Romeo and Juliet (Folger Shakespeare, free annotated e-text)',
             'https://www.folger.edu/explore/shakespeares-works/romeo-and-juliet/'),
            ('Harper Lee — To Kill a Mockingbird (Penguin Random House Canada)',
             'https://www.penguinrandomhouse.ca/books/172170/to-kill-a-mockingbird-by-harper-lee/9780446310789'),
            ('William Golding — Lord of the Flies (Penguin Random House Canada)',
             'https://www.penguinrandomhouse.ca/books/2870/lord-of-the-flies-by-william-golding/9780399501487'),
        ],
        'primary_sources': [],
    },
    'eng3u': {
        'ministry': ['english'],
        'primary':  ('Nelson Education — Reference Points 11 anthology', 'https://www.nelson.com/secondary/english/'),
        'alt':      ('Pearson Canada — ResourceLines 11', 'https://www.pearsoncanada.ca/'),
        'free_online': [
            ('Purdue OWL — citation &amp; rhetorical-modes guide',
             'https://owl.purdue.edu/'),
            ('Project Gutenberg — free public-domain literature',
             'https://www.gutenberg.org/'),
            ('CBC Books — Canadian author features',
             'https://www.cbc.ca/books'),
        ],
        'novels': [
            ('William Shakespeare — Macbeth (Folger Shakespeare, free annotated e-text)',
             'https://www.folger.edu/explore/shakespeares-works/macbeth/'),
            ('F. Scott Fitzgerald — The Great Gatsby (Project Gutenberg Australia, free)',
             'https://gutenberg.net.au/ebooks02/0200041.txt'),
            ('Yann Martel — Life of Pi (Penguin Random House Canada)',
             'https://www.penguinrandomhouse.ca/books/295/life-of-pi-by-yann-martel/9780676974447'),
            ('Richard Wagamese — Indian Horse (Douglas &amp; McIntyre) — Indigenous-voice required reading',
             'https://www.douglas-mcintyre.com/book/indian-horse'),
        ],
        'primary_sources': [],
    },
    'eng4u': {
        'ministry': ['english'],
        'primary':  ('Nelson Education — Echoes 12 anthology', 'https://www.nelson.com/secondary/english/'),
        'alt':      ('Pearson Canada — Inquiry into Life and Language', 'https://www.pearsoncanada.ca/'),
        'free_online': [
            ('Purdue OWL — research, writing &amp; MLA / APA citation',
             'https://owl.purdue.edu/'),
            ('Project Gutenberg — free public-domain literary canon',
             'https://www.gutenberg.org/'),
            ('Poetry Foundation — full poems &amp; author pages',
             'https://www.poetryfoundation.org/'),
            ('CBC Books — Canadian literature, Massey Lectures',
             'https://www.cbc.ca/books'),
        ],
        'novels': [
            ('William Shakespeare — Hamlet (Folger Shakespeare, free annotated e-text)',
             'https://www.folger.edu/explore/shakespeares-works/hamlet/'),
            ('Margaret Atwood — The Handmaid\'s Tale (Penguin Random House Canada)',
             'https://www.penguinrandomhouse.ca/books/55542/the-handmaids-tale-by-margaret-atwood/9780385490818'),
            ('Chinua Achebe — Things Fall Apart (Penguin Random House)',
             'https://www.penguinrandomhouse.com/books/304330/things-fall-apart-by-chinua-achebe/'),
            ('Toni Morrison — Beloved (Penguin Random House)',
             'https://www.penguinrandomhouse.com/books/117603/beloved-by-toni-morrison/'),
            ('Canadian poetry — Atwood, Birney, Page, Purdy, Ondaatje, Brand (Poetry Foundation)',
             'https://www.poetryfoundation.org/'),
        ],
        'primary_sources': [],
    },

    # ──────────── Computer Studies ────────────
    'ics3u': {
        'ministry': ['compsci'],
        'primary':  ('Hello World! Computer Programming for Kids and Other Beginners (Sande, 3rd ed.)',
                     'https://helloworldbook.com/'),
        'alt':      ('Allen Downey — Think Python (2nd ed., FREE full PDF)',
                     'https://greenteapress.com/wp/think-python-2e/'),
        'free_online': [
            ('Official Python 3 Documentation',
             'https://docs.python.org/3/'),
            ('CS Circles (University of Waterloo CEMC) — interactive Python',
             'https://cscircles.cemc.uwaterloo.ca/'),
            ('Python Tutor — step-by-step program visualiser',
             'https://pythontutor.com/'),
            ('Replit — free browser Python IDE',
             'https://replit.com/'),
        ],
        'novels': [], 'primary_sources': [],
    },
    'ics4u': {
        'ministry': ['compsci'],
        'primary':  ('Mark Lutz — Learning Python (O\'Reilly, 5th ed.)',
                     'https://www.oreilly.com/library/view/learning-python-5th/9781449355722/'),
        'alt':      ('Brad Miller &amp; David Ranum — Problem Solving with Algorithms and Data Structures Using Python (FREE)',
                     'https://runestone.academy/runestone/books/published/pythonds/index.html'),
        'free_online': [
            ('Official Python 3 Documentation',
             'https://docs.python.org/3/'),
            ('MIT OCW — 6.0001 Introduction to Computer Science in Python',
             'https://ocw.mit.edu/courses/6-0001-introduction-to-computer-science-and-programming-in-python-fall-2016/'),
            ('Python Tutor — algorithm visualiser',
             'https://pythontutor.com/'),
        ],
        'novels': [], 'primary_sources': [],
    },

    # ──────────── Canadian and World Studies ────────────
    'chv2o': {
        'ministry': ['cws'],
        'primary':  ('Nelson Education — Civics Today', 'https://www.nelson.com/secondary/canadian-world-studies/'),
        'alt':      ('Pearson Canada — Canadian Civics', 'https://www.pearsoncanada.ca/'),
        'free_online': [
            ('The Canadian Encyclopedia — Civics &amp; Government articles',
             'https://www.thecanadianencyclopedia.ca/en/browse/government-and-politics'),
            ('Mapleleafweb — civic-education resources',
             'https://www.mapleleafweb.com/'),
        ],
        'novels': [],
        'primary_sources': [
            ('Canadian Charter of Rights and Freedoms (Department of Justice, official text)',
             'https://laws-lois.justice.gc.ca/eng/const/page-12.html'),
            ('Parliament of Canada — House of Commons + Hansard',
             'https://www.ourcommons.ca/'),
            ('Elections Canada — voter information &amp; results archive',
             'https://www.elections.ca/'),
            ('Truth and Reconciliation Commission — 94 Calls to Action',
             'https://www.rcaanc-cirnac.gc.ca/eng/1450124405592/1529106060525'),
            ('CBC News — Politics',
             'https://www.cbc.ca/news/politics'),
        ],
    },
    'cpc3o': {
        'ministry': ['cws'],
        'primary':  ('Pearson Canada — Politics in Action: Making Change (custom anthology)',
                     'https://www.pearsoncanada.ca/'),
        'alt':      ('Nelson Education — Civics Today + current-events resources',
                     'https://www.nelson.com/secondary/canadian-world-studies/'),
        'free_online': [
            ('The Canadian Encyclopedia — Politics &amp; Government',
             'https://www.thecanadianencyclopedia.ca/en/browse/government-and-politics'),
            ('Samara Canada — youth civic-engagement research',
             'https://www.samaracanada.com/'),
        ],
        'novels': [],
        'primary_sources': [
            ('Canadian Charter of Rights and Freedoms',
             'https://laws-lois.justice.gc.ca/eng/const/page-12.html'),
            ('Parliament of Canada — Hansard',
             'https://www.ourcommons.ca/DocumentViewer/en/house/hansard-index'),
            ('Government of Canada — Open Government datasets',
             'https://open.canada.ca/en/open-data'),
            ('CBC News — Politics',
             'https://www.cbc.ca/news/politics'),
            ('The Globe and Mail — Politics',
             'https://www.theglobeandmail.com/canada/politics/'),
            ('Toronto Star — Politics',
             'https://www.thestar.com/politics.html'),
        ],
    },
    'cpw4u': {
        'ministry': ['cws'],
        'primary':  ('Pearson Canada — Canadian and World Politics (Coppen)',
                     'https://www.pearsoncanada.ca/'),
        'alt':      ('Nelson Education — Politics and You', 'https://www.nelson.com/secondary/canadian-world-studies/'),
        'free_online': [
            ('Council on Foreign Relations — global-politics primers',
             'https://www.cfr.org/'),
            ('Foreign Affairs — international relations magazine',
             'https://www.foreignaffairs.com/'),
            ('The Canadian Encyclopedia — Politics &amp; International Relations',
             'https://www.thecanadianencyclopedia.ca/en/browse/government-and-politics'),
        ],
        'novels': [],
        'primary_sources': [
            ('United Nations — official site &amp; UN Documentation',
             'https://www.un.org/en/'),
            ('Universal Declaration of Human Rights (UN, 1948)',
             'https://www.un.org/en/about-us/universal-declaration-of-human-rights'),
            ('International Court of Justice',
             'https://www.icj-cij.org/'),
            ('Global Affairs Canada — foreign-policy statements',
             'https://www.international.gc.ca/'),
            ('NATO — official documents &amp; communiqués',
             'https://www.nato.int/'),
            ('Hansard — Parliament of Canada',
             'https://www.ourcommons.ca/DocumentViewer/en/house/hansard-index'),
        ],
    },
    'chc2d': {
        'ministry': ['cws'],
        'primary':  ('McGraw-Hill Ryerson — Canada: Face of a Nation',
                     'https://www.mheducation.ca/'),
        'alt':      ('Nelson Education — Canadian History since World War I',
                     'https://www.nelson.com/secondary/canadian-world-studies/'),
        'free_online': [
            ('The Canadian Encyclopedia — Canadian History',
             'https://www.thecanadianencyclopedia.ca/en/browse/history'),
            ('Historica Canada — Heritage Minutes &amp; learning tools',
             'https://www.historicacanada.ca/'),
        ],
        'novels': [],
        'primary_sources': [
            ('Library and Archives Canada — primary-source archive',
             'https://library-archives.canada.ca/eng/'),
            ('Veterans Affairs Canada — historical records',
             'https://www.veterans.gc.ca/eng/remembrance/history'),
            ('Truth and Reconciliation Commission — final report &amp; Calls to Action',
             'https://www.rcaanc-cirnac.gc.ca/eng/1450124405592/1529106060525'),
            ('Maclean\'s — archival Canadian news',
             'https://www.macleans.ca/'),
        ],
    },
    'chw3m': {
        'ministry': ['cws'],
        'primary':  ('Pearson Canada — Worlds of History: A Comparative Reader (Reilly)',
                     'https://www.pearsoncanada.ca/'),
        'alt':      ('Nelson Education — Crossroads: A Meeting of Nations',
                     'https://www.nelson.com/secondary/canadian-world-studies/'),
        'free_online': [
            ('World History Encyclopedia (free, peer-reviewed)',
             'https://www.worldhistory.org/'),
            ('BBC History — ancient and medieval',
             'https://www.bbc.co.uk/history'),
        ],
        'novels': [],
        'primary_sources': [
            ('Project Gutenberg — historical primary documents in translation',
             'https://www.gutenberg.org/'),
            ('Internet History Sourcebooks Project (Fordham)',
             'https://sourcebooks.fordham.edu/'),
            ('Smithsonian — World History',
             'https://www.si.edu/'),
        ],
    },
    'chy4u': {
        'ministry': ['cws'],
        'primary':  ('Pearson Canada — Legacy: The West and the World (Cranny)',
                     'https://www.pearsoncanada.ca/'),
        'alt':      ('Nelson Education — Pathways: Civilizations Through Time',
                     'https://www.nelson.com/secondary/canadian-world-studies/'),
        'free_online': [
            ('World History Encyclopedia',
             'https://www.worldhistory.org/'),
            ('BBC History — modern era',
             'https://www.bbc.co.uk/history'),
        ],
        'novels': [],
        'primary_sources': [
            ('Library of Congress — digital primary-source collections',
             'https://www.loc.gov/collections/'),
            ('UK National Archives',
             'https://www.nationalarchives.gov.uk/'),
            ('U.S. National Archives — DocsTeach (Modern History)',
             'https://www.docsteach.org/'),
            ('Internet History Sourcebooks Project (Fordham)',
             'https://sourcebooks.fordham.edu/'),
        ],
    },
    'clu3m': {
        'ministry': ['cws'],
        'primary':  ('Emond Publishing — Understanding Canadian Law',
                     'https://emond.ca/'),
        'alt':      ('Pearson Canada — All About Law (Liepner, Boyko)',
                     'https://www.pearsoncanada.ca/'),
        'free_online': [
            ('CanLII — free Canadian case law, statutes &amp; regulations',
             'https://www.canlii.org/en/'),
            ('Department of Justice — Legal Resources',
             'https://www.justice.gc.ca/eng/'),
            ('Community Legal Education Ontario (CLEO)',
             'https://www.cleo.on.ca/'),
        ],
        'novels': [],
        'primary_sources': [
            ('Canadian Charter of Rights and Freedoms (full text)',
             'https://laws-lois.justice.gc.ca/eng/const/page-12.html'),
            ('Supreme Court of Canada — Judgments',
             'https://www.scc-csc.ca/case-dossier/info/sum-som-eng.aspx'),
            ('Criminal Code of Canada',
             'https://laws-lois.justice.gc.ca/eng/acts/c-46/'),
        ],
    },
    'cln4u': {
        'ministry': ['cws'],
        'primary':  ('Emond Publishing — Canadian and International Law', 'https://emond.ca/'),
        'alt':      ('Pearson Canada — Dimensions of Law', 'https://www.pearsoncanada.ca/'),
        'free_online': [
            ('CanLII — Canadian legal database',
             'https://www.canlii.org/en/'),
            ('UN Treaty Collection — international law',
             'https://treaties.un.org/'),
        ],
        'novels': [],
        'primary_sources': [
            ('Supreme Court of Canada — Judgments',
             'https://www.scc-csc.ca/case-dossier/info/sum-som-eng.aspx'),
            ('International Court of Justice — Cases',
             'https://www.icj-cij.org/decisions'),
            ('International Criminal Court — Documents',
             'https://www.icc-cpi.int/'),
            ('Constitution Act, 1867 + Constitution Act, 1982',
             'https://laws-lois.justice.gc.ca/eng/const/'),
        ],
    },
    'cgf3m': {
        'ministry': ['cws'],
        'primary':  ('Pearson Canada — Physical Geography of Canada and the World',
                     'https://www.pearsoncanada.ca/'),
        'alt':      ('Nelson Education — Physical Geography',
                     'https://www.nelson.com/secondary/canadian-world-studies/'),
        'free_online': [
            ('Natural Resources Canada — atlas, maps, satellite data',
             'https://www.nrcan.gc.ca/'),
            ('NASA Earth Observatory',
             'https://earthobservatory.nasa.gov/'),
            ('Environment and Climate Change Canada — climate data',
             'https://climate.weather.gc.ca/'),
            ('Google Earth (web)',
             'https://earth.google.com/'),
        ],
        'novels': [],
        'primary_sources': [
            ('Statistics Canada — geography &amp; environment',
             'https://www.statcan.gc.ca/en/subjects-start/environment'),
            ('Atlas of Canada',
             'https://atlas.gc.ca/'),
        ],
    },
    'cgw4u': {
        'ministry': ['cws'],
        'primary':  ('Pearson Canada — World Issues (Earle, Clarke et al.)',
                     'https://www.pearsoncanada.ca/'),
        'alt':      ('Nelson Education — Global Connections',
                     'https://www.nelson.com/secondary/canadian-world-studies/'),
        'free_online': [
            ('World Bank Open Data',
             'https://data.worldbank.org/'),
            ('UN Sustainable Development Goals',
             'https://sdgs.un.org/goals'),
            ('Our World in Data — global development indicators',
             'https://ourworldindata.org/'),
        ],
        'novels': [],
        'primary_sources': [
            ('Statistics Canada — international and trade data',
             'https://www.statcan.gc.ca/en/subjects-start/international_trade'),
            ('UNEP — environmental data',
             'https://www.unep.org/'),
            ('IPCC — climate-change reports',
             'https://www.ipcc.ch/'),
        ],
    },

    # ──────────── Business Studies ────────────
    'baf3m': {
        'ministry': ['business'],
        'primary':  ('McGraw-Hill Ryerson — Accounting 1 (Syme, Mitchell)',
                     'https://www.mheducation.ca/'),
        'alt':      ('Pearson Canada — Accounting Fundamentals',
                     'https://www.pearsoncanada.ca/'),
        'free_online': [
            ('CPA Canada — Financial Literacy resources',
             'https://www.cpacanada.ca/en/public-interest/financial-literacy'),
            ('Investopedia — accounting concepts',
             'https://www.investopedia.com/'),
        ],
        'novels': [],
        'primary_sources': [
            ('Canada Revenue Agency — Business income tax',
             'https://www.canada.ca/en/revenue-agency/services/tax/businesses.html'),
            ('Statistics Canada — Canadian business statistics',
             'https://www.statcan.gc.ca/en/start'),
        ],
    },
    'bat4m': {
        'ministry': ['business'],
        'primary':  ('McGraw-Hill Ryerson — Accounting 2',
                     'https://www.mheducation.ca/'),
        'alt':      ('Pearson Canada — Accounting Principles',
                     'https://www.pearsoncanada.ca/'),
        'free_online': [
            ('CPA Canada — Career and educational resources',
             'https://www.cpacanada.ca/'),
            ('Investopedia — advanced accounting',
             'https://www.investopedia.com/'),
            ('Canada Business Network',
             'https://www.canada.ca/en/services/business.html'),
        ],
        'novels': [],
        'primary_sources': [
            ('Canada Revenue Agency — Corporation tax',
             'https://www.canada.ca/en/revenue-agency.html'),
        ],
    },
    'bbb4m': {
        'ministry': ['business'],
        'primary':  ('Nelson Education — International Business: Trade and Production',
                     'https://www.nelson.com/secondary/business-studies/'),
        'alt':      ('Pearson Canada — International Business',
                     'https://www.pearsoncanada.ca/'),
        'free_online': [
            ('Export Development Canada (EDC) — export guides',
             'https://www.edc.ca/'),
            ('Trade Commissioner Service of Canada',
             'https://www.tradecommissioner.gc.ca/'),
            ('WTO — international trade statistics',
             'https://www.wto.org/'),
        ],
        'novels': [],
        'primary_sources': [
            ('Statistics Canada — International trade data',
             'https://www.statcan.gc.ca/en/subjects-start/international_trade'),
            ('Bank of Canada — exchange rates',
             'https://www.bankofcanada.ca/rates/exchange/'),
            ('WTO — official agreements',
             'https://www.wto.org/english/docs_e/legal_e/legal_e.htm'),
        ],
    },
    'boh4m': {
        'ministry': ['business'],
        'primary':  ('Nelson Education — Management Fundamentals: A Canadian Approach',
                     'https://www.nelson.com/secondary/business-studies/'),
        'alt':      ('Pearson Canada — Business Leadership: Management Fundamentals',
                     'https://www.pearsoncanada.ca/'),
        'free_online': [
            ('Harvard Business Review — leadership articles',
             'https://hbr.org/topic/leadership'),
            ('MIT Sloan Management Review',
             'https://sloanreview.mit.edu/'),
            ('McKinsey Quarterly — management insights',
             'https://www.mckinsey.com/quarterly/overview'),
        ],
        'novels': [],
        'primary_sources': [
            ('Conference Board of Canada — leadership research',
             'https://www.conferenceboard.ca/'),
        ],
    },

    # ──────────── Social Sciences and Humanities ────────────
    'hfn3m': {
        'ministry': ['ssh'],
        'primary':  ('Pearson Canada — Food for Today (Kowtaluk, Kopan-Johnson)',
                     'https://www.pearsoncanada.ca/'),
        'alt':      ('Nelson Education — Nutrition and You',
                     'https://www.nelson.com/secondary/social-sciences/'),
        'free_online': [
            ('Canada\'s Food Guide (Health Canada)',
             'https://food-guide.canada.ca/en/'),
            ('Dietitians of Canada',
             'https://www.dietitians.ca/'),
            ('Government of Canada — Canadian Nutrient File',
             'https://food-nutrition.canada.ca/cnf-fce/index-eng.jsp'),
        ],
        'novels': [],
        'primary_sources': [
            ('Statistics Canada — Health &amp; Nutrition data',
             'https://www.statcan.gc.ca/en/subjects-start/health'),
        ],
    },
    'hfa4m': {
        'ministry': ['ssh'],
        'primary':  ('Nelson Education — Nutrition for Health',
                     'https://www.nelson.com/secondary/social-sciences/'),
        'alt':      ('Pearson Canada — Foods and Nutrition: A Canadian Approach',
                     'https://www.pearsoncanada.ca/'),
        'free_online': [
            ('Canada\'s Food Guide (Health Canada)',
             'https://food-guide.canada.ca/en/'),
            ('Dietitians of Canada',
             'https://www.dietitians.ca/'),
            ('Public Health Agency of Canada — Nutrition',
             'https://www.canada.ca/en/public-health/services/food-nutrition.html'),
            ('Harvard T.H. Chan School of Public Health — Nutrition Source',
             'https://www.hsph.harvard.edu/nutritionsource/'),
        ],
        'novels': [],
        'primary_sources': [
            ('World Health Organization — Nutrition',
             'https://www.who.int/health-topics/nutrition'),
            ('UN FAO — Food security data',
             'https://www.fao.org/home/en/'),
        ],
    },
    'hsc4m': {
        'ministry': ['ssh'],
        'primary':  ('Pearson Canada — World Cultures (Lehr, Karras)',
                     'https://www.pearsoncanada.ca/'),
        'alt':      ('Nelson Education — Many Faces, Many Voices',
                     'https://www.nelson.com/secondary/social-sciences/'),
        'free_online': [
            ('UNESCO — World Heritage List',
             'https://whc.unesco.org/en/list/'),
            ('Ethnologue — languages of the world',
             'https://www.ethnologue.com/'),
            ('Smithsonian — World Cultures',
             'https://www.si.edu/'),
            ('Indigenous Peoples Atlas of Canada (free online)',
             'https://indigenouspeoplesatlasofcanada.ca/'),
        ],
        'novels': [],
        'primary_sources': [
            ('UNESCO — Intangible Cultural Heritage',
             'https://ich.unesco.org/'),
            ('Statistics Canada — Ethnocultural diversity data',
             'https://www.statcan.gc.ca/en/subjects-start/ethnocultural_diversity'),
        ],
    },

    # ──────────── Guidance and Career Education ────────────
    'glc2o': {
        'ministry': ['gce'],
        'primary':  ('Ministry of Education — Creating Pathways to Success (2013)',
                     CPS[1]),
        'alt':      ('Pearson Canada — Career Studies (workbook)',
                     'https://www.pearsoncanada.ca/'),
        'free_online': [
            ('Government of Canada — Job Bank',
             'https://www.jobbank.gc.ca/'),
            ('National Occupational Classification (NOC) — career database',
             'https://noc.esdc.gc.ca/'),
            ('OUAC — Ontario Universities Application Centre',
             'https://www.ouac.on.ca/'),
            ('OntarioColleges.ca — Ontario college applications',
             'https://www.ontariocolleges.ca/'),
        ],
        'novels': [], 'primary_sources': [],
    },
    'gwl3o': {
        'ministry': ['gce'],
        'primary':  ('Pearson Canada — Pathways: Career Studies',
                     'https://www.pearsoncanada.ca/'),
        'alt':      ('Ministry of Education — Creating Pathways to Success (2013)',
                     CPS[1]),
        'free_online': [
            ('Government of Canada — Job Bank',
             'https://www.jobbank.gc.ca/'),
            ('NOC — career taxonomy',
             'https://noc.esdc.gc.ca/'),
            ('OUAC + OntarioColleges.ca — post-secondary applications',
             'https://www.ouac.on.ca/'),
            ('Government of Ontario — OSAP financial aid',
             'https://www.ontario.ca/page/osap-ontario-student-assistance-program'),
        ],
        'novels': [], 'primary_sources': [],
    },
    'gpp3o': {
        'ministry': ['gce'],
        'primary':  ('Pearson Canada — Leadership and Peer Support',
                     'https://www.pearsoncanada.ca/'),
        'alt':      ('Nelson Education — Leadership: An Open Approach',
                     'https://www.nelson.com/secondary/social-sciences/'),
        'free_online': [
            ('Harvard Business Review — leadership topic',
             'https://hbr.org/topic/leadership'),
            ('Canadian Mental Health Association — peer-support frameworks',
             'https://cmha.ca/'),
            ('Public Health Agency of Canada — Mental Health',
             'https://www.canada.ca/en/public-health/services/mental-health.html'),
        ],
        'novels': [], 'primary_sources': [],
    },
    'gle3o': {
        'ministry': ['gce'],
        'primary':  ('Pearson Canada — Learning Strategies: Skills for Success in Secondary School',
                     'https://www.pearsoncanada.ca/'),
        'alt':      ('Ministry of Education — Achieving Excellence',
                     'http://www.edu.gov.on.ca/eng/about/excellent.html'),
        'free_online': [
            ('Cornell University — Cornell Note-Taking System',
             'https://lsc.cornell.edu/how-to-study/taking-notes/cornell-note-taking-system/'),
            ('Pomodoro Technique — official site',
             'https://francescocirillo.com/pages/pomodoro-technique'),
            ('Khan Academy — Learning how to learn',
             'https://www.khanacademy.org/'),
        ],
        'novels': [], 'primary_sources': [],
    },
    'gle4o': {
        'ministry': ['gce'],
        'primary':  ('Pearson Canada — Adult Learning Strategies: Skills for Success After Secondary School',
                     'https://www.pearsoncanada.ca/'),
        'alt':      ('Ministry of Education — Creating Pathways to Success (2013)',
                     CPS[1]),
        'free_online': [
            ('Government of Canada — Job Bank',
             'https://www.jobbank.gc.ca/'),
            ('OSAP — Ontario Student Assistance Program',
             'https://www.ontario.ca/page/osap-ontario-student-assistance-program'),
            ('Bank of Canada — financial literacy basics',
             'https://www.bankofcanada.ca/financial-literacy/'),
            ('Government of Canada — taxes &amp; benefits',
             'https://www.canada.ca/en/revenue-agency/services/tax/individuals.html'),
        ],
        'novels': [], 'primary_sources': [],
    },
}


def render_links_list(pairs, label=None):
    """Render a list of (label, url) into an HTML <ul>."""
    if not pairs:
        return ''
    items = []
    for lbl, url in pairs:
        items.append(f'  <li><a href="{url}" target="_blank" rel="noopener">{lbl}</a></li>')
    return '<ul>\n' + '\n'.join(items) + '\n</ul>'


def build_resources_block(code, data):
    """Construct the full Required Learning Resources HTML block."""
    parts = ['<h2>2. Required Learning Resources</h2>',
             '<p>Five-tier reading list aligned with Ontario Ministry curriculum. <strong>Free / freely-licensed resources are linked directly</strong>; commercial textbooks link to the publisher\'s information page (the school administrator confirms the current edition before purchase).</p>']

    # Tier 1 — Ontario Ministry curriculum
    parts.append('<h3>Tier 1 — Ontario Ministry curriculum (authoritative)</h3>')
    ministry_pairs = []
    for key in data['ministry']:
        if key in DCP:
            ministry_pairs.append(DCP[key])
    ministry_pairs.append(GROWING_SUCCESS)
    if 'gce' in data['ministry'] or code in ('glc2o', 'gwl3o', 'gle3o', 'gle4o'):
        ministry_pairs.append(CPS)
    parts.append(render_links_list(ministry_pairs))

    # Tier 2 — Primary text (Trillium-aligned)
    parts.append('<h3>Tier 2 — Primary text (Trillium-aligned)</h3>')
    primary_label, primary_url = data['primary']
    alt_label, alt_url = data['alt']
    parts.append('<table>')
    parts.append('  <tr><th style="width:24%;">Type</th><th>Resource</th></tr>')
    parts.append(f'  <tr><td><strong>Primary text</strong></td><td><a href="{primary_url}" target="_blank" rel="noopener">{primary_label}</a></td></tr>')
    parts.append(f'  <tr><td><strong>Alternative / supplementary</strong></td><td><a href="{alt_url}" target="_blank" rel="noopener">{alt_label}</a></td></tr>')
    parts.append('</table>')

    # Tier 3 — Free supplementary online textbooks
    if data['free_online']:
        parts.append('<h3>Tier 3 — Free supplementary online resources</h3>')
        parts.append(render_links_list(data['free_online']))

    # Tier 4 — Required novels & anchor texts (English)
    if data['novels']:
        parts.append('<h3>Tier 4 — Required novels &amp; anchor texts</h3>')
        parts.append(render_links_list(data['novels']))

    # Tier 5 — Primary sources / articles
    if data['primary_sources']:
        parts.append('<h3>Tier 5 — Primary sources, articles &amp; archives</h3>')
        parts.append(render_links_list(data['primary_sources']))

    parts.append('<div class="callout"><strong>Inspection note.</strong> Per Ontario\'s policy for private inspected schools (PIS Memorandum 2022B): the Tier 2 primary text is the resource an Inspector should expect to see on a student\'s desk or device. Tier 1 (Ministry curriculum) and Tier 3-5 are free, online, and accessible to all students at no cost. Commercial textbook editions change frequently — confirm the current ISBN with the publisher before purchase.</div>')
    return '\n'.join(parts)


# ─────────── Replace existing block (idempotent) ───────────

def patch_curriculum_page(code):
    path = ROOT / 'courses' / f'{code}_curriculum.html'
    if not path.exists():
        return f"  ✗ {code}: curriculum sub-page missing"
    if code not in COURSES_DATA:
        return f"  ⚠ {code}: no COURSES_DATA — skipped"

    text = path.read_text()

    # If a previous "Required Learning Resources" block exists, remove it.
    # The R1 v1 block started with <h2>2. Required Learning Resources</h2>
    # and ran until the next <h2>...</h2> heading.
    start_re = re.compile(r'<h2>\s*(?:\d+\.\s*)?Required Learning Resources\s*</h2>')
    m_start = start_re.search(text)
    if m_start:
        # find the next <h2> tag after our start
        m_end = re.search(r'<h2[^>]*>', text[m_start.end():])
        if m_end:
            block_end = m_start.end() + m_end.start()
            text = text[:m_start.start()] + text[block_end:]
        else:
            text = text[:m_start.start()]

    # Now insert the new block. Use the same flexible-headings strategy
    # as R1 v1 — find the SECOND <h2> (first is "Course Description" or
    # equivalent) and insert before it.
    headings = list(re.finditer(r'<h2[^>]*>', text))
    if len(headings) < 2:
        # Fall back to inserting at the end of the document, just before </body>.
        block = '\n\n' + build_resources_block(code, COURSES_DATA[code]) + '\n\n'
        if '</body>' in text:
            text = text.replace('</body>', block + '</body>', 1)
        else:
            text = text + block
    else:
        second_h2_start = headings[1].start()
        block = '\n\n' + build_resources_block(code, COURSES_DATA[code]) + '\n\n'
        text = text[:second_h2_start] + block + text[second_h2_start:]

    # Renumber any subsequent <h2>N. ... headings so that we maintain
    # sequence after the inserted block. We bump every <h2>N. that appears
    # AFTER our inserted block's location.
    insertion_marker = '<h2>2. Required Learning Resources</h2>'
    if insertion_marker in text:
        head_idx = text.index(insertion_marker) + len(insertion_marker)
        before = text[:head_idx]
        after = text[head_idx:]
        # Capture existing numbered headings and bump them if conflicting
        used_numbers = set(int(n) for n in re.findall(r'<h2>(\d+)\.\s', after))
        if 2 in used_numbers:
            def shift(match):
                n = int(match.group(1))
                return f'<h2>{n + 1}. '
            after = re.sub(r'<h2>(\d+)\.\s', shift, after)
        text = before + after

    path.write_text(text)
    return f"  ✓ {code}: replaced Required Learning Resources with 5-tier linked block"


def main():
    print("R1b — replacing Required Learning Resources with comprehensive 5-tier linked block")
    print()
    for code in sorted(COURSES_DATA):
        print(patch_curriculum_page(code))


if __name__ == '__main__':
    main()
