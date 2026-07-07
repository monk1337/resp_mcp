"""DBLP provider — free publication search API (no key). Strong CS-venue coverage.

Useful for ACL/NeurIPS/IJCAI/CVPR/PMLR metadata + the publisher ``ee`` link.
Docs: https://dblp.org/faq/How+to+use+the+dblp+search+API.html
"""
from __future__ import annotations

from typing import Optional

from .base import HttpClient, Paper, clean

PUBL_API = "https://dblp.org/search/publ/api"


class DblpProvider:
    name = "dblp"

    def __init__(self, client: Optional[HttpClient] = None):
        # DBLP is strict about rate; keep it slow to avoid 429/503.
        self.http = client or HttpClient(min_interval=1.0)

    def _paper_from(self, hit: dict) -> Paper:
        info = hit.get("info") or {}
        authors_node = (info.get("authors") or {}).get("author")
        authors: list[str] = []
        if isinstance(authors_node, list):
            authors = [a.get("text", a) if isinstance(a, dict) else a for a in authors_node]
        elif isinstance(authors_node, dict):
            authors = [authors_node.get("text", "")]
        year = info.get("year")
        return Paper(
            title=clean(info.get("title")) or "(no title)",
            link=info.get("ee") or info.get("url"),
            source=self.name,
            authors=[a for a in authors if a],
            year=int(year) if str(year).isdigit() else None,
            venue=clean(info.get("venue")),
            doi=info.get("doi"),
            paper_id=info.get("key"),
            extra={"type": info.get("type")} if info.get("type") else {},
        )

    def search(
        self,
        keyword: str,
        max_results: int = 25,
        venue: Optional[str] = None,
        year: Optional[int] = None,
    ) -> list[Paper]:
        query = keyword
        if venue:
            query += f" venue:{venue}:"
        if year:
            query += f" year:{year}:"
        papers: list[Paper] = []
        first = 0
        page = 100
        while len(papers) < max_results:
            resp = self.http.get(
                PUBL_API,
                params={
                    "q": query,
                    "format": "json",
                    "h": min(page, max_results - len(papers)),
                    "f": first,
                },
            )
            resp.raise_for_status()
            hits = ((resp.json().get("result") or {}).get("hits") or {})
            rows = hits.get("hit") or []
            if not rows:
                break
            papers.extend(self._paper_from(h) for h in rows)
            total = int(hits.get("@total", "0"))
            first += len(rows)
            if first >= total or len(rows) < page:
                break
        return papers[:max_results]
