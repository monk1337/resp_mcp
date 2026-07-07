"""Live smoke tests — hit real endpoints. Run with: pytest -q -s tests/test_live.py

These are integration tests (network required). Marked slow; skip in CI with -k.
"""
import pytest
import requests

from respmcp import Resp
from respmcp.providers import Paper


def skip_on_ratelimit(fn):
    """S2/DBLP share IP-based limits; a 429/503 without a key is not a code bug."""
    def wrapper(*a, **k):
        try:
            return fn(*a, **k)
        except requests.HTTPError as e:
            code = getattr(e.response, "status_code", None)
            if code in (429, 503):
                pytest.skip(f"rate-limited ({code}); set an API key to test reliably")
            raise
    wrapper.__name__ = fn.__name__
    return wrapper

resp = Resp()

KW = "multi label text classification"


def _assert_papers(papers, minimum=1):
    assert isinstance(papers, list)
    assert len(papers) >= minimum, f"expected >= {minimum}, got {len(papers)}"
    for p in papers:
        assert isinstance(p, Paper)
        assert p.title and p.title != "(no title)"
        assert p.source


def test_arxiv():
    _assert_papers(resp.arxiv(KW, max_results=5))


@skip_on_ratelimit
def test_semantic_scholar():
    _assert_papers(resp.semantic_scholar(KW, max_results=5))


def test_openreview():
    _assert_papers(resp.openreview("contrastive learning", max_results=5))


def test_openalex():
    _assert_papers(resp.openalex_search(KW, max_results=5))


@skip_on_ratelimit
def test_dblp():
    _assert_papers(resp.dblp_search("transformer attention", max_results=5))


def test_crossref_acm():
    _assert_papers(resp.acm(KW, max_results=5))


def test_connected_papers_search():
    _assert_papers(resp.cp.search(KW, max_results=5))


def test_connected_papers_related():
    hits = resp.cp.search(KW, max_results=1)
    assert hits and hits[0].paper_id
    _assert_papers(resp.cp.related(hits[0].paper_id, max_results=10))


@skip_on_ratelimit
def test_citations():
    _assert_papers(resp.citations("arXiv:1706.03762", max_results=5))


def test_neurips():
    _assert_papers(resp.nips("diffusion", year=2023, max_results=5))


def test_ijcai():
    _assert_papers(resp.ijcai("reinforcement learning", year=2024, max_results=5))


def test_cvf():
    _assert_papers(resp.cvf("diffusion", conference="CVPR", year=2024, max_results=5))


def test_pmlr():
    _assert_papers(resp.pmlr("adversarial", volume="v235", max_results=5))


def test_acl():
    _assert_papers(resp.acl("dependency parsing", max_results=5))


@skip_on_ratelimit
def test_search_all_dedupe():
    papers = resp.search_all(KW, sources=["arxiv", "semantic_scholar"], max_per_source=5)
    _assert_papers(papers)
    titles = ["".join(c for c in p.title.lower() if c.isalnum()) for p in papers]
    assert len(titles) == len(set(titles)), "duplicates not removed"
