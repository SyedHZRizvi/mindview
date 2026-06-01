#!/usr/bin/env python3
"""
video-inventory.py — Enumerate every video embed across the MindView site.

Walks every courses/{code}/ch*.html and courses/{code}.html (excluding
*_curriculum.html landing/curriculum files). For each video reference it
records:
    course code, chapter file, topic title, source type, source ID.

Recognised sources:
    YouTube:  <iframe ... src="https://www.youtube-nocookie.com/embed/{ID}..." ...>
              <iframe ... src="https://www.youtube.com/embed/{ID}..." ...>
    GCS MP4:  <video><source src="https://storage.googleapis.com/{bucket}/{path}.mp4" ...>

Outputs:
    stdout                              — tab-separated, header row first.
    /tmp/mindview-video-inventory.json  — list of records (same fields).

Print summary counts at the end to stderr (so stdout stays TSV-only).

Python 3 stdlib only.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

# Repo root = parent of the directory holding this script.
REPO_ROOT = Path(__file__).resolve().parent.parent
COURSES_DIR = REPO_ROOT / "courses"
OUT_JSON = Path("/tmp/mindview-video-inventory.json")

# Regex to capture the most-recent vid-title preceding a video tag, plus the
# video tag itself. We walk the file linearly so we can pair each video with
# the nearest preceding <span class="vid-title">...</span>.
VID_TITLE_RE = re.compile(
    r'<span\s+class="vid-title"[^>]*>(.*?)</span>',
    re.IGNORECASE | re.DOTALL,
)
YOUTUBE_IFRAME_RE = re.compile(
    r'<iframe[^>]*\bsrc="https?://(?:www\.)?youtube(?:-nocookie)?\.com/embed/([A-Za-z0-9_\-]{6,})[^"]*"',
    re.IGNORECASE,
)
GCS_SOURCE_RE = re.compile(
    r'<source[^>]*\bsrc="(https?://storage\.googleapis\.com/[^"]+\.mp4)"',
    re.IGNORECASE,
)


def strip_tags(html: str) -> str:
    """Cheap tag stripper for a vid-title span's inner HTML."""
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_records(path: Path, course_code: str) -> list[dict]:
    """Pair every video reference in `path` with its nearest preceding vid-title."""
    try:
        html = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    # Collect every interesting span as (offset, kind, payload):
    events: list[tuple[int, str, str]] = []
    for m in VID_TITLE_RE.finditer(html):
        events.append((m.start(), "title", strip_tags(m.group(1))))
    for m in YOUTUBE_IFRAME_RE.finditer(html):
        events.append((m.start(), "youtube", m.group(1)))
    for m in GCS_SOURCE_RE.finditer(html):
        events.append((m.start(), "gcs", m.group(1)))

    events.sort(key=lambda e: e[0])

    rows: list[dict] = []
    current_title = ""
    chapter_rel = str(path.relative_to(REPO_ROOT))
    for _offset, kind, payload in events:
        if kind == "title":
            current_title = payload
        elif kind == "youtube":
            rows.append({
                "course": course_code,
                "chapter": chapter_rel,
                "topic": current_title,
                "source_type": "youtube",
                "source_id": payload,
            })
        elif kind == "gcs":
            rows.append({
                "course": course_code,
                "chapter": chapter_rel,
                "topic": current_title,
                "source_type": "gcs",
                "source_id": payload,
            })
    return rows


def discover_html_files() -> list[tuple[Path, str]]:
    """Return (path, course_code) for every chapter file and landing page.

    Excludes *_curriculum.html (curriculum overview pages — no videos there).
    """
    pairs: list[tuple[Path, str]] = []
    if not COURSES_DIR.is_dir():
        return pairs
    for entry in sorted(COURSES_DIR.iterdir()):
        if entry.is_dir():
            course_code = entry.name
            for ch in sorted(entry.glob("ch*.html")):
                pairs.append((ch, course_code))
        elif entry.is_file() and entry.suffix == ".html":
            name = entry.name
            if name.endswith("_curriculum.html"):
                continue
            course_code = name[: -len(".html")]
            pairs.append((entry, course_code))
    return pairs


def main() -> int:
    pairs = discover_html_files()
    all_rows: list[dict] = []
    for path, course in pairs:
        all_rows.extend(extract_records(path, course))

    # TSV to stdout.
    header = ["course", "chapter", "topic", "source_type", "source_id"]
    sys.stdout.write("\t".join(header) + "\n")
    for row in all_rows:
        sys.stdout.write(
            "\t".join(str(row[h]).replace("\t", " ").replace("\n", " ") for h in header)
            + "\n"
        )

    # JSON sidecar.
    try:
        OUT_JSON.write_text(json.dumps(all_rows, indent=2, ensure_ascii=False))
    except OSError as exc:
        sys.stderr.write(f"warn: could not write {OUT_JSON}: {exc}\n")

    # Summary counts to stderr.
    yt_ids = {r["source_id"] for r in all_rows if r["source_type"] == "youtube"}
    gcs_urls = {r["source_id"] for r in all_rows if r["source_type"] == "gcs"}
    sys.stderr.write("\n=== Inventory summary ===\n")
    sys.stderr.write(f"HTML files scanned:       {len(pairs)}\n")
    sys.stderr.write(f"Total video references:   {len(all_rows)}\n")
    sys.stderr.write(f"  YouTube references:     {sum(1 for r in all_rows if r['source_type']=='youtube')}\n")
    sys.stderr.write(f"  GCS MP4 references:     {sum(1 for r in all_rows if r['source_type']=='gcs')}\n")
    sys.stderr.write(f"Unique YouTube IDs:       {len(yt_ids)}\n")
    sys.stderr.write(f"Unique GCS MP4 URLs:      {len(gcs_urls)}\n")
    sys.stderr.write(f"JSON sidecar:             {OUT_JSON}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
