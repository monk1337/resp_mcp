"""Conference registry — map a conference name (+ year) to the right
provider, so callers can say ``conference('EMNLP', 2023, 'prompting')`` without
knowing that EMNLP lives in the ACL dump while ICML is a PMLR volume.

Routing methods:
  - "cvf"      : CVF open-access proceedings (CVPR, ICCV, WACV)
  - "eccv"     : ECVA proceedings (ECCV only)
  - "pmlr"     : PMLR volume, resolved by conference+year (ICML, AISTATS, UAI, ...)
  - "acl"      : ACL Anthology, filtered by venue slug + year
  - "ijcai"    : IJCAI proceedings
  - "neurips"  : NeurIPS proceedings
  - "dblp"     : DBLP venue+year filter, with an OpenAlex venue fallback — for
                 venues without an open-proceedings page (AAAI, ICPR, KDD, ...)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ConfSpec:
    canonical: str
    method: str
    # method-specific hints:
    cvf_name: Optional[str] = None       # for "cvf": CVPR/ICCV/WACV
    acl_venue: Optional[str] = None      # for "acl": emnlp/eacl/conll/acl/naacl
    pmlr_conf: Optional[str] = None      # for "pmlr": ICML/AISTATS/UAI/...
    dblp_venue: Optional[str] = None     # for "dblp": DBLP venue tag (e.g. AAAI, ICPR)
    openalex_query: Optional[str] = None  # for "dblp" fallback: OpenAlex source-search string


# Keyed by upper-cased conference name. Aliases point at the same spec.
CONFERENCES: dict[str, ConfSpec] = {
    # -- Vision (CVF open access) --
    "CVPR": ConfSpec("CVPR", "cvf", cvf_name="CVPR"),
    "ICCV": ConfSpec("ICCV", "cvf", cvf_name="ICCV"),
    "WACV": ConfSpec("WACV", "cvf", cvf_name="WACV"),
    # -- Vision (ECVA) --
    "ECCV": ConfSpec("ECCV", "eccv"),
    # -- ML (PMLR) --
    "ICML": ConfSpec("ICML", "pmlr", pmlr_conf="ICML"),
    "AISTATS": ConfSpec("AISTATS", "pmlr", pmlr_conf="AISTATS"),
    "UAI": ConfSpec("UAI", "pmlr", pmlr_conf="UAI"),
    "COLT": ConfSpec("COLT", "pmlr", pmlr_conf="COLT"),
    "ACML": ConfSpec("ACML", "pmlr", pmlr_conf="ACML"),
    "COLLAS": ConfSpec("CoLLAs", "pmlr", pmlr_conf="CoLLAs"),
    # -- NLP (ACL Anthology) --
    "ACL": ConfSpec("ACL", "acl", acl_venue="acl"),
    "EMNLP": ConfSpec("EMNLP", "acl", acl_venue="emnlp"),
    "EACL": ConfSpec("EACL", "acl", acl_venue="eacl"),
    "NAACL": ConfSpec("NAACL", "acl", acl_venue="naacl"),
    "CONLL": ConfSpec("CoNLL", "acl", acl_venue="conll"),
    "COLING": ConfSpec("COLING", "acl", acl_venue="coling"),
    "LREC": ConfSpec("LREC", "acl", acl_venue="lrec"),
    "TACL": ConfSpec("TACL", "acl", acl_venue="tacl"),
    "FINDINGS": ConfSpec("Findings", "acl", acl_venue="findings"),
    # -- Other AI (dedicated scrapers) --
    "IJCAI": ConfSpec("IJCAI", "ijcai"),
    "NEURIPS": ConfSpec("NeurIPS", "neurips"),
    "NIPS": ConfSpec("NeurIPS", "neurips"),
    # -- Venues without a scrapeable open-proceedings page: DBLP venue+year
    #    filter (clean, returns publisher DOIs), OpenAlex source as fallback. --
    "AAAI": ConfSpec("AAAI", "dblp", dblp_venue="AAAI",
                     openalex_query="Proceedings of the AAAI Conference on Artificial Intelligence"),
    "ICPR": ConfSpec("ICPR", "dblp", dblp_venue="ICPR",
                     openalex_query="International Conference on Pattern Recognition"),
    "KDD": ConfSpec("KDD", "dblp", dblp_venue="KDD",
                    openalex_query="Knowledge Discovery and Data Mining"),
    "WWW": ConfSpec("WWW", "dblp", dblp_venue="WWW",
                    openalex_query="The Web Conference"),
    "SIGIR": ConfSpec("SIGIR", "dblp", dblp_venue="SIGIR",
                      openalex_query="Research and Development in Information Retrieval"),
    "ICDM": ConfSpec("ICDM", "dblp", dblp_venue="ICDM",
                     openalex_query="IEEE International Conference on Data Mining"),
}

ALIASES = {
    "CVPR2024": "CVPR",
    "CONLL": "CONLL",
}


def resolve(name: str) -> Optional[ConfSpec]:
    key = name.strip().upper().replace(" ", "").replace("-", "")
    if key in CONFERENCES:
        return CONFERENCES[key]
    if key in ALIASES:
        return CONFERENCES[ALIASES[key]]
    return None


def list_conferences() -> list[dict]:
    seen = set()
    out = []
    for spec in CONFERENCES.values():
        if spec.canonical in seen:
            continue
        seen.add(spec.canonical)
        out.append({"conference": spec.canonical, "method": spec.method})
    return out
