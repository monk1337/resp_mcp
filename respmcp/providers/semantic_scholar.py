"""Semantic Scholar provider — official Graph API (free; optional API key).

Replaces both the repo's broken internal ``/api/1/search`` scrape and the
citation lookups. Endpoints used:
  - /graph/v1/paper/search        -> keyword search
  - /graph/v1/paper/{id}          -> single paper
  - /graph/v1/paper/{id}/citations
  - /graph/v1/paper/{id}/references
  - /recommendations/v1/papers/forpaper/{id}

Set SEMANTIC_SCHOLAR_API_KEY to raise rate limits and avoid shared-IP 429s.
Docs: https://api.semanticscholar.org/api-docs/
"""
from __future__ import annotations

import os
from typing import Optional

from .base import HttpClient, Paper, clean

GRAPH = "https://api.semanticscholar.org/graph/v1"
REC = "https://api.semanticscholar.org/recommendations/v1"

PAPER_FIELDS = (
    "title,abstract,year,venue,externalIds,url,openAccessPdf,"
    "citationCount,authors"
)


class SemanticScholarProvider:
    name = "semantic_scholar"

    def __init__(self, client: Optional[HttpClient] = None, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("SEMANTIC_SCHOLAR_API_KEY")
        # Without a key S2 allows ~1 req/sec (shared, best-effort); be gentle.
        self.http = client or HttpClient(min_interval=1.1 if not self.api_key else 0.05)

    def _headers(self) -> dict:
        return {"x-api-key": self.api_key} if self.api_key else {}

    def _paper_from(self, d: dict) -> Paper:
        ext = d.get("externalIds") or {}
        pdf = (d.get("openAccessPdf") or {}).get("url")
        return Paper(
            title=clean(d.get("title")) or "(no title)",
            link=d.get("url"),
            source=self.name,
            authors=[a.get("name", "") for a in (d.get("authors") or []) if a.get("name")],
            year=d.get("year"),
            venue=clean(d.get("venue")),
            abstract=clean(d.get("abstract")),
            doi=ext.get("DOI"),
            pdf_url=pdf,
            num_citations=d.get("citationCount"),
            paper_id=d.get("paperId"),
            external_ids=ext,
        )

    def search(
        self,
        keyword: str,
        max_results: int = 25,
        min_year: Optional[int] = None,
        max_year: Optional[int] = None,
        fields_of_study: Optional[list[str]] = None,
    ) -> list[Paper]:
        papers: list[Paper] = []
        offset = 0
        page = 100
        while len(papers) < max_results:
            params = {
                "query": keyword,
                "offset": offset,
                "limit": min(page, max_results - len(papers)),
                "fields": PAPER_FIELDS,
            }
            if min_year or max_year:
                lo = min_year or 1900
                hi = max_year or 2100
                params["year"] = f"{lo}-{hi}"
            if fields_of_study:
                params["fieldsOfStudy"] = ",".join(fields_of_study)
            resp = self.http.get(f"{GRAPH}/paper/search", params=params, headers=self._headers())
            resp.raise_for_status()
            data = resp.json()
            batch = data.get("data") or []
            papers.extend(self._paper_from(d) for d in batch)
            nxt = data.get("next")
            if nxt is None or not batch:
                break
            offset = nxt
        return papers[:max_results]

    def get(self, paper_id: str) -> Optional[Paper]:
        """paper_id may be S2 id, 'arXiv:1706.03762', 'DOI:...', 'CorpusId:...'."""
        resp = self.http.get(
            f"{GRAPH}/paper/{paper_id}",
            params={"fields": PAPER_FIELDS},
            headers=self._headers(),
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return self._paper_from(resp.json())

    def citations(self, paper_id: str, max_results: int = 50) -> list[Paper]:
        return self._edge(paper_id, "citations", "citingPaper", max_results)

    def references(self, paper_id: str, max_results: int = 50) -> list[Paper]:
        return self._edge(paper_id, "references", "citedPaper", max_results)

    def _edge(self, paper_id: str, edge: str, key: str, max_results: int) -> list[Paper]:
        papers: list[Paper] = []
        offset = 0
        while len(papers) < max_results:
            resp = self.http.get(
                f"{GRAPH}/paper/{paper_id}/{edge}",
                params={
                    "offset": offset,
                    "limit": min(1000, max_results - len(papers)),
                    "fields": PAPER_FIELDS,
                },
                headers=self._headers(),
            )
            if resp.status_code == 404:
                break
            resp.raise_for_status()
            data = resp.json()
            batch = data.get("data") or []
            for row in batch:
                sub = row.get(key)
                if sub:
                    papers.append(self._paper_from(sub))
            nxt = data.get("next")
            if nxt is None or not batch:
                break
            offset = nxt
        return papers[:max_results]

    def recommendations(self, paper_id: str, max_results: int = 20) -> list[Paper]:
        resp = self.http.get(
            f"{REC}/papers/forpaper/{paper_id}",
            params={"limit": max_results, "fields": PAPER_FIELDS},
            headers=self._headers(),
        )
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        rec = resp.json().get("recommendedPapers") or []
        return [self._paper_from(d) for d in rec]
