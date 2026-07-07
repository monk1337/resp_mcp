"""Direct proceedings scrapers for venues with no search API.

NeurIPS, IJCAI, CVF (CVPR/ICCV/WACV), and PMLR publish full per-year/per-volume
listings we can fetch and keyword-filter locally. All verified working with a
browser User-Agent.

Because these are full-listing pages, ``search`` fetches the listing for the
requested year/volume then filters titles by the keyword tokens.
"""
from __future__ import annotations

import re
from typing import Optional

from bs4 import BeautifulSoup

from .base import BROWSER_UA, HttpClient, Paper, clean


def _match(title: str, keyword: str) -> bool:
    toks = [t for t in re.split(r"\s+", keyword.lower()) if t]
    tl = title.lower()
    return all(t in tl for t in toks)


class _ScraperBase:
    def __init__(self, client: Optional[HttpClient] = None):
        self.http = client or HttpClient(user_agent=BROWSER_UA, min_interval=1.0)

    def _soup(self, url: str) -> BeautifulSoup:
        resp = self.http.get(url)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")


class NeurIPSProvider(_ScraperBase):
    name = "neurips"
    BASE = "https://papers.nips.cc"

    def listing(self, year: int) -> list[Paper]:
        soup = self._soup(f"{self.BASE}/paper_files/paper/{year}")
        out: list[Paper] = []
        for a in soup.select("a[href*='/paper_files/paper/']"):
            href = a.get("href", "")
            if "-Abstract" not in href:
                continue
            title = clean(a.get_text())
            if not title:
                continue
            out.append(
                Paper(
                    title=title,
                    link=self.BASE + href,
                    source=self.name,
                    year=year,
                    venue=f"NeurIPS {year}",
                )
            )
        return out

    def search(self, keyword: str, year: int, max_results: int = 50) -> list[Paper]:
        return [p for p in self.listing(year) if _match(p.title, keyword)][:max_results]


class IJCAIProvider(_ScraperBase):
    name = "ijcai"
    BASE = "https://www.ijcai.org"

    def listing(self, year: int) -> list[Paper]:
        soup = self._soup(f"{self.BASE}/proceedings/{year}/")
        out: list[Paper] = []
        for wrap in soup.select("div.paper_wrapper"):
            t = wrap.select_one(".title")
            if not t:
                continue
            title = clean(t.get_text())
            pdf = None
            for a in wrap.select("a"):
                href = a.get("href", "")
                if href.lower().endswith(".pdf"):
                    pdf = href if href.startswith("http") else f"{self.BASE}/proceedings/{year}/{href}"
                    break
            out.append(
                Paper(
                    title=title or "(no title)",
                    link=pdf,
                    source=self.name,
                    year=year,
                    venue=f"IJCAI {year}",
                    pdf_url=pdf,
                )
            )
        return out

    def search(self, keyword: str, year: int, max_results: int = 50) -> list[Paper]:
        return [p for p in self.listing(year) if _match(p.title, keyword)][:max_results]


class CVFProvider(_ScraperBase):
    name = "cvf"
    BASE = "https://openaccess.thecvf.com"

    def listing(self, conference: str, year: int) -> list[Paper]:
        """conference: 'CVPR' | 'ICCV' | 'WACV'."""
        url = f"{self.BASE}/{conference}{year}?day=all"
        soup = self._soup(url)
        out: list[Paper] = []
        for dt in soup.select("dt.ptitle"):
            a = dt.find("a")
            if not a:
                continue
            href = a.get("href", "")
            out.append(
                Paper(
                    title=clean(a.get_text()) or "(no title)",
                    link=self.BASE + "/" + href.lstrip("/"),
                    source=self.name,
                    year=year,
                    venue=f"{conference} {year}",
                )
            )
        return out

    def search(
        self, keyword: str, conference: str = "CVPR", year: int = 2024, max_results: int = 50
    ) -> list[Paper]:
        return [
            p for p in self.listing(conference, year) if _match(p.title, keyword)
        ][:max_results]


class ECCVProvider(_ScraperBase):
    """ECCV via the ECVA open-access site (ecva.net). ECCV is NOT on
    openaccess.thecvf.com — ECVA publishes all years on one page, with the
    year encoded in each paper's href (e.g. papers/eccv_2024/...)."""

    name = "eccv"
    BASE = "https://www.ecva.net"

    def __init__(self, client: Optional[HttpClient] = None):
        super().__init__(client)
        self._all: Optional[list[tuple[int, Paper]]] = None

    def _load_all(self) -> list[tuple[int, Paper]]:
        if self._all is not None:
            return self._all
        soup = self._soup(f"{self.BASE}/papers.php")
        rows: list[tuple[int, Paper]] = []
        for dt in soup.select("dt.ptitle"):
            a = dt.find("a")
            if not a:
                continue
            href = a.get("href", "")
            ym = re.search(r"eccv_(\d{4})", href)
            year = int(ym.group(1)) if ym else None
            rows.append(
                (
                    year,
                    Paper(
                        title=clean(a.get_text()) or "(no title)",
                        link=f"{self.BASE}/{href.lstrip('/')}",
                        source=self.name,
                        year=year,
                        venue=f"ECCV {year}" if year else "ECCV",
                    ),
                )
            )
        self._all = rows
        return rows

    def listing(self, year: int) -> list[Paper]:
        return [p for y, p in self._load_all() if y == year]

    def search(self, keyword: str, year: Optional[int] = None, max_results: int = 50) -> list[Paper]:
        out = [
            p
            for y, p in self._load_all()
            if (year is None or y == year) and _match(p.title, keyword)
        ]
        return out[:max_results]


class PMLRProvider(_ScraperBase):
    name = "pmlr"
    BASE = "https://proceedings.mlr.press"

    def __init__(self, client: Optional[HttpClient] = None):
        super().__init__(client)
        self._vol_map: Optional[dict[str, dict[int, str]]] = None

    def volume_map(self) -> dict[str, dict[int, str]]:
        """Build {conference: {year: 'vNNN'}} by parsing the PMLR index once."""
        if self._vol_map is not None:
            return self._vol_map
        soup = self._soup(f"{self.BASE}/")
        mapping: dict[str, dict[int, str]] = {}
        for a in soup.find_all("a", href=re.compile(r"^v\d+$")):
            vol = a.get("href")
            parent = a.find_parent()
            text = " ".join(parent.get_text().split()) if parent else ""
            ym = re.search(r"(19|20)\d{2}", text)
            year = int(ym.group()) if ym else None
            if not year:
                continue
            for conf in ("ICML", "AISTATS", "UAI", "CoLLAs", "ACML", "COLT"):
                if re.search(rf"\b{conf}\b", text):
                    mapping.setdefault(conf.lower(), {})[year] = vol
        self._vol_map = mapping
        return mapping

    def resolve_volume(self, conference: str, year: int) -> Optional[str]:
        return self.volume_map().get(conference.lower(), {}).get(year)

    def search_conference(
        self, keyword: str, conference: str, year: int, max_results: int = 50
    ) -> list[Paper]:
        vol = self.resolve_volume(conference, year)
        if not vol:
            return []
        return self.search(keyword, volume=vol, max_results=max_results)

    def listing(self, volume: str) -> list[Paper]:
        """volume: e.g. 'v235' (ICML 2024)."""
        vol = volume if volume.startswith("v") else f"v{volume}"
        soup = self._soup(f"{self.BASE}/{vol}/")
        out: list[Paper] = []
        for div in soup.select("div.paper"):
            t = div.select_one(".title")
            if not t:
                continue
            links = {a.get_text(strip=True): a.get("href") for a in div.select("p.links a")}
            authors = clean(
                div.select_one(".authors").get_text() if div.select_one(".authors") else ""
            )
            out.append(
                Paper(
                    title=clean(t.get_text()) or "(no title)",
                    link=links.get("abs"),
                    source=self.name,
                    authors=[a.strip() for a in authors.split(",")] if authors else [],
                    venue=f"PMLR {vol}",
                    pdf_url=links.get("Download PDF"),
                    extra={"openreview": links.get("OpenReview")} if links.get("OpenReview") else {},
                )
            )
        return out

    def search(self, keyword: str, volume: str, max_results: int = 50) -> list[Paper]:
        return [p for p in self.listing(volume) if _match(p.title, keyword)][:max_results]
