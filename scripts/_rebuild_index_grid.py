#!/usr/bin/env python3
"""Rebuild the home-page index.html course grid with a symmetric
Grade-10 → 11 → 12 layout, grouping each subject so that paired
courses (e.g. SCH3U next to SCH4U) sit on the same logical row.

Reads templates from the existing course cards in index.html so it
preserves styling exactly; only the ORDER and GROUPING change.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "index.html"


# Subject-group layout. The user's request: Grade 10 first, then 11, then 12;
# paired siblings (Chemistry 11 next to Chemistry 12 etc.) on the same row.
# Layout: each section heading matches an Ontario Ministry curriculum
# discipline OR strand (sub-discipline) name. Within each section, courses
# are listed in grade order (10 → 11 → 12) and paired siblings sit
# adjacent (e.g. SCH3U → SCH4U).
#
# Section ordering (owner instruction 2026-06-01): all STEM/Sciences
# sections come first, A→Z alphabetical; then all Arts & Humanities
# sections, A→Z alphabetical. Within each section, courses keep their
# Grade-10 → Grade-11 → Grade-12 order (already pair-aware).
#
#   STEM band (alphabetical):
#     Biology · Chemistry · Computer Studies · Mathematics · Physics · Science
#   Arts & Humanities band (alphabetical):
#     Accounting · Business Leadership · Civics and Politics · English
#     · Food and Nutrition · Geography · Guidance and Career Education
#     · History · International Business · Law · World Cultures
#
# Ontario discipline → strand mapping reference (audit, 2026-06-01):
#
#   Mathematics                            → Mathematics (single section)
#   Science                                → split by strand:
#                                              · Science (integrated G10)
#                                              · Biology
#                                              · Chemistry
#                                              · Physics
#   English                                → English (single section)
#   Computer Studies                       → Computer Studies (single section)
#   Canadian and World Studies             → split by strand:
#                                              · Civics and Citizenship
#                                                (formally "Politics" strand)
#                                              · History
#                                              · Law
#                                              · Geography
#   Business Studies                       → split by strand:
#                                              · Accounting
#                                              · International Business
#                                              · Business Leadership
#                                                (formally "Management" strand)
#   Social Sciences and Humanities         → split by strand:
#                                              · Food and Nutrition
#                                                (Family Studies discipline)
#                                              · World Cultures
#                                                (Equity Studies discipline)
#   Guidance and Career Education          → single section
#
# Source: https://www.dcp.edu.gov.on.ca/en/curriculum/
# Single-course strands are kept as their own section per owner instruction
# (consistent with the Geography-as-own-section pattern from 2026-06-01).
#
# Each tuple is (code, label, grade, accent, title, description).
# The list of tuples within each group is presented in display order.
LAYOUT = [
    # ═══════════════════════════════════════════════════════════════════
    # STEM band (A → Z): Biology · Chemistry · Computer Studies ·
    #                    Mathematics · Physics · Science
    # ═══════════════════════════════════════════════════════════════════

    ("🧬 Biology", [
        # Ontario Science 2008 (rev.) — Biology strand.
        ("sbi3u", "SBI3U", 11, "#15803d", "Biology", "Diversity, evolution, genetics, animal systems, plant biology — prerequisite for SBI4U"),
        ("sbi4u", "SBI4U", 12, "#16a34a", "Biology", "Biochemistry, metabolic processes, molecular genetics, homeostasis, population dynamics"),
    ]),

    ("🧪 Chemistry", [
        # Ontario Science 2008 (rev.) — Chemistry strand.
        ("sch3u", "SCH3U", 11, "#0d9488", "Chemistry", "Matter & bonding, reactions, stoichiometry, solutions, gases — prerequisite for SCH4U"),
        ("sch4u", "SCH4U", 12, "#059669", "Chemistry", "Organic chemistry, structure & properties, energy & rates, equilibrium, electrochemistry"),
    ]),

    ("💻 Computer Studies", [
        # Ontario Computer Studies 2008 (rev.) — single discipline.
        ("ics3u", "ICS3U", 11, "#14b8a6", "Introduction to Computer Science", "Programming with Python — variables, control flow, functions, lists, software dev — prerequisite for ICS4U"),
        ("ics4u", "ICS4U", 12, "#6366f1", "Computer Science", "Programming, data structures, recursion, algorithms, software engineering, AI/ethics"),
    ]),

    ("📐 Mathematics", [
        # Ontario Mathematics 2007 (rev.) — courses-are-strands.
        # — Functions sequence (MCR3U → MHF4U)
        ("mcr3u", "MCR3U", 11, "#0891b2", "Functions", "Function notation, quadratics, exponentials, sequences, financial math, trig & sinusoids"),
        ("mhf4u", "MHF4U", 12, "#2563eb", "Advanced Functions", "Polynomial, rational, logarithmic, and trigonometric functions; rates of change"),
        # — Calculus and Vectors
        ("mcv4u", "MCV4U", 12, "#7c3aed", "Calculus and Vectors", "Derivatives, curve sketching, optimization, vectors in 2D/3D, lines and planes"),
        # — Data Management
        ("mdm4u", "MDM4U", 12, "#16a34a", "Mathematics of Data Management", "Counting, probability, distributions, statistics, correlation & regression"),
        # — College-Technology Mathematics (Grade 11 → Grade 12)
        ("mct3m", "MCT3M", 11, "#ea580c", "Math for College Tech", "Exponentials, polynomials, trig, measurement, geometric modelling — college pathway"),
        ("mct4m", "MCT4M", 12, "#c2410c", "Math for College Tech", "Exp/log functions, polynomial equations, trig functions, geometry applications"),
    ]),

    ("⚡ Physics", [
        # Ontario Science 2008 (rev.) — Physics strand.
        ("sph3u", "SPH3U", 11, "#ea580c", "Physics", "Kinematics, forces, energy & society, waves & sound, electricity & magnetism — prerequisite for SPH4U"),
        ("sph4u", "SPH4U", 12, "#dc2626", "Physics", "Dynamics, energy & momentum, fields, wave nature of light, modern physics"),
    ]),

    ("🔬 Science", [
        # Grade 10 Academic integrated science (Biology + Chemistry + Earth/
        # Space + Physics strands per Ontario Science 2008, rev.). Functions
        # as the prerequisite gate for SBI3U / SCH3U / SPH3U.
        ("snc2d", "SNC2D", 10, "#0891b2", "Science (Academic)", "Biology — tissues & systems, Chemistry — reactions, Earth/Space — climate change, Physics — light & optics"),
    ]),

    # ═══════════════════════════════════════════════════════════════════
    # Arts & Humanities band (A → Z):
    #   Accounting · Business Leadership · Civics and Politics · English
    #   · Food and Nutrition · Geography · Guidance and Career Education
    #   · History · International Business · Law · World Cultures
    # ═══════════════════════════════════════════════════════════════════

    ("📒 Accounting", [
        # Ontario Business Studies 2006 (rev.) — Accounting strand.
        ("baf3m", "BAF3M", 11, "#15803d", "Financial Accounting Fundamentals", "Accounting equation, journal & ledger, trial balance, financial statements, internal control & ethics"),
        ("bat4m", "BAT4M", 12, "#166534", "Financial Accounting Principles", "Specific accounts, subsidiary ledgers, statement analysis, internal control, computerized accounting"),
    ]),

    ("👔 Business Leadership", [
        # Ontario Business Studies 2006 (rev.) — Management strand.
        ("boh4m", "BOH4M", 12, "#7c3aed", "Business Leadership: Management", "Foundations of management, leadership theory, decision-making, planning, controlling & ethics"),
    ]),

    ("🏛️ Civics and Politics", [
        # Ontario CWS 2018 — Politics strand. Grade 10 Civics + Grade 11
        # Politics in Action + Grade 12 Canadian and World Politics now form
        # the full G10 → G11 → G12 progression.
        ("chv2o", "CHV2O", 10, "#7c3aed", "Civics and Citizenship", "Half-credit (0.5). Civic awareness, civic engagement & action, political inquiry skills"),
        ("cpc3o", "CPC3O", 11, "#7c3aed", "Politics in Action: Making Change", "Half-credit (0.5). Identifying issues, tools of civic engagement, designing & evaluating civic action"),
        ("cpw4u", "CPW4U", 12, "#6d28d9", "Canadian and World Politics", "Power & governance, ideologies, human rights, conflict, global cooperation — university preparation"),
    ]),

    ("📚 English", [
        # Ontario English 2007 (rev.) — single discipline.
        ("eng2d", "ENG2D", 10, "#1e40af", "English (Academic)", "Critical reading, the essay, drama (Romeo and Juliet), short stories & poetry, media literacy"),
        ("eng3u", "ENG3U", 11, "#3b82f6", "English", "Critical reading, the essay, Macbeth, short stories & poetry, ISU, media literacy — prerequisite for ENG4U"),
        ("eng4u", "ENG4U", 12, "#1e40af", "English", "Critical reading, essay writing, Shakespearean tragedy, Canadian voices, ISU, media literacy"),
    ]),

    ("🥗 Food and Nutrition", [
        # Ontario SSH 2013 (rev.) — Family Studies discipline,
        # Food and Nutrition strand.
        ("hfn3m", "HFN3M", 11, "#16a34a", "Nutrition and Health", "Nutrition basics, digestion & metabolism, Canadian Food Guide, food safety, trends & issues"),
        ("hfa4m", "HFA4M", 12, "#15803d", "Nutrition and Health Issues", "Determinants of nutritional health, lifespan nutrition, nutrition & disease, food systems"),
    ]),

    ("🌍 Geography", [
        # Ontario CWS 2018 — Geography strand.
        ("cgf3m", "CGF3M", 11, "#0e7490", "Physical Geography", "Earth systems, biomes & ecosystems, human-physical interactions, sustainability, geographic issues"),
        ("cgw4u", "CGW4U", 12, "#155e75", "World Issues: A Geographic Analysis", "Quality of life, sustainability & climate, conflict & cooperation, global connections"),
    ]),

    ("🧭 Guidance and Career Education", [
        # Ontario Guidance and Career Education 2006 (rev.). Full G10 → G11
        # → G11 → G11 → G12 sequence (the GCE discipline has multiple
        # Grade 11 courses serving complementary purposes).
        ("glc2o", "GLC2O", 10, "#059669", "Career Studies", "Half-credit (0.5). Knowing yourself, exploring opportunities, decisions & goals, transitions"),
        ("gwl3o", "GWL3O", 11, "#16a34a", "Designing Your Future", "Half-credit (0.5). Self-knowledge, workplace communication, designing your post-secondary pathway"),
        ("gpp3o", "GPP3O", 11, "#15803d", "Leadership and Peer Support", "Self-awareness, interpersonal skills, theories of leadership, peer support & mentoring, leadership in action"),
        ("gle3o", "GLE3O", 11, "#059669", "Advanced Learning Strategies", "Learning styles, reading/writing/numeracy strategies, memory & test-taking, communication, goal-setting"),
        ("gle4o", "GLE4O", 12, "#047857", "Advanced Learning Strategies: After Secondary", "Adult identity, post-secondary success, workplace leadership, financial literacy, civic engagement"),
    ]),

    ("📜 History", [
        # Ontario CWS 2018 — History strand.
        ("chc2d", "CHC2D", 10, "#dc2626", "Canadian History since WWI", "Canada 1914-1929, 1929-1945, 1945-1982, 1982-Present, historical inquiry skills"),
        ("chw3m", "CHW3M", 11, "#a16207", "World History to 16th Century", "Early civilizations, Classical Greco-Roman, Medieval Europe, non-European civilizations, interactions"),
        ("chy4u", "CHY4U", 12, "#a16207", "World History since 15th Century", "Renaissance/Reformation, Enlightenment, Revolutions, World Wars, Contemporary era"),
    ]),

    ("🌐 International Business", [
        # Ontario Business Studies 2006 (rev.) — International Business strand.
        ("bbb4m", "BBB4M", 12, "#0891b2", "International Business Fundamentals", "Global business environment, international marketing, sales & logistics, trade documentation"),
    ]),

    ("⚖️ Law", [
        # Ontario CWS 2018 — Law strand.
        ("clu3m", "CLU3M", 11, "#b91c1c", "Understanding Canadian Law", "Heritage of law, Charter rights, criminal law, civil law & dispute resolution, legal inquiry"),
        ("cln4u", "CLN4U", 12, "#7f1d1d", "Canadian and International Law", "Legal theory, Constitution, international law, human rights, disputes between nations"),
    ]),

    ("🎭 World Cultures", [
        # Ontario SSH 2013 (rev.) — Equity Studies discipline, World Cultures
        # course. Section uses the course name (not the broader "Equity
        # Studies" parent) since HSC4M is the only Equity Studies course in
        # the catalogue and "World Cultures" is more descriptive for users.
        ("hsc4m", "HSC4M", 12, "#9333ea", "World Cultures", "Foundations of culture, cultural expressions, identity & diversity, globalization, inquiry skills"),
    ]),
]


def grade_pill(grade, accent_hex):
    """A small grade pill for the course card."""
    # Light background derived heuristically
    bg = {
        "#0891b2": "#ecfeff", "#2563eb": "#dbeafe", "#0d9488": "#ccfbf1",
        "#059669": "#d1fae5", "#15803d": "#dcfce7", "#16a34a": "#dcfce7",
        "#ea580c": "#fff7ed", "#dc2626": "#fee2e2", "#1e40af": "#dbeafe",
        "#3b82f6": "#dbeafe", "#14b8a6": "#ccfbf1", "#6366f1": "#e0e7ff",
        "#7c3aed": "#ede9fe", "#a16207": "#fef3c7", "#b91c1c": "#fee2e2",
        "#7f1d1d": "#fee2e2", "#0e7490": "#ecfeff", "#155e75": "#cffafe",
        "#9333ea": "#f3e8ff", "#166534": "#dcfce7", "#c2410c": "#fff7ed",
    }.get(accent_hex, "#f1f5f9")
    fg = {
        "#0891b2": "#0e7490", "#2563eb": "#1e40af", "#0d9488": "#115e59",
        "#059669": "#065f46", "#15803d": "#14532d", "#16a34a": "#166534",
        "#ea580c": "#9a3412", "#dc2626": "#991b1b", "#1e40af": "#1e3a8a",
        "#3b82f6": "#1d4ed8", "#14b8a6": "#0f766e", "#6366f1": "#4338ca",
        "#7c3aed": "#5b21b6", "#a16207": "#78350f", "#b91c1c": "#7f1d1d",
        "#7f1d1d": "#7f1d1d", "#0e7490": "#0e7490", "#155e75": "#155e75",
        "#9333ea": "#6b21a8", "#166534": "#14532d", "#c2410c": "#7c2d12",
    }.get(accent_hex, "#475569")
    return (f'<span style="font-size:11px;background:{bg};color:{fg};'
            f'padding:2px 8px;border-radius:10px;margin-left:6px;letter-spacing:0.5px;">'
            f'GRADE {grade}</span>')


def card(code, label, grade, accent, title, desc):
    # Per-course icon. Picked so each Ontario discipline / strand has a
    # consistent emoji family within its section.
    icon_for_subject = (
        # Mathematics
        "📐" if code.startswith("m") else
        # Science → split by strand
        "🔬" if code == "snc2d" else                    # integrated G10
        "🧬" if code.startswith("sbi") else             # Biology
        "🧪" if code.startswith("sch") else             # Chemistry
        "⚡" if code.startswith("sph") else             # Physics
        # English
        "📚" if code.startswith("eng") else
        # Computer Studies
        "💻" if code.startswith("ics") else
        # Canadian and World Studies — by strand
        "🏛️" if code == "chv2o" else                  # Politics → Civics G10
        "🗳️" if code == "cpc3o" else                  # Politics in Action G11
        "🌐" if code == "cpw4u" else                    # Canadian and World Politics G12
        "🍁" if code == "chc2d" else                    # History (Canadian)
        "🏺" if code == "chw3m" else                    # History (Ancient)
        "🌍" if code == "chy4u" else                    # History (Modern)
        "⚖️" if code in ("clu3m", "cln4u") else        # Law
        "🌐" if code == "cgf3m" else                    # Geography (Physical)
        "🗺️" if code == "cgw4u" else                  # Geography (World Issues)
        # Social Sciences and Humanities — by strand
        "🥗" if code == "hfn3m" else                    # Food and Nutrition G11
        "🥦" if code == "hfa4m" else                    # Food and Nutrition G12
        "🎭" if code == "hsc4m" else                    # Equity Studies / World Cultures
        # Business Studies — by strand
        "📒" if code == "baf3m" else                    # Accounting G11
        "📊" if code == "bat4m" else                    # Accounting G12
        "💱" if code == "bbb4m" else                    # International Business
        "👔" if code == "boh4m" else                    # Management
        # Guidance and Career Education
        "🧭" if code == "glc2o" else                    # Career Studies G10
        "🗺️" if code == "gwl3o" else                  # Designing Your Future G11
        "🤝" if code == "gpp3o" else                    # Leadership & Peer Support G11
        "🎯" if code == "gle3o" else                    # Advanced Learning Strategies G11
        "🎓" if code == "gle4o" else                    # Advanced Learning Strategies: After Secondary G12
        "📘"
    )
    return (
        f'<a href="courses/{code}.html" class="course-card" style="border-top:4px solid {accent}">'
        f'<div class="course-icon" style="color:{accent}">{icon_for_subject}</div>'
        f'<div class="course-body">'
        f'<div class="course-code" style="color:{accent}">{label} {grade_pill(grade, accent)}</div>'
        f'<h3>{title}</h3>'
        f'<p class="course-desc">{desc}</p>'
        f'</div></a>'
    )


def build_grid():
    parts = []
    for group_label, courses in LAYOUT:
        # Preserve LAYOUT order verbatim: per owner instruction (2026-06-01),
        # complete one sub-subject across all its grade levels before moving
        # to the next sub-subject (Chemistry 11 → Chemistry 12 → Biology 11
        # → Biology 12 → Physics 11 → Physics 12, etc.). Do NOT re-sort.
        cards = "".join(card(*c) for c in courses)
        parts.append(
            f'        <div class="subject-group">\n'
            f'            <div class="subject-label">{group_label}</div>\n'
            f'            <div class="courses-grid">\n'
            f'                {cards}\n'
            f'            </div>\n'
            f'        </div>\n'
        )
    return "\n".join(parts)


def main():
    text = INDEX.read_text()
    # Find the courses section: from <section id="courses" to its closing
    m = re.search(
        r'(<section id="courses"[^>]*>\s*<div class="container">\s*<h2>Courses</h2>\s*'
        r'<p class="section-sub">[^<]*</p>\s*)([\s\S]*?)(\s*</div>\s*</section>)',
        text,
    )
    if not m:
        raise SystemExit("courses <section> not found in index.html")
    new_body = build_grid()
    new_text = text[:m.start(2)] + new_body + text[m.end(2):]
    INDEX.write_text(new_text)
    # Sanity count
    n_cards = new_text.count('class="course-card"')
    n_groups = new_text.count('class="subject-group"')
    print(f"Rebuilt index.html — {n_groups} subject groups, {n_cards} course cards")


if __name__ == "__main__":
    main()
