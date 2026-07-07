"""OpenReview provider — official API v2 (api2.openreview.net), no key.

The plain /notes endpoint now requires a browser challenge, but
/notes/search with source=forum returns the submission (root) notes directly,
each carrying title/abstract/authors. That is what we use.
"""
from __future__ import annotations

from typing import Optional

from .base import HttpClient, Paper, clean

API = "https://api2.openreview.net"


def _v(content: dict, key: str):
    """OpenReview v2 wraps every field as {'value': ...}."""
    node = content.get(key)
    if isinstance(node, dict):
        return node.get("value")
    return node


class OpenReviewProvider:
    name = "openreview"

    def __init__(self, client: Optional[HttpClient] = None):
        self.http = client or HttpClient(min_interval=0.3)

    def _paper_from(self, note: dict) -> Paper:
        c = note.get("content") or {}
        forum = note.get("forum")
        authors = _v(c, "authors") or []
        if isinstance(authors, str):
            authors = [authors]
        return Paper(
            title=clean(_v(c, "title")) or "(no title)",
            link=f"https://openreview.net/forum?id={forum}" if forum else None,
            source=self.name,
            authors=[a for a in authors if a],
            abstract=clean(_v(c, "abstract")),
            venue=clean(_v(c, "venue")),
            pdf_url=(f"https://openreview.net{_v(c, 'pdf')}"
                     if _v(c, "pdf") else None),
            paper_id=forum,
            extra={"keywords": _v(c, "keywords")} if _v(c, "keywords") else {},
        )

    def search(self, keyword: str, max_results: int = 25) -> list[Paper]:
        papers: list[Paper] = []
        offset = 0
        page = 25
        seen: set[str] = set()
        while len(papers) < max_results:
            resp = self.http.get(
                f"{API}/notes/search",
                params={
                    "term": keyword,
                    "source": "forum",   # <- return submissions, not reviews
                    "limit": min(page, max_results - len(papers)),
                    "offset": offset,
                },
            )
            resp.raise_for_status()
            notes = resp.json().get("notes") or []
            if not notes:
                break
            for n in notes:
                fid = n.get("forum")
                if fid in seen:
                    continue
                seen.add(fid)
                papers.append(self._paper_from(n))
            offset += len(notes)
            if len(notes) < page:
                break
        return papers[:max_results]
