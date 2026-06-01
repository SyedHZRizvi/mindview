#!/usr/bin/env python3
"""
find-cc-licensed.py — Discover which embedded YouTube videos are Creative
Commons (CC-BY 3.0) licensed and therefore legitimate re-host candidates.

For every unique YouTube ID referenced in the site, fetches
    https://www.youtube.com/watch?v={id}
and looks for the markers YouTube exposes when a video is published under
the Creative Commons licence:
  * The player-response field   "isCreativeCommons":true
  * The microformat field       "isUnlisted":false + "uploadDate" alongside
                                "creativeCommons":true
  * The page-meta line          "License":"Creative Commons - Attribution"
                                or "License: Creative Commons Attribution"

A page where at least one marker is present is treated as CC-licensed.
Anything else (including pages we couldn't fetch) is "standard" or
"unknown" and may NOT be downloaded / re-hosted.

Outputs:
    stdout — tab-separated:
        course   chapter   topic   video_id   license_status
    where license_status is one of: cc | standard | unknown.

    stderr — summary counts plus the explicit list of CC-licensed videos
             (these are the only legitimate download/re-host candidates).

Python 3 stdlib only.
"""

from __future__ import annotations

import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
COURSES_DIR = REPO_ROOT / "courses"

WATCH_URL = "https://www.youtube.com/watch?v={vid}&hl=en&gl=US"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
WORKERS = 10
TIMEOUT_S = 20
RETRIES = 2

VID_TITLE_RE = re.compile(
    r'<span\s+class="vid-title"[^>]*>(.*?)</span>',
    re.IGNORECASE | re.DOTALL,
)
YOUTUBE_IFRAME_RE = re.compile(
    r'<iframe[^>]*\bsrc="https?://(?:www\.)?youtube(?:-nocookie)?\.com/embed/([A-Za-z0-9_\-]{6,})[^"]*"',
    re.IGNORECASE,
)

# Markers YouTube exposes for CC-licensed videos.
CC_MARKERS = (
    re.compile(r'"isCreativeCommons"\s*:\s*true', re.IGNORECASE),
    re.compile(r'"creativeCommons"\s*:\s*true', re.IGNORECASE),
    re.compile(r'Creative Commons\s*[-–—:]?\s*Attribution', re.IGNORECASE),
    re.compile(r'License\s*[:\s]+Creative Commons Attribution', re.IGNORECASE),
    re.compile(r'"license"\s*:\s*"Creative Commons[^"]*"', re.IGNORECASE),
)


def strip_tags(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text).strip()


def discover_records() -> list[dict]:
    pairs: list[tuple[Path, str]] = []
    if COURSES_DIR.is_dir():
        for entry in sorted(COURSES_DIR.iterdir()):
            if entry.is_dir():
                code = entry.name
                for ch in sorted(entry.glob("ch*.html")):
                    pairs.append((ch, code))
            elif entry.is_file() and entry.suffix == ".html" and not entry.name.endswith("_curriculum.html"):
                pairs.append((entry, entry.stem))

    records: list[dict] = []
    for path, course in pairs:
        try:
            html = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        events: list[tuple[int, str, str]] = []
        for m in VID_TITLE_RE.finditer(html):
            events.append((m.start(), "title", strip_tags(m.group(1))))
        for m in YOUTUBE_IFRAME_RE.finditer(html):
            events.append((m.start(), "youtube", m.group(1)))
        events.sort(key=lambda e: e[0])

        current_title = ""
        chapter_rel = str(path.relative_to(REPO_ROOT))
        for _offset, kind, payload in events:
            if kind == "title":
                current_title = payload
            elif kind == "youtube":
                records.append({
                    "course": course,
                    "chapter": chapter_rel,
                    "topic": current_title,
                    "video_id": payload,
                })
    return records


def fetch_watch_page(vid: str) -> tuple[str, str]:
    """Return (status, body). status: 'ok' | 'unavailable' | 'error:<msg>'."""
    url = WATCH_URL.format(vid=vid)
    last_err = ""
    for attempt in range(RETRIES + 1):
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                return ("ok", body)
        except urllib.error.HTTPError as e:
            if e.code in (404, 410):
                return ("unavailable", "")
            last_err = f"HTTP {e.code}"
        except urllib.error.URLError as e:
            last_err = f"URLError: {e.reason}"
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
        if attempt < RETRIES:
            time.sleep(0.5 * (attempt + 1))
    return (f"error:{last_err}", "")


def classify(vid: str) -> str:
    """Return 'cc' | 'standard' | 'unknown' for a single YouTube ID."""
    status, body = fetch_watch_page(vid)
    if status != "ok":
        return "unknown"
    for pat in CC_MARKERS:
        if pat.search(body):
            return "cc"
    # The watch page reliably contains a "License" line for non-CC videos as
    # well (typically "Standard YouTube License"). If we got a body but none
    # of the CC markers match, we're confident in "standard".
    if re.search(r'Standard YouTube License', body, re.IGNORECASE) or \
       re.search(r'"license"\s*:\s*"YouTube"', body, re.IGNORECASE):
        return "standard"
    # We fetched a page but couldn't determine licence — flag as unknown.
    return "unknown"


def main() -> int:
    records = discover_records()
    if not records:
        sys.stdout.write("course\tchapter\ttopic\tvideo_id\tlicense_status\n")
        sys.stderr.write("No YouTube embeds discovered.\n")
        return 0

    unique_ids = sorted({r["video_id"] for r in records})
    sys.stderr.write(
        f"Probing {len(unique_ids)} unique YouTube IDs "
        f"({len(records)} total references) with {WORKERS} workers...\n"
    )

    verdicts: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        fut_map = {ex.submit(classify, vid): vid for vid in unique_ids}
        for fut in as_completed(fut_map):
            vid = fut_map[fut]
            try:
                verdicts[vid] = fut.result()
            except Exception:
                verdicts[vid] = "unknown"

    # TSV out.
    sys.stdout.write("course\tchapter\ttopic\tvideo_id\tlicense_status\n")
    for r in records:
        status = verdicts.get(r["video_id"], "unknown")
        topic = r["topic"].replace("\t", " ").replace("\n", " ")
        sys.stdout.write(
            f"{r['course']}\t{r['chapter']}\t{topic}\t{r['video_id']}\t{status}\n"
        )

    cc_ids = [v for v, s in verdicts.items() if s == "cc"]
    std_ids = [v for v, s in verdicts.items() if s == "standard"]
    unk_ids = [v for v, s in verdicts.items() if s == "unknown"]

    sys.stderr.write("\n=== Licence summary ===\n")
    sys.stderr.write(f"Unique YouTube IDs:  {len(unique_ids)}\n")
    sys.stderr.write(f"  Creative Commons:  {len(cc_ids)}\n")
    sys.stderr.write(f"  Standard:          {len(std_ids)}\n")
    sys.stderr.write(f"  Unknown:           {len(unk_ids)}\n")

    if cc_ids:
        sys.stderr.write("\n=== Creative-Commons-licensed videos (download/re-host candidates) ===\n")
        # Show every reference for the CC ids so an operator can copy attribution per page.
        cc_set = set(cc_ids)
        for r in records:
            if r["video_id"] in cc_set:
                sys.stderr.write(
                    f"  CC  {r['video_id']}  https://www.youtube.com/watch?v={r['video_id']}  "
                    f"<- {r['course']} / {r['chapter']}: {r['topic']}\n"
                )
        sys.stderr.write(
            "\nRe-host policy: download these only with full attribution "
            "(channel + uploader + title + CC-BY 3.0 link) and use them "
            "non-commercially. See docs/VIDEO_LICENSING.md.\n"
        )
    else:
        sys.stderr.write("\nNo CC-licensed videos found. No legitimate re-host candidates.\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
