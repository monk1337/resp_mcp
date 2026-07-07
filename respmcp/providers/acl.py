"""ACL Anthology provider — no SerpApi, no search API needed.

The Anthology has no keyword-search endpoint, but it publishes a complete
BibTeX dump (anthology.bib.gz). We download it once, cache it on disk, parse it
with a fast regex, and search titles locally. This yields real aclanthology.org
links and complete coverage — a faithful SERP-free replacement for the repo's
``site:aclanthology.org`` queries.

First call downloads ~13 MB (cached under RESP_CACHE_DIR or ~/.cache/resp-mcp);
subsequent calls are instant until the cache TTL expires.
"""
from __future__ import annotations

import gzip
import os
import re
import time
from pathlib import Path
from typing import Optional

from .base import BROWSER_UA, HttpClient, Paper, clean

DUMP_URL = "https://aclanthology.org/anthology.bib.gz"
CACHE_TTL = 7 * 24 * 3600  # refresh weekly

_FIELD_RE = {
    name: re.compile(name + r"\s*=\s*[\"{](.+?)[\"}],?\s*\n", re.S)
    for name in ("title", "author", "url", "year", "booktitle", "abstract", "doi")
}


def _cache_dir() -> Path:
    base = os.environ.get("RESP_CACHE_DIR") or os.path.expanduser("~/.cache/resp-mcp")
    p = Path(base)
    p.mkdir(parents=True, exist_ok=True)
    return p


class ACLProvider:
    name = "acl"

    def __init__(self, client: Optional[HttpClient] = None):
        self.http = client or HttpClient(user_agent=BROWSER_UA, timeout=120)
        self._entries: Optional[list[dict]] = None

    # -- dump handling ---------------------------------------------------

    def _dump_path(self) -> Path:
        return _cache_dir() / "anthology.bib"

    def _ensure_dump(self) -> Path:
        path = self._dump_path()
        fresh = path.exists() and (time.time() - path.stat().st_mtime) < CACHE_TTL
        if not fresh:
            resp = self.http.get(DUMP_URL)
            resp.raise_for_status()
            text = gzip.decompress(resp.content).decode("utf-8", "replace")
            path.write_text(text, encoding="utf-8")
        return path

    def _load(self) -> list[dict]:
        if self._entries is not None:
            return self._entries
        raw = self._ensure_dump().read_text(encoding="utf-8", errors="replace")
        entries: list[dict] = []
        for block in raw.split("\n@"):
            title_m = _FIELD_RE["title"].search(block)
            if not title_m:
                continue
            rec = {}
            for name, rx in _FIELD_RE.items():
                m = rx.search(block)
                if m:
                    rec[name] = re.sub(r"\s+", " ", m.group(1)).strip()
            entries.append(rec)
        self._entries = entries
        return entries

    # -- search ----------------------------------------------------------

    def _paper_from(self, rec: dict) -> Paper:
        authors = []
        if rec.get("author"):
            # BibTeX authors are "Last, First and Last, First"
            for a in rec["author"].split(" and "):
                a = a.strip()
                if "," in a:
                    last, first = a.split(",", 1)
                    a = f"{first.strip()} {last.strip()}"
                if a:
                    authors.append(a)
        year = rec.get("year")
        url = rec.get("url")
        return Paper(
            title=clean(rec.get("title")) or "(no title)",
            link=url,
            source=self.name,
            authors=authors,
            year=int(year) if year and year.isdigit() else None,
            venue=clean(rec.get("booktitle")),
            abstract=clean(rec.get("abstract")),
            doi=rec.get("doi"),
            pdf_url=(url.rstrip("/") + ".pdf") if url and "aclanthology.org" in url else None,
        )

    @staticmethod
    def _venue_year(url: str) -> tuple[Optional[str], Optional[int]]:
        """Parse the anthology id in the URL, e.g.
        https://aclanthology.org/2023.conll-1.1/  -> ('conll', 2023)
        Modern ids are 'YYYY.<venue>-...'; legacy ids like 'P19-...' are skipped.
        """
        if not url:
            return None, None
        m = re.search(r"aclanthology\.org/(\d{4})\.([a-z-]+)", url)
        if m:
            return m.group(2), int(m.group(1))
        return None, None

    def search(
        self,
        keyword: str,
        max_results: int = 25,
        venue: Optional[str] = None,   # e.g. 'emnlp', 'eacl', 'conll', 'acl', 'naacl'
        year: Optional[int] = None,
        include_findings: bool = True,
    ) -> list[Paper]:
        toks = [t for t in re.split(r"\s+", keyword.lower()) if t]
        vfilter = venue.lower() if venue else None
        out: list[Paper] = []
        for rec in self._load():
            title = rec.get("title", "").lower()
            if not all(t in title for t in toks):
                continue
            if vfilter or year:
                v, y = self._venue_year(rec.get("url", ""))
                if year and y != year:
                    continue
                if vfilter:
                    # 'emnlp' matches both '2023.emnlp' and '2023.findings-emnlp'
                    if not v or vfilter not in v:
                        continue
                    if not include_findings and v.startswith("findings"):
                        continue
            out.append(self._paper_from(rec))
            if len(out) >= max_results:
                break
        return out
