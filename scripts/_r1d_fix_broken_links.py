#!/usr/bin/env python3
"""R1d — Replace every broken / redirected URL found by the link-check
sweep on 2026-06-03 with a verified working replacement.

Two categories:
  (A) 404 / 521 — page genuinely gone; replaced with a working
      equivalent from the same publisher / site.
  (B) Permanent redirects where the domain or path changed; updated
      to the canonical destination URL.

403 / timeout responses were verified to be bot-blocking only (these
URLs work normally in a browser); they are NOT changed.

Idempotent: if the old URL is no longer present in the file, no action.
Owner-approved 2026-06-03.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent

# ── URL replacement map ──────────────────────────────────────────────────
# (old_url, new_url, display_label_if_changed)
# If display_label_if_changed is None, only the href is updated; the link
# text stays the same (good for publisher-page moves). If a label is given,
# the entire <a> tag text is also updated.
REPLACEMENTS = [

    # ── A: Genuine 404s — replaced with working equivalents ─────────────

    # The Canadian Encyclopedia dropped /browse/ routes; use the search/topic pages
    (
        'https://www.thecanadianencyclopedia.ca/en/browse/history',
        'https://www.thecanadianencyclopedia.ca/en/search#q=Canadian+history&t=encyclopediaresults',
        None,
    ),
    (
        'https://www.thecanadianencyclopedia.ca/en/browse/government-and-politics',
        'https://www.thecanadianencyclopedia.ca/en/search#q=government+politics&t=encyclopediaresults',
        None,
    ),

    # Hansard — Parliament of Canada restructured the URL
    (
        'https://www.ourcommons.ca/DocumentViewer/en/house/hansard-index',
        'https://www.ourcommons.ca/en/parliamentary-business/chamber-business/sittings/hansard',
        None,
    ),

    # Globe and Mail restructured /canada/politics/ → /politics/
    (
        'https://www.theglobeandmail.com/canada/politics/',
        'https://www.theglobeandmail.com/politics/',
        None,
    ),

    # Penguin Random House CA restructured book-detail URLs — use canonical search pages
    # Lord of the Flies (Golding)
    (
        'https://www.penguinrandomhouse.ca/books/2870/lord-of-the-flies-by-william-golding/9780399501487',
        'https://www.penguinrandomhouse.ca/books/2870',
        None,
    ),
    # Life of Pi (Martel)
    (
        'https://www.penguinrandomhouse.ca/books/295/life-of-pi-by-yann-martel/9780676974447',
        'https://www.penguinrandomhouse.ca/books/295',
        None,
    ),
    # The Handmaid's Tale (Atwood) — the link the user clicked
    (
        'https://www.penguinrandomhouse.ca/books/55542/the-handmaids-tale-by-margaret-atwood/9780385490818',
        'https://www.penguinrandomhouse.ca/books/55542',
        None,
    ),
    # Beloved (Morrison) — PRH.com restructured
    (
        'https://www.penguinrandomhouse.com/books/117603/beloved-by-toni-morrison/',
        'https://www.penguinrandomhouse.com/books/117603',
        None,
    ),

    # Pomodoro Technique — site moved
    (
        'https://francescocirillo.com/pages/pomodoro-technique',
        'https://www.pomodorotechnique.com/',
        None,
    ),

    # Bank of Canada financial literacy page was removed; point to their education hub
    (
        'https://www.bankofcanada.ca/financial-literacy/',
        'https://www.bankofcanada.ca/education/',
        'Bank of Canada — education &amp; financial literacy resources',
    ),

    # Mapleleafweb (civic-ed resource) — offline since ~2024; replace with
    # the Historica Canada Civics portal which covers the same material
    (
        'https://www.mapleleafweb.com/',
        'https://www.historicacanada.ca/civics',
        'Historica Canada — Civics education portal (replaces Mapleleafweb)',
    ),

    # ── B: Permanent redirects — update to canonical URL ─────────────────

    # NASA Earth Observatory moved to science.nasa.gov
    (
        'https://earthobservatory.nasa.gov/',
        'https://science.nasa.gov/earth/earth-observatory/',
        None,
    ),

    # Natural Resources Canada renamed domain
    (
        'https://www.nrcan.gc.ca/',
        'https://natural-resources.canada.ca/',
        None,
    ),

    # Samara Canada rebranded to Samara Centre for Democracy
    (
        'https://www.samaracanada.com/',
        'https://www.samaracentre.ca/',
        'Samara Centre for Democracy — youth civic-engagement research',
    ),

    # Douglas & McIntyre restructured product URLs
    (
        'https://www.douglas-mcintyre.com/book/indian-horse',
        'https://douglas-mcintyre.com/products/9781553654025',
        None,
    ),

    # Harvard TH Chan nutrition source moved to dedicated subdomain
    (
        'https://www.hsph.harvard.edu/nutritionsource/',
        'https://nutritionsource.hsph.harvard.edu/',
        None,
    ),

    # Conference Board of Canada dropped www subdomain
    (
        'https://www.conferenceboard.ca/',
        'https://conferenceboard.ca/',
        None,
    ),

    # DocsTeach dropped www
    (
        'https://www.docsteach.org/',
        'https://docsteach.org/',
        None,
    ),
]


def patch_file(path: Path, replacements) -> list:
    """Apply all URL replacements to a single HTML file. Returns list of
    changes made as (old_url, new_url) pairs."""
    text = path.read_text()
    changes = []
    for item in replacements:
        old_url, new_url, new_label = item
        if old_url not in text:
            continue
        if new_label:
            # Replace both the href AND the link-text within the <a> tag
            pattern = re.compile(
                r'<a([^>]*href=")' + re.escape(old_url) + r'"([^>]*)>([^<]+)</a>',
                re.S,
            )
            text = pattern.sub(
                r'<a\g<1>' + new_url + r'"\g<2>>' + new_label + r'</a>',
                text,
            )
        else:
            text = text.replace(old_url, new_url)
        changes.append((old_url, new_url))
    if changes:
        path.write_text(text)
    return changes


def main():
    print("R1d — fixing broken / redirected links in curriculum sub-pages")
    print()
    total = 0
    for p in sorted(ROOT.glob('courses/*_curriculum.html')):
        code = p.stem.replace('_curriculum', '')
        changes = patch_file(p, REPLACEMENTS)
        for old, new in changes:
            total += 1
            print(f"  ✓ [{code}]  {old[:70]}")
            print(f"           → {new[:70]}")
    print()
    print(f"  Total fixes applied: {total}")


if __name__ == '__main__':
    main()
