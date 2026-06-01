# MindView Video Licensing & Compliance Policy

**Owner-approved policy. Future contributors MUST read this before adding,
downloading, or re-hosting any video content on the MindView site.**

This document is paired with three operational scripts in `scripts/`:

| Script | Purpose |
|---|---|
| `scripts/video-inventory.py` | Enumerates every video embed on the site (YouTube + GCS). |
| `scripts/video-audit.py`     | Twice-weekly health check; non-zero exit on any breakage. |
| `scripts/find-cc-licensed.py`| Identifies which embedded YouTube videos are Creative-Commons-licensed. |

---

## 1. What we own

We own and self-host a library of lesson recordings in the Google Cloud
Storage bucket **`dondelete_vi`** (~16.1 GB, ~817 MP4 files). These are
referenced from the chapter pages via:

```html
<video controls preload="none">
  <source src="https://storage.googleapis.com/dondelete_vi/{COURSE}/{file}.mp4" type="video/mp4">
</video>
```

These recordings are the **primary** video source on every course where they
exist (currently five Grade-12 courses, including SBI4U). They are
unambiguously ours to keep, re-encode, mirror, and continue to host.

Operational rule: **never delete or rename a file in `dondelete_vi`**
without explicit owner approval. The bucket name encodes that.

## 2. What is third-party

The remainder of the site (the great majority of embeds — roughly 540 unique
videos across all chapter pages) is **YouTube embeds owned by other
creators**. Each is included via the standard YouTube IFrame embed:

```html
<iframe src="https://www.youtube-nocookie.com/embed/{ID}?rel=0&modestbranding=1" ...>
```

The IFrame embed is YouTube's officially supported way to surface another
channel's content; it remains within the bounds of YouTube's Terms of
Service and the uploader's choice of licence.

### What that does NOT permit

- We **must not** download these videos to our own infrastructure.
- We **must not** rip the audio, transcode, mirror, cache, or re-upload
  these videos anywhere we control (GCS, R2, our own server, etc.).
- We **must not** mass-scrape the channels for backup copies — even if our
  intent is purely "in case the upload disappears."

The legally clean way to keep a third-party YouTube video on our pages is
to keep it embedded via the IFrame and to **rotate to a replacement** the
moment the original goes dark.

## 3. The Creative Commons exception (narrow + audited)

A small fraction of YouTube videos are published under
**Creative Commons Attribution (CC BY 3.0)**. For those, the licence does
permit download, redistribution, and re-hosting — subject to **proper
attribution and non-commercial use** in our context.

To discover which embedded videos qualify, run:

```bash
python3 scripts/find-cc-licensed.py > /tmp/license-report.tsv
```

The script reads each unique YouTube ID, fetches the watch page, and looks
for the explicit CC markers YouTube exposes in the page (`isCreativeCommons:true`,
`creativeCommons:true`, the visible "License: Creative Commons Attribution"
line, etc.). The TSV columns are:

```
course   chapter   topic   video_id   license_status
```

`license_status` is one of `cc`, `standard`, or `unknown`. Only `cc` rows
are download/re-host candidates.

### Required steps before re-hosting any CC video

1. Re-verify the licence by visiting the watch page yourself — the script's
   verdict is advisory, not gospel.
2. Record, in a checked-in attribution file alongside the MP4:
   - The original channel name and uploader handle.
   - The original video title.
   - The original watch URL.
   - The licence (`Creative Commons Attribution 3.0`) and a link
     to https://creativecommons.org/licenses/by/3.0/.
3. Upload the MP4 to `dondelete_vi` under a clearly attributed path
   (e.g. `dondelete_vi/THIRD_PARTY_CC/{channel}/{title}.mp4`).
4. Swap the chapter HTML from the IFrame embed to the `<video>` tag,
   keeping the attribution visible to the student (e.g. in the
   `vid-title` span: `"... — {Channel} (CC BY 3.0)"`).
5. Commit the HTML change and the attribution file together.

### What we will NOT do, even for CC videos

- **No bulk download** of an entire channel even if everything on the
  channel is CC. We download one CC video at a time, on demand, when an
  embed has broken or is at obvious risk.
- **No removal of attribution** from the embedded title or page metadata.
- **No commercial re-use** outside MindView's existing student-facing site.

## 4. Owned recordings come first

When a `dondelete_vi` recording covers the same topic as a third-party
YouTube embed on the same chapter page, **the owned recording is primary**
and the YouTube embed is removed (not merely demoted). This is already in
place for the five Grade-12 courses where we have a full recording set.

For new courses (Wave 2 onward):
1. If we already have an owned recording in `dondelete_vi`, use it.
2. Otherwise, prefer **CC-licensed channels** for new embeds — they are
   resilient (we can re-host if they vanish) and legally clean.
3. Standard-licence YouTube embeds remain acceptable as a fallback, but
   they live on borrowed time and will appear in the audit's broken list
   the moment the uploader removes the video.

## 5. Audit cadence (twice weekly)

`scripts/video-audit.py` probes every YouTube ID and every GCS URL in
parallel (20 workers) and writes a JSON report to
`/tmp/mindview-video-audit-YYYY-MM-DD.json`. It exits with status `1` if
**any** video is broken — suitable for cron + email-on-failure.

Recommended cron line (Monday + Thursday at 09:00 local time):

```cron
0 9 * * 1,4 cd /path/to/mindview && python3 scripts/video-audit.py
```

Why twice weekly: YouTube takedowns and channel deletions happen
continuously, but waiting a week to discover a broken embed is too long
for a student-facing course; auditing more often than every few days
risks rate-limiting from YouTube oEmbed.

## 6. Replacement workflow (when a video breaks)

1. **Detection.** The Monday or Thursday audit fails. The cron email lists
   each broken video by source type, ID, and the chapter file + topic.
2. **Search for a like-for-like replacement.** Prefer the same channel
   (uploader sometimes re-uploads under a new ID); failing that, prefer a
   CC-licensed channel covering the same Ontario curriculum expectation.
3. **Swap the iframe** in the chapter HTML, preserving the surrounding
   `vid-title` and the relative position in the topic block. Update the
   `vid-title` to credit the new source.
4. **Re-run the audit** locally to confirm the swap is healthy:
   ```bash
   python3 scripts/video-audit.py
   ```
5. **Commit** the HTML change with a message that lists the dead ID and the
   new ID, e.g. `videos(chw3m/ch3): replace IhYJbCAcCKE → q5b3wYxL3vM (CC BY)`.
6. **Deploy via the usual staging-first flow** (`scripts/safe-deploy.sh`).

If the broken video was a `dondelete_vi` MP4 (rare — the bucket is private
and stable), the failure is almost certainly a transient GCS issue or an
inadvertent ACL change; **do not delete or re-upload** without owner
approval, since the file is irreplaceable.

## 7. Quick reference — what counts as legal

| Action | Status |
|---|---|
| Embed a YouTube video via the IFrame embed | OK (any licence) |
| Keep an owned `dondelete_vi` MP4 on `<video>` tag | OK (we own it) |
| Re-host a CC-BY YouTube video as our own MP4 | OK *only* with attribution + per-video justification |
| Download a non-CC YouTube video to GCS / our server | NOT OK |
| Bulk-download an entire channel (even if CC) | NOT OK |
| Re-encode and strip attribution off a CC video | NOT OK |
| Remove an owned recording when a third-party embed exists | NOT OK without owner approval |

## 8. Where to ask

If a contributor is unsure whether a particular action is allowed, the
default answer is **stop and ask the owner first** — the same rule that
applies in `CLAUDE.md` for architectural changes applies here for content
sourcing. Re-hosting third-party content is exactly the kind of change
that is cheap to avoid up front and expensive to clean up later.
