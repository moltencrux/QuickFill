"""Host-keyed HTTP sessions with optional browser clearance.

Any web fetcher can opt in when a site serves anti-bot interstitials
(Cloudflare Turnstile, etc.):

    from ..site_session import fetch_html, is_challenge_response

    html = fetch_html(
        url,
        host="dictionary.cambridge.org",
        config=config,
        page_ok=lambda h: "entry-body" in h,
    )

Design
------
* **One session per host** (process-wide), shared by every fetcher that
  talks to that host (e.g. all Cambridge EC/EJ flavors).
* **Not** one global session for unrelated sites (Yahoo, MW, …).
* Optional **Playwright** harvest: open a real browser only when a
  response looks like a challenge; save cookies + UA identity to disk;
  close the browser; retry with curl_cffi (preferred) or requests.
* Optional deps: ``curl_cffi``, ``playwright``. Without them, behavior
  falls back to plain requests / cloudscraper via ``http_client``.

Config keys (under the fetcher's ``config.config`` dict)
-------------------------------------------------------
``use_site_session``
    true / false / omit.  omit or true → use this module when possible.
``browser_clearance``
    ``"auto"`` (default) — open browser only on challenge.
    ``"never"`` — never open a browser; raise on challenge.
    ``"always"`` — harvest before the first request if no saved session.
``session_dir``
    Directory for ``<host>.json`` session files and Playwright profiles.
    Default: ``./.quickfill_sessions`` (override in Anki to user_files).
``http_backend``
    ``"auto"`` | ``"curl_cffi"`` | ``"requests"``.  auto prefers curl_cffi.
``solve_timeout``
    Seconds to wait for a human to pass the browser check (default 300).
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urlparse

from .http_client import (
    DEFAULT_HEADERS,
    create_session,
    is_cloudflare_challenge,
)

try:
    from curl_cffi import requests as cffi_requests
    from curl_cffi.requests import BrowserType

    _HAS_CFFI = True
except ImportError:
    cffi_requests = None
    BrowserType = None
    _HAS_CFFI = False

# Process-wide: host → SiteSession
_REGISTRY: dict[str, "SiteSession"] = {}

PageOk = Callable[[str], bool]


def is_challenge_response(status: int, html: str) -> bool:
    """True if the HTTP response looks like an anti-bot interstitial."""
    if status in (403, 503):
        return True
    return is_cloudflare_challenge(html or "")


def default_session_dir() -> Path:
    return Path.cwd() / ".quickfill_sessions"


def _cfg(config) -> dict:
    if not config:
        return {}
    return config.get("config") or {}


def _host_from_url(url: str) -> str:
    return urlparse(url).hostname or ""


def _safe_host_filename(host: str) -> str:
    return re.sub(r"[^\w.-]+", "_", host)


def _pick_impersonation(ua: str) -> str:
    if not _HAS_CFFI or not BrowserType:
        return "chrome"
    m = re.search(r"Chrome/(\d+)", ua or "")
    major = int(m.group(1)) if m else 0
    versions = []
    for b in BrowserType:
        mm = re.fullmatch(r"chrome(\d+)", getattr(b, "value", str(b)))
        if mm:
            versions.append(int(mm.group(1)))
    if not versions:
        return "chrome"
    below = [v for v in versions if v <= major]
    return f"chrome{max(below) if below else min(versions)}"


def _playwright_available() -> bool:
    try:
        import playwright  # noqa: F401

        return True
    except ImportError:
        return False


def harvest_browser_identity(
    url: str,
    *,
    host: str,
    session_dir: Path,
    solve_timeout: int = 300,
    page_ok: Optional[PageOk] = None,
    message: Optional[Callable[[str], None]] = None,
) -> dict:
    """Open Chromium, wait until *page_ok* (or non-challenge), return identity.

    Identity: ``{ua, hints, cookies, saved_at}``. Browser is closed before return.
    """
    if not _playwright_available():
        raise RuntimeError(
            "Playwright is not installed. Run: pip install playwright && "
            "playwright install chromium"
        )

    from playwright.sync_api import sync_playwright

    log = message or (lambda _m: None)
    profile = session_dir / f"pw-profile-{_safe_host_filename(host)}"
    profile.mkdir(parents=True, exist_ok=True)

    def _ok(html: str) -> bool:
        if page_ok is not None:
            return bool(page_ok(html)) and not is_cloudflare_challenge(html)
        return bool(html) and not is_cloudflare_challenge(html) and len(html) > 5000

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(profile),
            headless=False,
            no_viewport=True,
            ignore_default_args=["--enable-automation"],
            args=["--disable-blink-features=AutomationControlled"],
        )
        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(url, wait_until="load")

            deadline = time.time() + solve_timeout
            announced = False
            while True:
                try:
                    html = page.content()
                except Exception:
                    html = ""
                if _ok(html):
                    break
                if not announced:
                    log(
                        f"Solve the anti-bot check for {host} in the browser window…"
                    )
                    announced = True
                if time.time() > deadline:
                    raise TimeoutError(
                        f"Timed out waiting for clearance on {host} ({solve_timeout}s)"
                    )
                time.sleep(1)

            ua = page.evaluate("navigator.userAgent")
            hints = page.evaluate(
                """() => navigator.userAgentData
                    ? {brands: navigator.userAgentData.brands,
                       platform: navigator.userAgentData.platform}
                    : null"""
            )
            cookies = [
                c
                for c in context.cookies()
                if host.lstrip(".") in (c.get("domain") or "").lstrip(".")
                or (c.get("domain") or "").endswith(host)
            ]
        finally:
            context.close()

    log(f"Harvested {len(cookies)} cookies for {host}; browser closed.")
    return {
        "host": host,
        "ua": ua,
        "hints": hints,
        "cookies": cookies,
        "saved_at": time.time(),
    }


class SiteSession:
    """HTTP client + persisted identity for a single host."""

    def __init__(self, host: str, session_dir: Optional[Path] = None):
        self.host = host
        self.session_dir = Path(session_dir) if session_dir else default_session_dir()
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.session_dir / f"{_safe_host_filename(host)}.json"
        self.identity: Optional[dict] = None
        self._http = None  # curl_cffi or requests session
        self._backend: Optional[str] = None
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("cookies") is not None:
                self.identity = data
                self._rebuild_http()
        except Exception:
            self.identity = None
            self._http = None

    def save(self) -> None:
        if not self.identity:
            return
        self.path.write_text(
            json.dumps(self.identity, indent=2), encoding="utf-8"
        )

    def _rebuild_http(self, backend: str = "auto") -> None:
        """Build HTTP session from current identity."""
        identity = self.identity or {}
        ua = identity.get("ua") or DEFAULT_HEADERS["User-Agent"]
        headers = dict(DEFAULT_HEADERS)
        headers["User-Agent"] = ua
        hints = identity.get("hints")
        if hints and hints.get("brands"):
            headers["sec-ch-ua"] = ", ".join(
                f'"{b["brand"]}";v="{b["version"]}"' for b in hints["brands"]
            )
            headers["sec-ch-ua-mobile"] = "?0"
            if hints.get("platform"):
                headers["sec-ch-ua-platform"] = f'"{hints["platform"]}"'

        use_cffi = backend == "curl_cffi" or (
            backend == "auto" and _HAS_CFFI
        )
        if use_cffi and _HAS_CFFI:
            impersonate = _pick_impersonation(ua)
            self._http = cffi_requests.Session(
                impersonate=impersonate, headers=headers
            )
            self._backend = f"curl_cffi:{impersonate}"
        else:
            self._http = create_session(headers=headers, use_cloudscraper=False)
            self._backend = "requests"

        for c in identity.get("cookies") or []:
            try:
                self._http.cookies.set(
                    c["name"],
                    c["value"],
                    domain=c.get("domain") or self.host,
                    path=c.get("path") or "/",
                )
            except Exception:
                continue

    def ensure_http(self, backend: str = "auto") -> None:
        if self._http is None:
            self._rebuild_http(backend=backend)

    def apply_identity(self, identity: dict, backend: str = "auto") -> None:
        self.identity = identity
        self._rebuild_http(backend=backend)
        self.save()

    def get(self, url: str, timeout: int = 20):
        self.ensure_http()
        assert self._http is not None
        return self._http.get(url, timeout=timeout)


def get_site_session(host: str, config=None) -> SiteSession:
    """Return the process-wide session for *host*."""
    cfg = _cfg(config)
    session_dir = cfg.get("session_dir")
    key = host
    if key not in _REGISTRY:
        _REGISTRY[key] = SiteSession(
            host, session_dir=Path(session_dir) if session_dir else None
        )
    else:
        # Allow late session_dir override only if still default empty load
        if session_dir:
            ss = _REGISTRY[key]
            new_dir = Path(session_dir)
            if ss.session_dir != new_dir:
                _REGISTRY[key] = SiteSession(host, session_dir=new_dir)
    return _REGISTRY[key]


def fetch_html(
    url: str,
    *,
    host: Optional[str] = None,
    config=None,
    page_ok: Optional[PageOk] = None,
    timeout: int = 20,
    message: Optional[Callable[[str], None]] = None,
) -> str:
    """GET *url* using the shared host session; harvest browser on challenge.

    Raises ``RuntimeError`` if still challenged after a harvest attempt, or
    if browser clearance is disabled / unavailable.
    """
    cfg = _cfg(config)
    host = host or _host_from_url(url)
    if not host:
        raise ValueError(f"Cannot determine host from URL: {url}")

    log = message or (lambda _m: None)
    backend = cfg.get("http_backend") or "auto"
    clearance = cfg.get("browser_clearance") or "auto"
    solve_timeout = int(cfg.get("solve_timeout") or 300)

    ss = get_site_session(host, config)
    ss.ensure_http(backend=backend)

    if clearance == "always" and not ss.identity:
        identity = harvest_browser_identity(
            url,
            host=host,
            session_dir=ss.session_dir,
            solve_timeout=solve_timeout,
            page_ok=page_ok,
            message=log,
        )
        ss.apply_identity(identity, backend=backend)

    def _once() -> tuple[int, str]:
        r = ss.get(url, timeout=timeout)
        status = getattr(r, "status_code", 0)
        html = r.text or ""
        return status, html

    status, html = _once()

    challenged = is_challenge_response(status, html)
    if page_ok is not None and not challenged and not page_ok(html):
        # Soft failure: page loaded but missing expected markers — treat as
        # possible soft block only if it also looks empty/small.
        if len(html) < 8000:
            challenged = True

    if not challenged:
        return html

    if clearance == "never":
        raise RuntimeError(
            f"Anti-bot challenge from {host} (HTTP {status}) and "
            f"browser_clearance is 'never'. URL: {url}"
        )

    log(f"Challenge from {host}; opening browser for clearance…")
    identity = harvest_browser_identity(
        url,
        host=host,
        session_dir=ss.session_dir,
        solve_timeout=solve_timeout,
        page_ok=page_ok,
        message=log,
    )
    ss.apply_identity(identity, backend=backend)

    status, html = _once()
    if is_challenge_response(status, html):
        raise RuntimeError(
            f"Still challenged by {host} after browser clearance "
            f"(HTTP {status}). The HTTP backend may be fingerprint-blocked; "
            f"try http_backend=requests or a different network. URL: {url}"
        )
    if page_ok is not None and not page_ok(html):
        raise RuntimeError(
            f"Clearance obtained for {host} but page_ok check failed. URL: {url}"
        )
    return html


def use_site_session_enabled(config=None) -> bool:
    """Whether the caller should route through ``fetch_html``."""
    cfg = _cfg(config)
    flag = cfg.get("use_site_session")
    if flag is False:
        return False
    # true or omit → enabled (harvest still needs playwright when challenged)
    return True
