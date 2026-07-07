"""Connected Papers provider — reverse-engineered REST API (no Selenium, no key).

The site's front-end (assets/index-*.js) posts to a REST base it reads from
https://www.connectedpapers.com/rest-addr.json  ->  rest.prod.connectedpapers.com

Two endpoints matter:
  POST /search/<url-encoded-query>/<page>   -> JSON list of matching papers
  POST /graph/<paper_id>                    -> a "CPGR" binary blob:
        bytes 0:4  = magic b'CPGR'
        bytes 4:12 = header (length/flags, unused here)
        bytes 12:  = zlib-compressed JSON of the full related-papers graph

This replaces the old cnnp.py which drove a headless Chrome through the UI.
Treat as unofficial: wrap failures and fall back to S2 recommendations upstream.
"""
from __future__ import annotations

import json
import zlib
from typing import Optional

from .base import HttpClient, Paper, clean

ADDR_URL = "https://www.connectedpapers.com/rest-addr.json"
DEFAULT_REST = "https://rest.prod.connectedpapers.com/"
CPGR_MAGIC = b"CPGR"
CPGR_HEADER_LEN = 12


class ConnectedPapersProvider:
    name = "connected_papers"

    def __init__(self, client: Optional[HttpClient] = None):
        self.http = client or HttpClient(min_interval=0.5)
        self._rest_base: Optional[str] = None

    def _base(self) -> str:
        if self._rest_base:
            return self._rest_base
        try:
            resp = self.http.get(ADDR_URL)
            resp.raise_for_status()
            self._rest_base = resp.json().get("addr", DEFAULT_REST)
        except Exception:
            self._rest_base = DEFAULT_REST
        return self._rest_base

    def search(self, keyword: str, max_results: int = 25) -> list[Paper]:
        """Search Connected Papers' corpus (Semantic Scholar-backed)."""
        from urllib.parse import quote

        papers: list[Paper] = []
        page = 1  # Connected Papers search is 1-indexed; page 0 is always empty.
        while len(papers) < max_results:
            url = f"{self._base()}search/{quote(keyword)}/{page}"
            resp = self.http.post(url, json={})
            if resp.status_code != 200:
                break
            try:
                payload = resp.json()
            except ValueError:
                break
            results = payload.get("results") or []
            if not results:
                break
            for r in results:
                papers.append(self._paper_from_search(r))
            if page >= (payload.get("totalPages") or page):
                break
            page += 1
        return papers[:max_results]

    def related(self, paper_id: str, max_results: int = 50) -> list[Paper]:
        """Build the graph for a paper id and return its related papers.

        paper_id is a Semantic Scholar / Connected Papers 40-char paper hash
        (the ``id`` field returned by :meth:`search`).
        """
        url = f"{self._base()}graph/{paper_id}"
        resp = self.http.post(url, json={})
        resp.raise_for_status()
        graph = self._decode_cpgr(resp.content)
        nodes = graph.get("nodes") or {}
        start_id = graph.get("start_id")
        papers: list[Paper] = []
        for nid, node in nodes.items():
            if nid == start_id:
                continue
            papers.append(self._paper_from_node(nid, node))
        # Order by citation count desc as a sensible default.
        papers.sort(key=lambda p: p.num_citations or 0, reverse=True)
        return papers[:max_results]

    # -- parsing helpers -------------------------------------------------

    @staticmethod
    def _decode_cpgr(blob: bytes) -> dict:
        if blob[:4] != CPGR_MAGIC:
            # Fall back: maybe already raw zlib or JSON.
            try:
                return json.loads(zlib.decompress(blob))
            except Exception:
                return json.loads(blob.decode("utf-8"))
        return json.loads(zlib.decompress(blob[CPGR_HEADER_LEN:]))

    def _paper_from_search(self, r: dict) -> Paper:
        def txt(d):
            return clean(d.get("text")) if isinstance(d, dict) else clean(d)

        authors: list[str] = []
        for grp in r.get("authors") or []:
            for a in grp:
                if a.get("name"):
                    authors.append(a["name"])
        stats = r.get("citationStats") or {}
        yr = txt(r.get("year"))
        return Paper(
            title=txt(r.get("title")) or "(no title)",
            link=f"https://www.connectedpapers.com/main/{r.get('id')}"
            if r.get("id") else None,
            source=self.name,
            authors=authors,
            year=int(yr) if yr and yr.isdigit() else None,
            venue=txt(r.get("venue")),
            abstract=txt(r.get("paperAbstract")),
            num_citations=stats.get("numCitations"),
            paper_id=r.get("id"),
        )

    def _paper_from_node(self, nid: str, node: dict) -> Paper:
        authors = [a.get("name", "") for a in (node.get("authors") or []) if a.get("name")]
        pdfs = [u for u in (node.get("pdfUrls") or []) if u]
        return Paper(
            title=clean(node.get("title")) or "(no title)",
            link=node.get("url") or f"https://www.connectedpapers.com/main/{nid}",
            source=self.name,
            authors=authors,
            year=node.get("year"),
            venue=clean(node.get("venue")),
            abstract=clean(node.get("abstract")),
            doi=node.get("doi") or None,
            pdf_url=pdfs[0] if pdfs else None,
            num_citations=node.get("citations_length"),
            paper_id=node.get("paperId") or nid,
            external_ids=node.get("externalIds") or {},
            extra={"tldr": node.get("tldr")} if node.get("tldr") else {},
        )
