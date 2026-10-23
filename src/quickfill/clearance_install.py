"""Optional Playwright / Chromium installer for browser clearance.

Prompted on the first anti-bot challenge when Playwright is not available.
Installs into ``user_files/`` so addon code updates do not wipe the payload:

  user_files/pydeps/          # playwright (and deps) on sys.path
  user_files/ms-playwright/   # browser binaries (PLAYWRIGHT_BROWSERS_PATH)

Config / prefs (under package user_files):

  clearance_prefs.json → {"declined": true} after user says No
"""

from __future__ import annotations

import os
import json
import subprocess
import sys
import threading
from pathlib import Path
from typing import Callable, Optional

Log = Callable[[str], None]


def package_root() -> Path:
    return Path(__file__).resolve().parent


def user_files_dir() -> Path:
    d = package_root() / "user_files"
    d.mkdir(parents=True, exist_ok=True)
    return d


def pydeps_dir() -> Path:
    return user_files_dir() / "pydeps"


def browsers_dir() -> Path:
    return user_files_dir() / "ms-playwright"


def prefs_path() -> Path:
    return user_files_dir() / "clearance_prefs.json"


def ensure_runtime_paths() -> None:
    """Put user_files pydeps on sys.path and set PLAYWRIGHT_BROWSERS_PATH."""
    deps = pydeps_dir()
    if deps.is_dir():
        p = str(deps)
        if p not in sys.path:
            sys.path.insert(0, p)
    # Prefer explicit env; otherwise point at our user_files browsers tree
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(browsers_dir()))


def load_prefs() -> dict:
    path = prefs_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_prefs(data: dict) -> None:
    prefs_path().write_text(json.dumps(data, indent=2), encoding="utf-8")


def clearance_declined() -> bool:
    return bool(load_prefs().get("declined"))


def set_declined(value: bool = True) -> None:
    prefs = load_prefs()
    prefs["declined"] = bool(value)
    save_prefs(prefs)


def playwright_importable() -> bool:
    ensure_runtime_paths()
    try:
        import playwright  # noqa: F401

        return True
    except ImportError:
        return False


def chromium_installed() -> bool:
    ensure_runtime_paths()
    root = Path(os.environ.get("PLAYWRIGHT_BROWSERS_PATH", str(browsers_dir())))
    if not root.is_dir():
        return False
    # Playwright lays out chromium-XXXX/ or chrome-linux etc.
    for child in root.iterdir():
        if child.is_dir() and (
            "chrom" in child.name.lower() or "firefox" in child.name.lower()
        ):
            return True
    return False


def clearance_available() -> bool:
    return playwright_importable() and chromium_installed()


def _ask_user(prompt: str) -> bool:
    """Yes/No prompt. Uses Anki askUser on the main thread when available."""
    try:
        from aqt import mw
        from aqt.utils import askUser

        if mw is None:
            raise RuntimeError("no mw")

        result: list[bool] = [False]
        done = threading.Event()

        def _on_main() -> None:
            try:
                result[0] = bool(askUser(prompt))
            finally:
                done.set()

        # Always hop to main — safe if already on main (runs inline via taskman)
        mw.taskman.run_on_main(_on_main)
        if not done.wait(timeout=600):
            return False
        return result[0]
    except Exception:
        # CLI / tests: require explicit opt-in
        env = os.environ.get("QUICKFILL_INSTALL_CLEARANCE", "").strip().lower()
        if env in ("1", "true", "yes", "y"):
            return True
        print(prompt)
        print(
            "(CLI: set QUICKFILL_INSTALL_CLEARANCE=1 to auto-accept install prompts)"
        )
        return False


_PROMPT = (
    "This dictionary site is showing a bot check (Cloudflare).\n\n"
    "QuickFill can install optional browser-clearance support "
    "(Playwright + Chromium, roughly 100+ MB download) so you can "
    "pass the check once and reuse the session.\n\n"
    "Install browser clearance now?\n\n"
    "If you choose No, use a VPN or a different network, or install "
    "later from Tools if available."
)


def offer_clearance_install(
    message: Optional[Log] = None,
    *,
    force: bool = False,
) -> bool:
    """Prompt once; on Yes run install. Returns True if clearance is ready.

    Skips the prompt if the user previously declined (unless *force*).
    """
    log = message or (lambda _m: None)
    ensure_runtime_paths()

    if clearance_available():
        return True

    if clearance_declined() and not force:
        log(
            "Browser clearance was previously declined. "
            "Use a VPN, or clear user_files/clearance_prefs.json to be asked again."
        )
        return False

    if not _ask_user(_PROMPT):
        set_declined(True)
        log("Browser clearance install declined.")
        return False

    # User accepted — allow future prompts if install fails
    set_declined(False)
    try:
        install_clearance(message=log)
    except Exception as e:
        log(f"Clearance install failed: {e}")
        return False

    ok = clearance_available()
    if ok:
        log("Browser clearance is ready. Retry the fetch.")
    else:
        log(
            "Install finished but Playwright/Chromium still not detected. "
            "Restart Anki and try again."
        )
    return ok


def install_clearance(message: Optional[Log] = None) -> None:
    """pip-install playwright into user_files/pydeps and download Chromium."""
    log = message or (lambda _m: None)
    ensure_runtime_paths()
    deps = pydeps_dir()
    deps.mkdir(parents=True, exist_ok=True)
    browsers = browsers_dir()
    browsers.mkdir(parents=True, exist_ok=True)

    log("Installing Playwright into user_files/pydeps …")
    subprocess.check_call(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--upgrade",
            "playwright",
            "-t",
            str(deps),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    ensure_runtime_paths()
    env = os.environ.copy()
    env["PLAYWRIGHT_BROWSERS_PATH"] = str(browsers)
    # So ``python -m playwright`` finds the just-installed package
    pp = str(deps)
    env["PYTHONPATH"] = pp + os.pathsep + env.get("PYTHONPATH", "")

    log("Downloading Chromium (this may take a while) …")
    subprocess.check_call(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    log(f"Chromium installed under {browsers}")
