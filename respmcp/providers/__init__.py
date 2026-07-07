"""Scholarly paper search providers.

Each provider returns lists of ``respmcp.providers.base.Paper``.
"""
from .base import HttpClient, Paper
from .arxiv import ArxivProvider
from .semantic_scholar import SemanticScholarProvider
from .openreview import OpenReviewProvider
from .connected_papers import ConnectedPapersProvider
from .openalex import OpenAlexProvider
from .dblp import DblpProvider
from .crossref import CrossrefProvider
from .acl import ACLProvider
from .venues import (
    NeurIPSProvider,
    IJCAIProvider,
    CVFProvider,
    ECCVProvider,
    PMLRProvider,
)
from .conferences import CONFERENCES, ConfSpec, resolve, list_conferences

__all__ = [
    "HttpClient",
    "Paper",
    "ArxivProvider",
    "SemanticScholarProvider",
    "OpenReviewProvider",
    "ConnectedPapersProvider",
    "OpenAlexProvider",
    "DblpProvider",
    "CrossrefProvider",
    "ACLProvider",
    "NeurIPSProvider",
    "IJCAIProvider",
    "CVFProvider",
    "ECCVProvider",
    "PMLRProvider",
    "CONFERENCES",
    "ConfSpec",
    "resolve",
    "list_conferences",
]
