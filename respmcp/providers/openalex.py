"""OpenAlex provider — free scholarly graph, no key. Cross-venue search + filters.

General cross-venue search: filter by host, venue,
year, open-access, and traverse citations. Add a mailto for the polite pool.
Docs: https://docs.openalex.org/
"""
from __future__ import annotations

from typing import Optional

from .base import CONTACT, HttpClient, Paper, clean


API = "https://api.openalex.org/works"


def _reconstruct_abstract(inv: Optional[dict]) -> Optional[str]:
    """OpenAlex stores abstracts as an inverted index {word: [positions]}."""
    if not inv:
        return None
    positions: list[tuple[int, str]] = []
    for word, idxs in inv.items():
        for i in idxs:
            positions.append((i, word))
    positions.sort()
    return " ".join(w for _, w in positions) or None


class OpenAlexProvider:
    name = "openalex"

    def __init__(self, client: Optional[HttpClient] = None):
        self.http = client or HttpClient(min_interval=0.11)  # polite pool ~10/s

    def _paper_from(self, w: dict) -> Paper:
        pl = w.get("primary_location") or {}
        src = pl.get("source") or {}
        oa = w.get("open_access") or {}
        ids = w.get("ids") or {}
        authors = [
            (a.get("author") or {}).get("display_name", "")
            for a in (w.get("authorships") or [])
        ]
        doi = w.get("doi")
        if doi and doi.startswith("https://doi.org/"):
            doi = doi[len("https://doi.org/"):]
        return Paper(
            title=clean(w.get("title")) or "(no title)",
            link=pl.get("landing_page_url") or w.get("id"),
            source=self.name,
            authors=[a for a in authors if a],
            year=w.get("publication_year"),
            venue=clean(src.get("display_name")),
            abstract=_reconstruct_abstract(w.get("abstract_inverted_index")),
            doi=doi,
            pdf_url=oa.get("oa_url"),
            num_citations=w.get("cited_by_count"),
            paper_id=w.get("id"),
            external_ids={k: v for k, v in ids.items() if v},
        )

    def search(
        self,
        keyword: str,
        max_results: int = 25,
        min_year: Optional[int] = None,
        max_year: Optional[int] = None,
        host: Optional[str] = None,       # e.g. "aclanthology.org"
        venue: Optional[str] = None,      # OpenAlex source id or display name search
        open_access: Optional[bool] = None,
    ) -> list[Paper]:
        filters = []
        if min_year:
            filters.append(f"from_publication_date:{min_year}-01-01")
        if max_year:
            filters.append(f"to_publication_date:{max_year}-12-31")
        if host:
            filters.append(f"primary_location.source.host_organization_lineage_names.search:{host}")
        if open_access is not None:
            filters.append(f"is_oa:{str(open_access).lower()}")

        papers: list[Paper] = []
        cursor = "*"
        while len(papers) < max_results:
            params = {
                "search": keyword,
                "per-page": min(200, max_results - len(papers)),
                "cursor": cursor,
                "mailto": CONTACT,
            }
            if filters:
                params["filter"] = ",".join(filters)
            resp = self.http.get(API, params=params)
            resp.raise_for_status()
            data = resp.json()
            batch = data.get("results") or []
            papers.extend(self._paper_from(w) for w in batch)
            cursor = (data.get("meta") or {}).get("next_cursor")
            if not cursor or not batch:
                break
        # Host filter above is best-effort; also post-filter by landing URL.
        if host:
            papers = [p for p in papers if p.link and host in p.link] or papers
        return papers[:max_results]

    def find_source_id(self, name: str) -> Optional[str]:
        """Look up an OpenAlex source (venue) id by name, e.g. 'AAAI'."""
        resp = self.http.get(
            "https://api.openalex.org/sources",
            params={"search": name, "per-page": 1, "mailto": CONTACT},
        )
        resp.raise_for_status()
        results = resp.json().get("results") or []
        return results[0]["id"].split("/")[-1] if results else None

    def search_venue(
        self,
        keyword: str,
        source_id: str,
        year: Optional[int] = None,
        max_results: int = 50,
    ) -> list[Paper]:
        """Search within a specific venue (OpenAlex source id) and optional year.

        This is the route for conferences without open proceedings
        pages we can scrape (e.g. AAAI, ICPR).
        """
        filters = [f"primary_location.source.id:{source_id}"]
        if year:
            filters.append(f"publication_year:{year}")
        papers: list[Paper] = []
        cursor = "*"
        while len(papers) < max_results:
            resp = self.http.get(
                API,
                params={
                    "search": keyword,
                    "filter": ",".join(filters),
                    "per-page": min(200, max_results - len(papers)),
                    "cursor": cursor,
                    "mailto": CONTACT,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            batch = data.get("results") or []
            papers.extend(self._paper_from(w) for w in batch)
            cursor = (data.get("meta") or {}).get("next_cursor")
            if not cursor or not batch:
                break
        return papers[:max_results]

    def get(self, work_id: str) -> Optional[Paper]:
        """work_id: OpenAlex id (W...), 'doi:10...', 'arxiv:...' etc."""
        resp = self.http.get(f"{API}/{work_id}", params={"mailto": CONTACT})
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return self._paper_from(resp.json())

    def citations(self, work_id: str, max_results: int = 50) -> list[Paper]:
        """Papers that cite work_id."""
        oid = work_id.split("/")[-1]
        papers: list[Paper] = []
        cursor = "*"
        while len(papers) < max_results:
            resp = self.http.get(
                API,
                params={
                    "filter": f"cites:{oid}",
                    "per-page": min(200, max_results - len(papers)),
                    "cursor": cursor,
                    "mailto": CONTACT,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            batch = data.get("results") or []
            papers.extend(self._paper_from(w) for w in batch)
            cursor = (data.get("meta") or {}).get("next_cursor")
            if not cursor or not batch:
                break
        return papers[:max_results]
