"""Live tests for the unified conference router across the requested venues."""
import functools

import pytest
import requests

from respmcp import Resp
from respmcp.providers import Paper

resp = Resp()


def _ok(papers, minimum=1):
    assert isinstance(papers, list)
    assert len(papers) >= minimum, f"expected >= {minimum}, got {len(papers)}"
    for p in papers:
        assert isinstance(p, Paper) and p.title and p.title != "(no title)"


def skip_rl(fn):
    @functools.wraps(fn)
    def w(*a, **k):
        try:
            return fn(*a, **k)
        except requests.HTTPError as e:
            if getattr(e.response, "status_code", None) in (429, 503):
                pytest.skip("rate-limited")
            raise
    return w


# The exact list the user asked for, plus the ones already covered.
CASES = [
    ("ICML", "deep learning", 2024),
    ("EACL", "translation", 2024),
    ("CVPR", "diffusion", 2024),
    ("AAAI", "reinforcement learning", 2023),
    ("EMNLP", "prompting", 2023),
    ("ICCV", "segmentation", 2023),
    ("ECCV", "detection", 2024),
    ("ICPR", "classification", 2022),
    ("CoNLL", "parsing", 2023),
    ("IJCAI", "learning", 2024),
]


@pytest.mark.parametrize("conf,kw,year", CASES)
@skip_rl
def test_conference(conf, kw, year):
    _ok(resp.conference(conf, kw, year=year, max_results=5))


def test_list_conferences():
    confs = {c["conference"] for c in resp.list_conferences()}
    for required in ("ICML", "EACL", "CVPR", "AAAI", "EMNLP", "ICCV", "ECCV", "ICPR", "CoNLL", "IJCAI"):
        assert required in confs, f"{required} missing from registry"


def test_pmlr_volume_resolution():
    assert resp.pmlr_p.resolve_volume("ICML", 2024) == "v235"
    assert resp.pmlr_p.resolve_volume("ICML", 2023) == "v202"


def test_acl_venue_filter():
    # EMNLP-only results should all have emnlp in their anthology URL.
    papers = resp.conference("EMNLP", "machine translation", year=2023, max_results=10)
    _ok(papers)
    assert all("emnlp" in (p.link or "").lower() for p in papers)
    assert all(p.year == 2023 for p in papers)
