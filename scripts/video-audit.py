#!/usr/bin/env python3
"""
video-audit.py — Twice-weekly health sweep of every video embed.

Probes every YouTube ID and GCS MP4 URL referenced in the site:
  * YouTube: GET https://www.youtube.com/oembed?url=...&format=json
            (200 = available; 401/404 = removed/private; everything else flagged)
  * GCS:    HTTP HEAD on the storage URL; 200 = OK.

Run in parallel (20 workers) via concurrent.futures.ThreadPoolExecutor.

Outputs:
    stdout                                       — human-readable summary.
    /tmp/mindview-video-audit-YYYY-MM-DD.json    — machine-readable report.

Exit code:
    0  — all OK.
    1  — at least one broken video (cron + mail-on-failure friendly).

Recommended cron line (Monday + Thursday, 09:00 — twice weekly):

    0 9 * * 1,4 cd /path/to/mindview && python3 scripts/video-audit.py

Python 3 stdlib only.
"""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
COURSES_DIR = REPO_ROOT / "courses"

OEMBED_URL = "https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={vid}&format=json"
USER_AGENT = "MindViewVideoAudit/1.0 (+https://mindview.pages.dev/)"
WORKERS = 20
TIMEOUT_S = 15
RETRIES = 2

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
    text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text).strip()


def discover_records() -> list[dict]:
    """Replicates video-inventory.py's traversal but in-process."""
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
        for m in GCS_SOURCE_RE.finditer(html):
            events.append((m.start(), "gcs", m.group(1)))
        events.sort(key=lambda e: e[0])

        current_title = ""
        chapter_rel = str(path.relative_to(REPO_ROOT))
        for _offset, kind, payload in events:
            if kind == "title":
                current_title = payload
            elif kind in ("youtube", "gcs"):
                records.append({
                    "course": course,
                    "chapter": chapter_rel,
                    "topic": current_title,
                    "source_type": kind,
                    "source_id": payload,
                })
    return records


def probe_youtube(vid: str) -> tuple[bool, int, str]:
    url = OEMBED_URL.format(vid=vid)
    last_status, last_err = 0, ""
    for attempt in range(RETRIES + 1):
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                return (resp.status == 200, resp.status, "")
        except urllib.error.HTTPError as e:
            last_status, last_err = e.code, f"HTTP {e.code}"
            # 401 (embed disabled) / 403 / 404 = won't get better with retries.
            if e.code in (401, 403, 404):
                return (False, e.code, last_err)
        except urllib.error.URLError as e:
            last_err = f"URLError: {e.reason}"
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
        if attempt < RETRIES:
            time.sleep(0.5 * (attempt + 1))
    return (False, last_status, last_err or "unknown error")


def probe_gcs(url: str) -> tuple[bool, int, str]:
    last_status, last_err = 0, ""
    for attempt in range(RETRIES + 1):
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                return (resp.status == 200, resp.status, "")
        except urllib.error.HTTPError as e:
            last_status, last_err = e.code, f"HTTP {e.code}"
            if e.code in (401, 403, 404):
                return (False, e.code, last_err)
        except urllib.error.URLError as e:
            last_err = f"URLError: {e.reason}"
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
        if attempt < RETRIES:
            time.sleep(0.5 * (attempt + 1))
    return (False, last_status, last_err or "unknown error")


def main() -> int:
    records = discover_records()
    if not records:
        sys.stdout.write("No video records discovered. Nothing to audit.\n")
        return 0

    # Build the *unique* probe set (dedup across pages).
    yt_ids = sorted({r["source_id"] for r in records if r["source_type"] == "youtube"})
    gcs_urls = sorted({r["source_id"] for r in records if r["source_type"] == "gcs"})

    sys.stdout.write(
        f"Auditing {len(yt_ids)} unique YouTube IDs and {len(gcs_urls)} unique GCS URLs "
        f"({len(records)} total references) with {WORKERS} workers...\n"
    )
    sys.stdout.flush()

    results: dict[tuple[str, str], tuple[bool, int, str]] = {}
    start = time.time()
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        future_map = {}
        for vid in yt_ids:
            future_map[ex.submit(probe_youtube, vid)] = ("youtube", vid)
        for url in gcs_urls:
            future_map[ex.submit(probe_gcs, url)] = ("gcs", url)
        for fut in as_completed(future_map):
            key = future_map[fut]
            try:
                results[key] = fut.result()
            except Exception as e:
                results[key] = (False, 0, f"executor: {type(e).__name__}: {e}")
    elapsed = time.time() - start

    broken_keys = {k for k, v in results.items() if not v[0]}

    # Fan back out: every reference inherits the verdict for its source_id.
    broken_refs: list[dict] = []
    ok_refs: list[dict] = []
    for r in records:
        key = (r["source_type"], r["source_id"])
        ok, status, err = results.get(key, (False, 0, "no result"))
        out = {**r, "ok": ok, "http_status": status, "error": err}
        (broken_refs if not ok else ok_refs).append(out)

    date_str = time.strftime("%Y-%m-%d")
    report_path = Path(f"/tmp/mindview-video-audit-{date_str}.json")
    report = {
        "audit_date": date_str,
        "audit_iso": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "elapsed_seconds": round(elapsed, 1),
        "totals": {
            "unique_youtube": len(yt_ids),
            "unique_gcs": len(gcs_urls),
            "unique_broken": len(broken_keys),
            "total_references": len(records),
            "broken_references": len(broken_refs),
        },
        "broken": broken_refs,
    }
    try:
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    except OSError as exc:
        sys.stderr.write(f"warn: could not write {report_path}: {exc}\n")

    # Human summary.
    sys.stdout.write("\n=== Video audit summary ===\n")
    sys.stdout.write(f"Date:              {date_str}\n")
    sys.stdout.write(f"Elapsed:           {elapsed:.1f}s\n")
    sys.stdout.write(f"Unique YouTube:    {len(yt_ids)}\n")
    sys.stdout.write(f"Unique GCS:        {len(gcs_urls)}\n")
    sys.stdout.write(f"Unique broken:     {len(broken_keys)}\n")
    sys.stdout.write(f"Total references:  {len(records)}\n")
    sys.stdout.write(f"Broken references: {len(broken_refs)}\n")
    sys.stdout.write(f"Report:            {report_path}\n")

    if broken_refs:
        sys.stdout.write("\n=== Broken videos ===\n")
        for r in broken_refs:
            sys.stdout.write(
                f"  [{r['source_type']:7}] {r['source_id']}  "
                f"(HTTP {r['http_status']}, {r['error']})  "
                f"<- {r['course']} / {r['chapter']}: {r['topic']}\n"
            )
        return 1

    sys.stdout.write("\nAll videos OK.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
