"""arXiv provider — uses the official export API (Atom), no scraping, no key.

Docs: https://info.arxiv.org/help/api/user-manual.html
The official API asks for <= 1 request / 3s; we honor that with a rate limiter.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Optional

from .base import HttpClient, Paper, clean

ATOM = "{http://www.w3.org/2005/Atom}"
API_URL = "http://export.arxiv.org/api/query"


class ArxivProvider:
    name = "arxiv"

    def __init__(self, client: Optional[HttpClient] = None):
        self.http = client or HttpClient(min_interval=3.0)

    def search(
        self,
        keyword: str,
        max_results: int = 25,
        start: int = 0,
        sort_by: str = "relevance",  # relevance | lastUpdatedDate | submittedDate
        sort_order: str = "descending",
    ) -> list[Paper]:
        papers: list[Paper] = []
        page = 100  # arXiv caps effective page size; fetch in chunks
        fetched = 0
        while fetched < max_results:
            want = min(page, max_results - fetched)
            params = {
                "search_query": f"all:{keyword}",
                "start": start + fetched,
                "max_results": want,
                "sortBy": sort_by,
                "sortOrder": sort_order,
            }
            resp = self.http.get(API_URL, params=params)
            resp.raise_for_status()
            batch = self._parse(resp.text)
            if not batch:
                break
            papers.extend(batch)
            fetched += len(batch)
            if len(batch) < want:
                break
        return papers[:max_results]

    def get(self, arxiv_id: str) -> Optional[Paper]:
        """Fetch a single paper by arXiv id (e.g. '1706.03762' or '2401.01234v2')."""
        resp = self.http.get(API_URL, params={"id_list": arxiv_id, "max_results": 1})
        resp.raise_for_status()
        results = self._parse(resp.text)
        return results[0] if results else None

    def _parse(self, xml_text: str) -> list[Paper]:
        root = ET.fromstring(xml_text)
        out: list[Paper] = []
        for entry in root.findall(f"{ATOM}entry"):
            title = clean((entry.findtext(f"{ATOM}title") or ""))
            if not title:
                continue
            abstract = clean(entry.findtext(f"{ATOM}summary"))
            published = entry.findtext(f"{ATOM}published") or ""
            year = int(published[:4]) if published[:4].isdigit() else None
            authors = [
                clean(a.findtext(f"{ATOM}name")) or ""
                for a in entry.findall(f"{ATOM}author")
            ]
            abs_link = None
            pdf_link = None
            for link in entry.findall(f"{ATOM}link"):
                href = link.get("href")
                if link.get("type") == "application/pdf":
                    pdf_link = href
                elif link.get("rel") == "alternate":
                    abs_link = href
            arxiv_id = None
            id_text = entry.findtext(f"{ATOM}id") or ""
            if "/abs/" in id_text:
                arxiv_id = id_text.split("/abs/")[-1]
            doi = entry.findtext(f"{ATOM}{{http://arxiv.org/schemas/atom}}doi")
            out.append(
                Paper(
                    title=title,
                    link=abs_link or id_text,
                    source=self.name,
                    authors=[a for a in authors if a],
                    year=year,
                    abstract=abstract,
                    pdf_url=pdf_link,
                    paper_id=arxiv_id,
                    doi=doi,
                    external_ids={"arxiv": arxiv_id} if arxiv_id else {},
                )
            )
        return out
