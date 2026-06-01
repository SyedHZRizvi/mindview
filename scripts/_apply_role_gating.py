#!/usr/bin/env python3
# scripts/_apply_role_gating.py
#
# Stamp the `instructor-only` CSS class onto every answer-key / solution /
# rubric element across every assessment HTML file. Runtime gating is then
# performed by /js/role-gated.js + /css/role-gated.css (injected by
# functions/_middleware.js into every HTML response): the class is hidden
# from students (and scrubbed from the DOM) and revealed for teacher /
# admin / superuser.
#
# Targets (in priority order, all idempotent):
#
#   1. `<details>` blocks whose `<summary>` text contains any of:
#        "Answer Key", "Complete Answer Key", "Answer Click",
#        "Solution" / "Show solution", "Marking", "Rubric",
#        "Reveal expected answer", "Reveal"
#      → Add `instructor-only` to the <details> tag's class list.
#
#   2. `<div class="solution">` blocks → add `instructor-only` to class list.
#
#   3. `<div class="rubric">` blocks → add `instructor-only` to class list.
#
#   4. `<div class="answer-key">` and `<details class="answer-key">` → add
#      `instructor-only` (these already use a recognizable class).
#
# Idempotent: if the element already lists `instructor-only`, it is left
# alone. Re-running this script will not double-stamp.
#
# What is NOT touched:
#   - `data-answer="..."` attributes on form inputs (used by the AS quiz's
#     instant-check buttons). Per policy, per-question instant feedback is
#     allowed for AS practice quizzes; only the human-readable answer-key
#     reveal is gated.
#   - `<button onclick="chkMC(...)">Check</button>` and `chkMC` / `cN` JS.
#   - `<div class="sol">` blocks. These appear in OF tests as per-question
#     feedback driven by chkMC; they are kept visible so students get
#     "Correct!" / "Try again" feedback without seeing the worked-solution
#     prose. The aggregate "Complete Answer Key" details block is what
#     reveals OF solutions, and that IS gated (rule 1).
#
# CLI:
#   python3 scripts/_apply_role_gating.py            # apply changes
#   python3 scripts/_apply_role_gating.py --dry-run  # report only
#
# Walks both file patterns:
#   - assessments/<course>/Unit*_*.html and assessments/<course>/Final_Exam.html
#     (eng4u, sbi3u, sch3u, ics3u, eng3u, snc2d, eng2d, chc2d, chv2o, glc2o,
#      chy4u, chw3m, clu3m, cln4u, cgf3m, cgw4u, hsc4m, hfa4m, ics4u, sph3u,
#      sph4u, sch4u, sbi4u, mcv4u)
#   - assessments/<course>_*.html (flat pattern: mcr3u, mhf4u, mdm4u, sbi3u,
#     sch3u, baf3m, bat4m, bbb4m, boh4m, hfn3m, mct3m, mct4m)
#
# The script is pure stdlib; no external dependencies.

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ASSESS_DIR = REPO_ROOT / "assessments"

# Regex helpers ---------------------------------------------------------------

# Match a single `class="..."` attribute (capturing the inner value).
CLASS_ATTR_RE = re.compile(r'class\s*=\s*"([^"]*)"', re.IGNORECASE)

# Trigger keywords for <summary> text. Case-insensitive substring match on
# the rendered text inside <summary>...</summary> (HTML entities tolerated;
# we match on the raw bytes since the keywords are all ASCII).
SUMMARY_TRIGGERS = (
    "answer key",
    "answer click",
    "complete answer key",
    "complete worked answer key",
    "marking",
    "rubric",
    "reveal expected answer",
    "reveal",
    "show solution",
    "solution",
)


def add_instructor_only(class_value: str) -> str:
    """Return class_value with `instructor-only` appended if not already
    present. Preserves existing classes and whitespace boundaries."""
    classes = class_value.split()
    if "instructor-only" in classes:
        return class_value
    classes.append("instructor-only")
    return " ".join(classes)


def upsert_class_on_open_tag(open_tag: str) -> tuple[str, bool]:
    """Given a single open-tag string like `<details>` or
    `<details class="answer-key">` or `<div class="solution"   id="x">`,
    return (new_open_tag, changed). Idempotent: if `instructor-only` is
    already in the class list, no change is made."""
    m = CLASS_ATTR_RE.search(open_tag)
    if m:
        existing = m.group(1)
        new_value = add_instructor_only(existing)
        if new_value == existing:
            return open_tag, False
        new_tag = open_tag[: m.start(1)] + new_value + open_tag[m.end(1):]
        return new_tag, True
    # No class attribute — insert one immediately after the tag name.
    # open_tag looks like: <tagname ...> or <tagname>
    # Insert `class="instructor-only"` after the tagname.
    # Find the end of the tag name.
    tag_name_match = re.match(r"<([A-Za-z][A-Za-z0-9]*)", open_tag)
    if not tag_name_match:
        return open_tag, False
    name_end = tag_name_match.end()
    new_tag = (
        open_tag[:name_end]
        + ' class="instructor-only"'
        + open_tag[name_end:]
    )
    return new_tag, True


def gate_details_with_triggered_summary(html: str) -> tuple[str, int]:
    """Find every `<details ...>...<summary ...>...</summary>` whose summary
    text contains one of SUMMARY_TRIGGERS, and stamp `instructor-only` on
    the <details> open tag. Returns (new_html, count_changed)."""

    # Match `<details` (open tag with optional attributes) lazily followed
    # by anything up to `<summary` ... `</summary>`.
    # We use re.IGNORECASE to be safe with `<Details>`-style markup.
    pattern = re.compile(
        r"(<details\b[^>]*>)"           # group 1: details open tag
        r"(\s*)"                         # group 2: whitespace
        r"(<summary\b[^>]*>)"            # group 3: summary open tag
        r"(.*?)"                         # group 4: summary text (lazy)
        r"(</summary>)",                 # group 5: summary close
        re.IGNORECASE | re.DOTALL,
    )

    count = 0

    def repl(m: re.Match) -> str:
        nonlocal count
        details_tag = m.group(1)
        ws = m.group(2)
        sum_open = m.group(3)
        sum_text = m.group(4)
        sum_close = m.group(5)
        # Lowercase the summary text for matching (we tolerate HTML entities
        # and emoji bytes — keywords are pure ASCII).
        haystack = sum_text.lower()
        if not any(trigger in haystack for trigger in SUMMARY_TRIGGERS):
            return m.group(0)
        new_open, changed = upsert_class_on_open_tag(details_tag)
        if changed:
            count += 1
        return new_open + ws + sum_open + sum_text + sum_close

    new_html = pattern.sub(repl, html)
    return new_html, count


def gate_div_class(html: str, class_name: str) -> tuple[str, int]:
    """Find every `<div ... class="...class_name..." ...>` and stamp
    `instructor-only` onto its class list. Returns (new_html, count_changed).
    Matches when class_name is a whole-word token in the class attribute."""

    # Match a div open tag whose class attribute contains class_name as a
    # whole-word token. We tolerate the class attribute appearing anywhere
    # in the attribute list, and additional attributes around it.
    # Pattern: <div ...class="...{class_name}..." ...>
    # We use a two-step approach: find all <div ...>, then inspect the
    # class attribute for the token.

    div_open_re = re.compile(r"<div\b[^>]*>", re.IGNORECASE)
    count = 0

    def repl(m: re.Match) -> str:
        nonlocal count
        open_tag = m.group(0)
        class_m = CLASS_ATTR_RE.search(open_tag)
        if not class_m:
            return open_tag
        tokens = class_m.group(1).split()
        if class_name not in tokens:
            return open_tag
        new_open, changed = upsert_class_on_open_tag(open_tag)
        if changed:
            count += 1
        return new_open

    new_html = div_open_re.sub(repl, html)
    return new_html, count


def gate_details_class(html: str, class_name: str) -> tuple[str, int]:
    """Same as gate_div_class but for `<details class="...class_name...">`."""

    open_re = re.compile(r"<details\b[^>]*>", re.IGNORECASE)
    count = 0

    def repl(m: re.Match) -> str:
        nonlocal count
        open_tag = m.group(0)
        class_m = CLASS_ATTR_RE.search(open_tag)
        if not class_m:
            return open_tag
        tokens = class_m.group(1).split()
        if class_name not in tokens:
            return open_tag
        new_open, changed = upsert_class_on_open_tag(open_tag)
        if changed:
            count += 1
        return new_open

    new_html = open_re.sub(repl, html)
    return new_html, count


# File walk ------------------------------------------------------------------


def iter_assessment_files(root: Path) -> list[Path]:
    """Return every assessment HTML file in deterministic sorted order."""
    if not root.is_dir():
        return []
    files: list[Path] = []
    # Flat-style: assessments/*.html (mcr3u, mhf4u, mdm4u, baf3m, etc.)
    for entry in sorted(root.iterdir()):
        if entry.is_file() and entry.suffix.lower() == ".html":
            files.append(entry)
        elif entry.is_dir():
            # Subdirectory-style: assessments/<course>/*.html
            for sub in sorted(entry.iterdir()):
                if sub.is_file() and sub.suffix.lower() == ".html":
                    files.append(sub)
    return files


def patch_file(html: str) -> tuple[str, int]:
    """Apply all four gating rules. Returns (new_html, total_elements_gated)."""
    total = 0
    html, n1 = gate_details_with_triggered_summary(html)
    total += n1
    html, n2 = gate_div_class(html, "solution")
    total += n2
    html, n3 = gate_div_class(html, "rubric")
    total += n3
    # answer-key may exist as either <details class="answer-key"> or
    # <div class="answer-key"> — cover both.
    html, n4 = gate_details_class(html, "answer-key")
    total += n4
    html, n5 = gate_div_class(html, "answer-key")
    total += n5
    return html, total


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Stamp `instructor-only` class on answer-key / solution "
        "/ rubric elements across every assessment HTML file."
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Report changes per file without writing.",
    )
    ap.add_argument(
        "--root",
        type=Path,
        default=ASSESS_DIR,
        help="Path to assessments directory (default: <repo>/assessments).",
    )
    args = ap.parse_args()

    files = iter_assessment_files(args.root)
    if not files:
        print(f"No HTML files found under {args.root}", file=sys.stderr)
        return 1

    total_files_modified = 0
    total_elements_gated = 0

    for f in files:
        original = f.read_text(encoding="utf-8")
        patched, n = patch_file(original)
        if n == 0 or patched == original:
            continue
        rel = f.relative_to(REPO_ROOT)
        print(f"{rel} -> {n} element(s) gated")
        total_files_modified += 1
        total_elements_gated += n
        if not args.dry_run:
            f.write_text(patched, encoding="utf-8")

    suffix = " (dry-run, no files written)" if args.dry_run else ""
    print()
    print(
        f"Total: {total_files_modified} file(s) modified, "
        f"{total_elements_gated} element(s) gated{suffix}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
