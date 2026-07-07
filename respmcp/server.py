"""resp-mcp MCP server — scholarly paper search tools for any MCP client.

Run:
    python -m respmcp.server            # stdio (for Claude Desktop / Code)
    RESP_MCP_TRANSPORT=http python -m respmcp.server   # streamable HTTP

Every tool returns a list of paper dicts (normalized schema). No API key is
required to get started. Optional env:
    SEMANTIC_SCHOLAR_API_KEY   raise Semantic Scholar rate limits
    RESP_CONTACT_EMAIL         polite-pool contact for OpenAlex/Crossref
    RESP_CACHE_DIR             where the ACL Anthology index is cached
"""
from __future__ import annotations

import os
from typing import Optional

from mcp.server.fastmcp import FastMCP

from .core import Resp
from .providers.base import Paper

mcp = FastMCP("resp")
_resp = Resp(semantic_scholar_api_key=os.environ.get("SEMANTIC_SCHOLAR_API_KEY"))


def _out(papers: list[Paper]) -> list[dict]:
    return [p.to_dict() for p in papers]


# -- keyword search per source -------------------------------------------

@mcp.tool()
def search_arxiv(keyword: str, max_results: int = 25) -> list[dict]:
    """Search arXiv via its official export API (no key). Returns papers with
    titles, authors, abstracts, PDF links, and arXiv ids."""
    return _out(_resp.arxiv(keyword, max_results))


@mcp.tool()
def search_semantic_scholar(
    keyword: str, max_results: int = 25,
    min_year: Optional[int] = None, max_year: Optional[int] = None,
) -> list[dict]:
    """Search Semantic Scholar's Graph API (free; set SEMANTIC_SCHOLAR_API_KEY
    for higher limits). Covers most CS/ML venues with citation counts."""
    return _out(_resp.semantic_scholar(keyword, max_results, min_year=min_year, max_year=max_year))


@mcp.tool()
def search_openreview(keyword: str, max_results: int = 25) -> list[dict]:
    """Search OpenReview (ICLR, NeurIPS tracks, etc.) via its official v2 API."""
    return _out(_resp.openreview(keyword, max_results))


@mcp.tool()
def search_openalex(
    keyword: str, max_results: int = 25,
    min_year: Optional[int] = None, max_year: Optional[int] = None,
    host: Optional[str] = None, open_access: Optional[bool] = None,
) -> list[dict]:
    """Search OpenAlex (free, cross-venue). Optional filters: year range, host
    domain (e.g. 'aclanthology.org'), and open-access only."""
    return _out(_resp.openalex_search(
        keyword, max_results, min_year=min_year, max_year=max_year,
        host=host, open_access=open_access))


@mcp.tool()
def search_dblp(keyword: str, max_results: int = 25, venue: Optional[str] = None) -> list[dict]:
    """Search DBLP (free) — excellent CS-venue metadata with publisher links.
    Optional venue filter (e.g. 'ACL', 'NeurIPS')."""
    return _out(_resp.dblp_search(keyword, max_results, venue=venue))


@mcp.tool()
def search_acl(keyword: str, max_results: int = 25) -> list[dict]:
    """Search the ACL Anthology via its cached BibTeX dump (complete offline
    index; first call downloads ~13 MB). Returns aclanthology.org links."""
    return _out(_resp.acl(keyword, max_results))


@mcp.tool()
def search_acm(keyword: str, max_results: int = 25, min_year: Optional[int] = None) -> list[dict]:
    """Search ACM Digital Library papers via Crossref. Returns DOIs and
    publisher links."""
    return _out(_resp.acm(keyword, max_results, min_year=min_year))


@mcp.tool()
def search_connected_papers(keyword: str, max_results: int = 25) -> list[dict]:
    """Search the Connected Papers corpus by keyword."""
    return _out(_resp.cp.search(keyword, max_results))


# -- venue proceedings (year/volume scoped) ------------------------------

@mcp.tool()
def search_neurips(keyword: str, year: int, max_results: int = 50) -> list[dict]:
    """Search a NeurIPS proceedings year (e.g. 2023) by scraping papers.nips.cc."""
    return _out(_resp.nips(keyword, year, max_results))


@mcp.tool()
def search_ijcai(keyword: str, year: int, max_results: int = 50) -> list[dict]:
    """Search an IJCAI proceedings year (e.g. 2024) by scraping ijcai.org."""
    return _out(_resp.ijcai(keyword, year, max_results))


@mcp.tool()
def search_cvf(keyword: str, conference: str = "CVPR", year: int = 2024, max_results: int = 50) -> list[dict]:
    """Search CVF open-access proceedings (conference: CVPR/ICCV/WACV, given year)."""
    return _out(_resp.cvf(keyword, conference, year, max_results))


@mcp.tool()
def search_pmlr(keyword: str, volume: str, max_results: int = 50) -> list[dict]:
    """Search a PMLR volume (e.g. 'v235' for ICML 2024) via proceedings.mlr.press."""
    return _out(_resp.pmlr(keyword, volume, max_results))


@mcp.tool()
def search_eccv(keyword: str, year: Optional[int] = None, max_results: int = 50) -> list[dict]:
    """Search ECCV proceedings via the ECVA open-access site (ecva.net). Omit
    year to search all ECCV years at once."""
    return _out(_resp.eccv(keyword, year=year, max_results=max_results))


@mcp.tool()
def search_aaai(keyword: str, year: Optional[int] = None, max_results: int = 50) -> list[dict]:
    """Search AAAI proceedings via DBLP venue+year filter, with an OpenAlex
    venue fallback."""
    return _out(_resp.aaai(keyword, year=year, max_results=max_results))


@mcp.tool()
def list_conferences() -> list[dict]:
    """List the conferences the unified search_conference tool knows how to
    route, with the source each uses."""
    return _resp.list_conferences()


@mcp.tool()
def search_conference(
    conference: str, keyword: str, year: Optional[int] = None, max_results: int = 50
) -> list[dict]:
    """Search any known conference, auto-routing to the right source.

    Supported (see list_conferences): CVPR, ICCV, WACV, ECCV, ICML, AISTATS, UAI,
    COLT, ACML, CoLLAs, ACL, EMNLP, EACL, NAACL, CoNLL, COLING, LREC, TACL,
    IJCAI, NeurIPS, AAAI, ICPR, KDD, WWW, SIGIR, ICDM.

    Most conferences need a `year`; ACL-family and ECCV can search across years.
    Examples: search_conference('ICML','diffusion',2024);
    search_conference('EMNLP','prompting',2023)."""
    return _out(_resp.conference(conference, keyword, year=year, max_results=max_results))


# -- citation graph & related --------------------------------------------

@mcp.tool()
def get_citations(paper_id: str, max_results: int = 50) -> list[dict]:
    """Papers that cite the given paper. paper_id may be a Semantic Scholar id,
    'arXiv:1706.03762', 'DOI:10.xxxx', or 'CorpusId:...'."""
    return _out(_resp.citations(paper_id, max_results))


@mcp.tool()
def get_references(paper_id: str, max_results: int = 50) -> list[dict]:
    """Papers referenced by the given paper (Semantic Scholar Graph API)."""
    return _out(_resp.references(paper_id, max_results))


@mcp.tool()
def get_related_papers(query_or_id: str, max_results: int = 40) -> list[dict]:
    """Related papers for a title/query or paper id, using the Connected Papers
    graph with a Semantic Scholar recommendations fallback."""
    return _out(_resp.related_papers(query_or_id, max_results))


# -- unified --------------------------------------------------------------

@mcp.tool()
def search_all(keyword: str, sources: Optional[list[str]] = None, max_per_source: int = 10) -> list[dict]:
    """Search several sources at once and merge/de-duplicate. Default sources:
    arxiv, semantic_scholar, openreview, openalex. Other options: dblp, acl,
    acm, connected_papers."""
    return _out(_resp.search_all(keyword, sources=sources, max_per_source=max_per_source))


def main() -> None:
    transport = os.environ.get("RESP_MCP_TRANSPORT", "stdio")
    if transport == "http":
        mcp.run(transport="streamable-http")
    else:
        mcp.run()


if __name__ == "__main__":
    main()
