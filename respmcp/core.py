"""Resp — the unified search facade.

A drop-in-spirit replacement for the original ``resp.Resp`` class, but every
method is powered by a public scholarly API or proceedings source.
Providers are lazily instantiated so importing this is cheap.
"""
from __future__ import annotations

from typing import Optional

from .providers import (
    ACLProvider,
    ArxivProvider,
    ConnectedPapersProvider,
    CrossrefProvider,
    CVFProvider,
    DblpProvider,
    ECCVProvider,
    IJCAIProvider,
    NeurIPSProvider,
    OpenAlexProvider,
    OpenReviewProvider,
    PMLRProvider,
    Paper,
    SemanticScholarProvider,
)
from .providers.conferences import list_conferences as _list_conferences, resolve as _resolve_conf


class Resp:
    """Scholarly paper search across many sources."""

    def __init__(self, semantic_scholar_api_key: Optional[str] = None):
        self._s2_key = semantic_scholar_api_key
        self._cache: dict = {}
        self._source_ids: dict[str, Optional[str]] = {}

    # lazy singletons -----------------------------------------------------
    def _p(self, key, factory):
        if key not in self._cache:
            self._cache[key] = factory()
        return self._cache[key]

    @property
    def arxiv_p(self) -> ArxivProvider:
        return self._p("arxiv", ArxivProvider)

    @property
    def s2(self) -> SemanticScholarProvider:
        return self._p("s2", lambda: SemanticScholarProvider(api_key=self._s2_key))

    @property
    def openreview_p(self) -> OpenReviewProvider:
        return self._p("openreview", OpenReviewProvider)

    @property
    def cp(self) -> ConnectedPapersProvider:
        return self._p("cp", ConnectedPapersProvider)

    @property
    def openalex(self) -> OpenAlexProvider:
        return self._p("openalex", OpenAlexProvider)

    @property
    def dblp(self) -> DblpProvider:
        return self._p("dblp", DblpProvider)

    @property
    def crossref(self) -> CrossrefProvider:
        return self._p("crossref", CrossrefProvider)

    @property
    def acl_p(self) -> ACLProvider:
        return self._p("acl", ACLProvider)

    @property
    def neurips_p(self) -> NeurIPSProvider:
        return self._p("neurips", NeurIPSProvider)

    @property
    def ijcai_p(self) -> IJCAIProvider:
        return self._p("ijcai", IJCAIProvider)

    @property
    def cvf_p(self) -> CVFProvider:
        return self._p("cvf", CVFProvider)

    @property
    def eccv_p(self) -> ECCVProvider:
        return self._p("eccv", ECCVProvider)

    @property
    def pmlr_p(self) -> PMLRProvider:
        return self._p("pmlr", PMLRProvider)

    # -- source-specific search (mirrors original Resp method names) -----

    def arxiv(self, keyword: str, max_results: int = 25, **kw) -> list[Paper]:
        return self.arxiv_p.search(keyword, max_results=max_results, **kw)

    def semantic_scholar(self, keyword: str, max_results: int = 25, **kw) -> list[Paper]:
        return self.s2.search(keyword, max_results=max_results, **kw)

    def openreview(self, keyword: str, max_results: int = 25) -> list[Paper]:
        return self.openreview_p.search(keyword, max_results=max_results)

    def acl(self, keyword: str, max_results: int = 25) -> list[Paper]:
        return self.acl_p.search(keyword, max_results=max_results)

    def acm(self, keyword: str, max_results: int = 25, min_year: Optional[int] = None) -> list[Paper]:
        # ACM via Crossref.
        return self.crossref.acm(keyword, max_results=max_results, min_year=min_year)

    def nips(self, keyword: str, year: int, max_results: int = 50) -> list[Paper]:
        return self.neurips_p.search(keyword, year=year, max_results=max_results)

    def ijcai(self, keyword: str, year: int, max_results: int = 50) -> list[Paper]:
        return self.ijcai_p.search(keyword, year=year, max_results=max_results)

    def cvf(self, keyword: str, conference: str = "CVPR", year: int = 2024, max_results: int = 50) -> list[Paper]:
        return self.cvf_p.search(keyword, conference=conference, year=year, max_results=max_results)

    def pmlr(self, keyword: str, volume: str, max_results: int = 50) -> list[Paper]:
        return self.pmlr_p.search(keyword, volume=volume, max_results=max_results)

    def eccv(self, keyword: str, year: Optional[int] = None, max_results: int = 50) -> list[Paper]:
        return self.eccv_p.search(keyword, year=year, max_results=max_results)

    def aaai(self, keyword: str, year: Optional[int] = None, max_results: int = 50) -> list[Paper]:
        return self.conference("AAAI", keyword, year=year, max_results=max_results)

    # -- unified conference dispatch -------------------------------------

    def list_conferences(self) -> list[dict]:
        return _list_conferences()

    def _openalex_source_id(self, query: str) -> Optional[str]:
        if query not in self._source_ids:
            try:
                self._source_ids[query] = self.openalex.find_source_id(query)
            except Exception:
                self._source_ids[query] = None
        return self._source_ids[query]

    def conference(
        self,
        conference: str,
        keyword: str,
        year: Optional[int] = None,
        max_results: int = 50,
    ) -> list[Paper]:
        """Search a named conference, routing to the right provider.

        Examples:
            conference("ICML", "diffusion", 2024)
            conference("EMNLP", "prompting", 2023)
            conference("CVPR", "nerf", 2024)
            conference("AAAI", "planning", 2023)
            conference("ECCV", "segmentation", 2024)
        """
        spec = _resolve_conf(conference)
        if spec is None:
            raise ValueError(
                f"Unknown conference '{conference}'. "
                f"Known: {[c['conference'] for c in self.list_conferences()]}"
            )
        m = spec.method
        if m == "cvf":
            if year is None:
                raise ValueError(f"{spec.canonical} requires a year")
            return self.cvf_p.search(keyword, conference=spec.cvf_name, year=year, max_results=max_results)
        if m == "eccv":
            return self.eccv_p.search(keyword, year=year, max_results=max_results)
        if m == "pmlr":
            if year is None:
                raise ValueError(f"{spec.canonical} requires a year")
            return self.pmlr_p.search_conference(keyword, conference=spec.pmlr_conf, year=year, max_results=max_results)
        if m == "acl":
            return self.acl_p.search(keyword, max_results=max_results, venue=spec.acl_venue, year=year)
        if m == "ijcai":
            if year is None:
                raise ValueError("IJCAI requires a year")
            return self.ijcai_p.search(keyword, year=year, max_results=max_results)
        if m == "neurips":
            if year is None:
                raise ValueError("NeurIPS requires a year")
            return self.neurips_p.search(keyword, year=year, max_results=max_results)
        if m == "dblp":
            # Primary: DBLP venue+year filter (clean, publisher DOIs).
            try:
                papers = self.dblp.search(
                    keyword, max_results=max_results, venue=spec.dblp_venue, year=year
                )
            except Exception:
                papers = []
            if papers:
                return papers
            # Fallback: OpenAlex venue (source id) filter, for editions DBLP
            # rate-limited or missed.
            if spec.openalex_query:
                source_id = self._openalex_source_id(spec.openalex_query)
                if source_id:
                    return self.openalex.search_venue(keyword, source_id, year=year, max_results=max_results)
            return papers
        if m == "openalex":
            source_id = self._openalex_source_id(spec.openalex_query)
            if not source_id:
                return self.openalex.search(keyword, max_results=max_results, min_year=year, max_year=year)
            return self.openalex.search_venue(keyword, source_id, year=year, max_results=max_results)
        raise ValueError(f"Unhandled method {m}")

    def dblp_search(self, keyword: str, max_results: int = 25, venue: Optional[str] = None) -> list[Paper]:
        return self.dblp.search(keyword, max_results=max_results, venue=venue)

    def openalex_search(self, keyword: str, max_results: int = 25, **kw) -> list[Paper]:
        return self.openalex.search(keyword, max_results=max_results, **kw)

    # -- citation graph / related ----------------------------------------

    def citations(self, paper_id: str, max_results: int = 50) -> list[Paper]:
        """Papers citing paper_id (S2 ids/DOI/'arXiv:...')."""
        return self.s2.citations(paper_id, max_results=max_results)

    def references(self, paper_id: str, max_results: int = 50) -> list[Paper]:
        return self.s2.references(paper_id, max_results=max_results)

    def related_papers(self, query_or_id: str, max_results: int = 40) -> list[Paper]:
        """Related papers. Resolves a query to a paper, then uses Connected
        Papers' graph, falling back to S2 recommendations.
        """
        paper_id = query_or_id
        # If it looks like free text, resolve to a paper id via CP search first.
        if " " in query_or_id or len(query_or_id) < 20:
            hits = self.cp.search(query_or_id, max_results=1)
            if hits and hits[0].paper_id:
                paper_id = hits[0].paper_id
        try:
            rel = self.cp.related(paper_id, max_results=max_results)
            if rel:
                return rel
        except Exception:
            pass
        # Fallback: Semantic Scholar recommendations.
        return self.s2.recommendations(paper_id, max_results=max_results)

    # -- unified multi-source search -------------------------------------

    def search_all(
        self,
        keyword: str,
        sources: Optional[list[str]] = None,
        max_per_source: int = 10,
    ) -> list[Paper]:
        """Search several sources and merge, de-duplicating by title/DOI."""
        sources = sources or ["arxiv", "semantic_scholar", "openreview", "openalex"]
        dispatch = {
            "arxiv": lambda: self.arxiv(keyword, max_per_source),
            "semantic_scholar": lambda: self.semantic_scholar(keyword, max_per_source),
            "openreview": lambda: self.openreview(keyword, max_per_source),
            "openalex": lambda: self.openalex_search(keyword, max_per_source),
            "dblp": lambda: self.dblp_search(keyword, max_per_source),
            "acl": lambda: self.acl(keyword, max_per_source),
            "acm": lambda: self.acm(keyword, max_per_source),
            "connected_papers": lambda: self.cp.search(keyword, max_per_source),
        }
        merged: list[Paper] = []
        for src in sources:
            fn = dispatch.get(src)
            if not fn:
                continue
            try:
                merged.extend(fn())
            except Exception:
                continue
        return self._dedupe(merged)

    @staticmethod
    def _dedupe(papers: list[Paper]) -> list[Paper]:
        seen_title: set[str] = set()
        seen_doi: set[str] = set()
        out: list[Paper] = []
        for p in papers:
            tkey = "".join(ch for ch in p.title.lower() if ch.isalnum())
            dkey = (p.doi or "").lower()
            if tkey in seen_title or (dkey and dkey in seen_doi):
                continue
            seen_title.add(tkey)
            if dkey:
                seen_doi.add(dkey)
            out.append(p)
        return out
