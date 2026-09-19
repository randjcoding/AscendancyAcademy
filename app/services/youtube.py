"""Pull a YouTube transcript so a parent can turn a video into questions.

Fails soft on purpose: if a video has no captions or the library is missing,
we return a friendly message and the paste box in the UI still works.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

log = logging.getLogger("aa.youtube")

_ID_PATTERNS = (
    re.compile(r"(?:v=|/shorts/|/embed/|youtu\.be/)([A-Za-z0-9_-]{11})"),
    re.compile(r"^([A-Za-z0-9_-]{11})$"),
)


@dataclass
class Transcript:
    text: str
    video_id: str
    error: str = ""


def video_id_from(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        return ""
    for pattern in _ID_PATTERNS:
        match = pattern.search(raw)
        if match:
            return match.group(1)
    return ""


def fetch_transcript(url: str) -> Transcript:
    vid = video_id_from(url)
    if not vid:
        return Transcript("", "", "That does not look like a YouTube link. Paste the transcript instead.")
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except Exception:  # noqa: BLE001 - library optional
        log.info("youtube-transcript-api not installed")
        return Transcript("", vid, "Auto-fetch is off on this site. Paste the transcript instead.")
    try:
        rows = None
        # The library has shifted APIs across versions; try the common ones.
        getter = getattr(YouTubeTranscriptApi, "get_transcript", None)
        if callable(getter):
            rows = getter(vid, languages=["en", "en-US", "en-GB"])
        else:
            api = YouTubeTranscriptApi()
            fetched = api.fetch(vid, languages=["en", "en-US", "en-GB"])
            rows = getattr(fetched, "to_raw_data", lambda: fetched)()
        parts = []
        for row in rows or []:
            piece = row.get("text") if isinstance(row, dict) else getattr(row, "text", "")
            if piece:
                parts.append(str(piece).strip())
        text = " ".join(p for p in parts if p).strip()
        if not text:
            return Transcript("", vid, "That video has no captions we can read. Paste the transcript instead.")
        return Transcript(text, vid)
    except Exception as exc:  # noqa: BLE001 - many library-specific errors
        log.info("transcript fetch failed: %s", exc)
        return Transcript("", vid, "Could not get captions for that video. Paste the transcript instead.")
