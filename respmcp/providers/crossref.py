"""Crossref provider — free metadata API (no key). Good for ACM/publisher DOIs.

This is the practical SERP-free stand-in for the repo's ACM scraper, which is
now blocked by Cloudflare. Filter by publisher/container to target ACM et al.
Docs: https://api.crossref.org/swagger-ui/index.html
"""
from __future__ import annotations

from typing import Optional

from .base import CONTACT, HttpClient, Paper, clean

API = "https://api.crossref.org/works"

# ACM's Crossref member id, handy for ACM-only queries.
ACM_MEMBER = "320"


class CrossrefProvider:
    name = "crossref"

    def __init__(self, client: Optional[HttpClient] = None):
        self.http = client or HttpClient(min_interval=0.2)

    def _paper_from(self, it: dict) -> Paper:
        title = (it.get("title") or ["(no title)"])[0]
        authors = [
            " ".join(x for x in [a.get("given"), a.get("family")] if x)
            for a in (it.get("author") or [])
        ]
        year = None
        dp = ((it.get("published") or it.get("issued") or {}).get("date-parts") or [[None]])
        if dp and dp[0] and dp[0][0]:
            year = dp[0][0]
        container = (it.get("container-title") or [None])[0]
        pdf = None
        for lk in it.get("link") or []:
            if lk.get("content-type") == "application/pdf":
                pdf = lk.get("URL")
                break
        return Paper(
            title=clean(title) or "(no title)",
            link=it.get("URL"),
            source=self.name,
            authors=[a for a in authors if a],
            year=year,
            venue=clean(container),
            doi=it.get("DOI"),
            pdf_url=pdf,
            num_citations=it.get("is-referenced-by-count"),
            paper_id=it.get("DOI"),
            extra={"publisher": it.get("publisher")} if it.get("publisher") else {},
        )

    def search(
        self,
        keyword: str,
        max_results: int = 25,
        member: Optional[str] = None,   # e.g. CrossrefProvider.ACM_MEMBER
        min_year: Optional[int] = None,
    ) -> list[Paper]:
        filters = []
        if member:
            filters.append(f"member:{member}")
        if min_year:
            filters.append(f"from-pub-date:{min_year}-01-01")
        papers: list[Paper] = []
        offset = 0
        page = 100
        while len(papers) < max_results:
            params = {
                "query": keyword,
                "rows": min(page, max_results - len(papers)),
                "offset": offset,
                "mailto": CONTACT,
            }
            if filters:
                params["filter"] = ",".join(filters)
            resp = self.http.get(API, params=params)
            resp.raise_for_status()
            items = (resp.json().get("message") or {}).get("items") or []
            if not items:
                break
            papers.extend(self._paper_from(it) for it in items)
            offset += len(items)
            if len(items) < page:
                break
        return papers[:max_results]

    def acm(self, keyword: str, max_results: int = 25, min_year: Optional[int] = None) -> list[Paper]:
        """ACM Digital Library papers via Crossref (SERP-free, Cloudflare-free)."""
        return self.search(keyword, max_results, member=ACM_MEMBER, min_year=min_year)
