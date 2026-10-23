"""Intermediate base for HTTP / HTML scrape fetchers.

Sits between ``Fetcher`` and site-specific bases (Cambridge, MW, Yahoo, …).
Non-HTTP sources (e.g. CSV) keep inheriting ``Fetcher`` directly.

Provides a single entry point for page downloads:

* **site_session** (default) — host-keyed cookies, optional Playwright
  clearance, curl_cffi when available.
* **legacy** — per-instance ``http_client.create_session`` (requests /
  cloudscraper) when ``use_site_session`` is false.

Subclasses typically set::

    site_host = "dictionary.cambridge.org"
    headers = {...}

    def page_ok(self, html) -> bool:
        return "entry-body" in html

Prefer ``self.acquire_soup(url, config)`` in ``fetch()`` — it re-raises
clearance errors so QueryOp can prompt, and returns None on other failures.
Low-level: ``_get_html`` / ``_get_soup``.
"""

from __future__ import annotations

from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from .base_fetcher import Fetcher
from .http_client import create_session, is_cloudflare_challenge
from .site_session import fetch_html, use_site_session_enabled
from .clearance_install import is_clearance_needed_error


class HttpFetcher(Fetcher):
    """Shared HTTP download helpers for web scrape fetchers.

    Intermediate base – the auto-loader skips it because ``source_name()``
    raises ``NotImplementedError``.
    """

    # Optional fixed host for site_session (else taken from each URL).
    site_host = None

    # Default headers for the legacy (non–site_session) path.
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;"
            "q=0.9,image/avif,image/webp,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
    }

    @staticmethod
    def source_name():
        raise NotImplementedError(
            "HttpFetcher is an abstract base; subclasses must implement source_name()"
        )

    def page_ok(self, html: str) -> bool:
        """Return True if *html* looks like a real content page for this site.

        Default: non-empty and not a Cloudflare interstitial. Override with
        a site-specific marker (e.g. ``\"entry-body\" in html``).
        """
        if not html or len(html) < 500:
            return False
        return not is_cloudflare_challenge(html)

    def _legacy_session(self, config=None):
        """Per-instance requests/cloudscraper session (site_session off)."""
        cfg = (config or {}).get("config") or {}
        flag = cfg.get("use_cloudscraper")
        if (
            not hasattr(self, "_http")
            or getattr(self, "_http_flag", object()) != flag
        ):
            self._http = create_session(
                headers=self.headers,
                use_cloudscraper=flag,
            )
            self._http_flag = flag
        return self._http

    def _resolve_host(self, url: str) -> str | None:
        if self.site_host:
            return self.site_host
        return urlparse(url).hostname or None

    def _get_html(self, url: str, config=None, timeout: int = 20) -> str:
        """Download *url* as text, using site_session or legacy HTTP."""
        if use_site_session_enabled(config):
            return fetch_html(
                url,
                host=self._resolve_host(url),
                config=config,
                page_ok=self.page_ok,
                timeout=timeout,
                message=self.message_callback,
            )

        session = self._legacy_session(config)
        r = session.get(url, timeout=timeout)
        r.raise_for_status()
        html = r.text or ""
        if is_cloudflare_challenge(html) or not self.page_ok(html):
            raise RuntimeError(
                "Anti-bot challenge or unexpected page from %s (HTTP %s, %d bytes). "
                "Enable site session (Playwright) or use a different network. URL: %s"
                % (
                    self._resolve_host(url) or "host",
                    r.status_code,
                    len(html),
                    url,
                )
            )
        return html

    def _get_soup(self, url: str, config=None, timeout: int = 20, parser: str = "html.parser"):
        """``_get_html`` then parse with BeautifulSoup."""
        html = self._get_html(url, config=config, timeout=timeout)
        return BeautifulSoup(html, parser)

    def acquire_soup(
        self,
        url: str,
        config=None,
        *,
        timeout: int = 20,
        parser: str = "html.parser",
        error_label: str = "Fetch",
    ):
        """Download and parse *url*.

        * Re-raises clearance / Playwright-needed errors (for QueryOp UI).
        * On other failures: logs via ``message_callback`` and returns ``None``.

        Subclasses should use this in ``fetch()`` instead of a local
        ``try/except Exception`` around ``_get_soup``.
        """
        try:
            return self._get_soup(
                url, config=config, timeout=timeout, parser=parser
            )
        except Exception as e:
            if is_clearance_needed_error(e):
                raise
            self.message_callback(f"{error_label} error: {e}")
            return None
