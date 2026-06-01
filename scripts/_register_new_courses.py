#!/usr/bin/env python3
"""Add all 20 new Wave-2 courses to verify-baseline.py's
COURSES_AND_CHAPTERS list. Idempotent — safe to re-run."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
VERIFIER = ROOT / "scripts" / "verify-baseline.py"

# (code, expected_chapter_count) — derived from courses/{code}/ contents
NEW_COURSES = [
    ("snc2d", 5), ("eng2d", 5), ("chc2d", 5), ("chv2o", 3), ("glc2o", 3),
    ("chy4u", 6), ("chw3m", 5), ("clu3m", 5), ("cln4u", 5),
    ("cgf3m", 5), ("cgw4u", 5), ("hsc4m", 5),
    ("baf3m", 5), ("bat4m", 5), ("bbb4m", 5), ("boh4m", 5),
    ("hfn3m", 5), ("hfa4m", 5), ("mct3m", 5), ("mct4m", 5),
]


def main():
    src = VERIFIER.read_text()

    # Find the COURSES_AND_CHAPTERS = [...] block and replace contents
    m = re.search(r"COURSES_AND_CHAPTERS = \[([\s\S]*?)\]", src)
    if not m:
        raise SystemExit("COURSES_AND_CHAPTERS list not found in verifier")
    current_block = m.group(1)

    # Extract existing courses + counts so we can de-dup
    existing = dict(re.findall(r'\("(\w+)",\s*(\d+)\)', current_block))

    # Merge new courses
    merged = dict(existing)
    for code, n in NEW_COURSES:
        merged[code] = str(n)

    # Sort: grade 10 first, then 11, then 12; within grade alphabetical
    def grade_of(code):
        # 2nd char of Ontario course code is the grade digit
        return int(code[2]) if len(code) >= 3 and code[2].isdigit() else 9

    items = sorted(merged.items(), key=lambda kv: (grade_of(kv[0]), kv[0]))

    # Group output 4-per-line
    lines = []
    for i in range(0, len(items), 4):
        chunk = items[i:i + 4]
        lines.append("    " + ", ".join(f'("{c}", {n})' for c, n in chunk) + ",")
    new_block = "\n" + "\n".join(lines) + "\n"

    new_src = src[:m.start(1)] + new_block + src[m.end(1):]
    VERIFIER.write_text(new_src)
    print(f"Updated verifier — now tracks {len(items)} courses total:")
    for c, n in items:
        print(f"  ({c}, {n})")


if __name__ == "__main__":
    main()
