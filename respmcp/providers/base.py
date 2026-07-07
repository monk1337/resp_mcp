"""Shared HTTP session, rate limiting, retry, and the normalized Paper model.

Every provider returns lists of ``Paper``.
"""
from __future__ import annotations

import os
import time
import threading
from dataclasses import dataclass, field, asdict
from typing import Any, Optional

import requests

# A polite contact string lands you in the "polite pool" for OpenAlex/Crossref
# and is generally good manners for the other open APIs.
CONTACT = os.environ.get("RESP_CONTACT_EMAIL", "resp-mcp@example.com")

DEFAULT_UA = (
    f"resp-mcp/0.1 (https://github.com/monk1337/resp; mailto:{CONTACT}) "
    "python-requests"
)

# A browser-like UA for sites that reject obvious bots (arXiv HTML, CVF, PMLR).
BROWSER_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)


@dataclass
class Paper:
    """Normalized paper record returned by every provider."""

    title: str
    link: Optional[str] = None
    source: str = ""
    authors: list[str] = field(default_factory=list)
    year: Optional[int] = None
    venue: Optional[str] = None
    abstract: Optional[str] = None
    doi: Optional[str] = None
    pdf_url: Optional[str] = None
    num_citations: Optional[int] = None
    paper_id: Optional[str] = None  # provider-native id (S2, OpenAlex, OpenReview, CP)
    external_ids: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return {k: v for k, v in d.items() if v not in (None, [], {}, "")}


class RateLimiter:
    """Simple thread-safe minimum-interval limiter (token-bucket of size 1)."""

    def __init__(self, min_interval: float):
        self.min_interval = min_interval
        self._lock = threading.Lock()
        self._last = 0.0

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            delta = now - self._last
            if delta < self.min_interval:
                time.sleep(self.min_interval - delta)
            self._last = time.monotonic()


class HttpClient:
    """A shared requests session with retry/backoff and per-host rate limiting."""

    def __init__(
        self,
        user_agent: str = DEFAULT_UA,
        min_interval: float = 0.0,
        max_retries: int = 3,
        backoff: float = 1.5,
        timeout: float = 30.0,
    ):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent})
        self.limiter = RateLimiter(min_interval) if min_interval > 0 else None
        self.max_retries = max_retries
        self.backoff = backoff
        self.timeout = timeout

    def request(self, method: str, url: str, **kwargs) -> requests.Response:
        kwargs.setdefault("timeout", self.timeout)
        last_exc: Optional[Exception] = None
        for attempt in range(self.max_retries):
            if self.limiter:
                self.limiter.wait()
            try:
                resp = self.session.request(method, url, **kwargs)
            except requests.RequestException as exc:  # network-level failure
                last_exc = exc
                time.sleep(self.backoff ** attempt)
                continue
            # Retry on transient server / rate-limit statuses.
            if resp.status_code in (429, 500, 502, 503, 504):
                last_exc = requests.HTTPError(
                    f"{resp.status_code} for {url}", response=resp
                )
                retry_after = resp.headers.get("Retry-After")
                sleep_s = (
                    float(retry_after)
                    if retry_after and retry_after.isdigit()
                    else self.backoff ** attempt
                )
                time.sleep(sleep_s)
                continue
            return resp
        if last_exc:
            raise last_exc
        raise RuntimeError(f"request failed without exception: {url}")

    def get(self, url: str, **kwargs) -> requests.Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs) -> requests.Response:
        return self.request("POST", url, **kwargs)


def clean(text: Optional[str]) -> Optional[str]:
    if text is None:
        return None
    return " ".join(text.split()).strip() or None
