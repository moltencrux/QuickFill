"""Shared HTTP helpers for QuickFill fetchers.

Optional dependency: ``cloudscraper`` (``pip install cloudscraper``).

When installed, sessions are created with cloudscraper so Cloudflare
JS challenges are more likely to pass. Without it, plain
``requests.Session`` is used and behavior is unchanged.

Per-request override via config::

    "config": { "use_cloudscraper": true }   # force on (error if missing)
    "config": { "use_cloudscraper": false }  # force plain requests
    # omit / null → auto (use cloudscraper if importable)
"""

from __future__ import annotations

import requests

try:
    import cloudscraper
except ImportError:
    cloudscraper = None


DEFAULT_HEADERS = {
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
    # Avoid br — requests may not decompress it on all installs.
    "Accept-Encoding": "gzip, deflate",
}


def cloudscraper_available() -> bool:
    return cloudscraper is not None


# Markers that show up on Cloudflare interstitial / challenge pages.
# These often return HTTP 200, so status checks alone are not enough.
_CF_MARKERS = (
    "just a moment",
    "cf-browser-verification",
    "challenge-platform",
    "cdn-cgi/challenge",
    "turnstile",
    "cf-turnstile",
    "attention required",
    "enable javascript and cookies",
    "checking your browser",
    "ddos protection by cloudflare",
)


def is_cloudflare_challenge(html: str) -> bool:
    """True if *html* looks like a Cloudflare challenge, not real content."""
    if not html:
        return False
    lower = html.lower()
    # Strong signals
    hits = sum(1 for m in _CF_MARKERS if m in lower)
    if hits >= 1 and (
        "cloudflare" in lower
        or "cf-" in lower
        or "challenge-platform" in lower
        or "turnstile" in lower
    ):
        return True
    # Title-only interstitial
    if "<title>just a moment" in lower or "<title>attention required" in lower:
        return True
    return False


def _want_cloudscraper(flag) -> bool:
    """Resolve optional config flag to a concrete bool.

    ``None`` / omitted → use cloudscraper when importable.
    ``True`` → require cloudscraper (raise if missing).
    ``False`` → always plain requests.
    """
    if flag is False:
        return False
    if flag is True:
        if cloudscraper is None:
            raise RuntimeError(
                "config sets use_cloudscraper=true but cloudscraper is not "
                "installed. Run: pip install cloudscraper"
            )
        return True
    # auto
    return cloudscraper is not None


def create_session(headers=None, use_cloudscraper=None):
    """Return a Session (cloudscraper or requests) with headers applied.

    Args:
        headers: optional dict merged over DEFAULT_HEADERS.
        use_cloudscraper: True / False / None (auto). See module docstring.
    """
    use_cs = _want_cloudscraper(use_cloudscraper)
    if use_cs:
        session = cloudscraper.create_scraper(
            browser={
                "browser": "chrome",
                "platform": "windows",
                "mobile": False,
            }
        )
    else:
        session = requests.Session()

    merged = dict(DEFAULT_HEADERS)
    if headers:
        merged.update(headers)
    session.headers.update(merged)
    return session


def get(url, headers=None, timeout=12, use_cloudscraper=None, session=None):
    """GET *url*, optionally via cloudscraper.

    Pass an existing *session* to reuse cookies; otherwise a one-shot
    session is created.
    """
    own = session is None
    if own:
        session = create_session(headers=headers, use_cloudscraper=use_cloudscraper)
    elif headers:
        # ephemeral header override for this request only
        pass
    try:
        if headers and not own:
            return session.get(url, headers=headers, timeout=timeout)
        return session.get(url, timeout=timeout)
    finally:
        if own:
            session.close()
