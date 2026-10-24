"""Optional Playwright / Chromium installer for browser clearance.

Fetch layer raises ``ClearanceNeededError`` (no UI). QueryOp ``on_success``
on the main thread prompts and installs after the progress dialog closes.

Install layout (under the addon package)::

  user_files/pydeps/          # pip packages
  user_files/ms-playwright/   # Chromium (PLAYWRIGHT_BROWSERS_PATH)
  user_files/clearance_prefs.json
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


class ClearanceNeededError(RuntimeError):
    """Playwright/Chromium missing when a site challenges.

    Marker attribute ``quickfill_clearance_needed`` is True so callers can
    detect this even if two copies of the module are loaded (Anki addon
    path quirks) and ``except ClearanceNeededError`` would miss.
    """

    quickfill_clearance_needed = True


def is_clearance_needed_error(exc: BaseException) -> bool:
    if getattr(exc, "quickfill_clearance_needed", False):
        return True
    if type(exc).__name__ == "ClearanceNeededError":
        return True
    return False


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


def _on_main_thread() -> bool:
    try:
        from aqt.qt import QCoreApplication, QThread

        app = QCoreApplication.instance()
        if app is None:
            return False
        return QThread.currentThread() is app.thread()
    except Exception:
        return False


def _ask_user(prompt: str) -> bool:
    """Yes/No via Anki askUser. Safe on main thread; hop if on a worker."""
    try:
        from aqt import mw
        from aqt.utils import askUser

        if mw is None:
            raise RuntimeError("no mw")

        # Editor "Fill" runs on the main thread — call askUser directly.
        if _on_main_thread():
            return bool(askUser(prompt))

        # Background worker only: hop to main and wait (main keeps spinning).
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
        print("(CLI: set QUICKFILL_INSTALL_CLEARANCE=1 to auto-accept)")
        return False


# Packages installed into user_files/pydeps (optional clearance stack).
# requests is expected from Anki itself.
CLEARANCE_PIP_PACKAGES = (
    "beautifulsoup4",
    "curl_cffi",
    "cloudscraper",
    "playwright",
)

_PROMPT = (
    "This dictionary site is showing a bot check (Cloudflare).\n\n"
    "Install optional browser-clearance support?\n"
    "(Playwright, Chromium, curl_cffi, … — roughly 100+ MB)\n\n"
    "If you choose No, use a VPN or a different network."
)


def offer_clearance_install(
    message: Optional[Log] = None,
    *,
    force: bool = False,
) -> bool:
    """Prompt + install. Call only from the main thread (e.g. QueryOp success)."""
    log = message or (lambda _m: None)
    ensure_runtime_paths()

    if clearance_available():
        return True

    if clearance_declined() and not force:
        log(
            "Browser clearance was previously declined. "
            "Delete user_files/clearance_prefs.json to be asked again."
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
    log(
        "Browser clearance is ready. Retry the fetch."
        if ok
        else "Install finished but Playwright/Chromium not detected. Restart Anki."
    )
    return ok


def _run(cmd: list[str], *, env: Optional[dict] = None, log: Log) -> None:
    """Run *cmd* and stream output to *log* (avoids PIPE deadlock)."""
    log("$ " + " ".join(cmd))
    # Inherit stdout/stderr so pip/playwright progress is visible in a
    # terminal; also append lines to the addon log when we can read them.
    proc = subprocess.Popen(
        cmd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        line = line.rstrip()
        if line:
            log(line)
    rc = proc.wait()
    if rc != 0:
        raise RuntimeError(f"Command failed ({rc}): {' '.join(cmd)}")


def _pip_available() -> bool:
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "--version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except Exception:
        return False


def _bootstrap_pip(log: Log) -> None:
    """Make ``python -m pip`` work when the runtime ships without pip (Flatpak).

    Order:
      1. ``python -m ensurepip --upgrade`` (stdlib; may be disabled)
      2. Download get-pip.py and run it with ``--user``
    """
    if _pip_available():
        return

    log("pip not found; trying ensurepip …")
    try:
        _run(
            [sys.executable, "-m", "ensurepip", "--upgrade"],
            log=log,
        )
    except Exception as e:
        log(f"ensurepip failed: {e}")

    if _pip_available():
        log("pip available after ensurepip")
        return

    log("Downloading get-pip.py …")
    get_pip = user_files_dir() / "get-pip.py"
    try:
        import urllib.request

        urllib.request.urlretrieve(
            "https://bootstrap.pypa.io/get-pip.py",
            str(get_pip),
        )
    except Exception as e:
        raise RuntimeError(
            "Could not download get-pip.py (network blocked?). "
            f"Original error: {e}"
        ) from e

    # --user: install pip into the user site (writable under Flatpak home).
    # Do not combine with -t (pip rejects that).
    log("Running get-pip.py --user …")
    _run([sys.executable, str(get_pip), "--user"], log=log)

    if not _pip_available():
        raise RuntimeError(
            "Bootstrapped pip but ``python -m pip`` still fails. "
            "Install packages manually into vendor/ or user_files/pydeps."
        )
    log("pip is ready")


def install_clearance(message: Optional[Log] = None) -> None:
    """Bootstrap pip if needed, install deps into user_files/pydeps, fetch Chromium."""
    log = message or (lambda _m: None)
    ensure_runtime_paths()
    deps = pydeps_dir()
    deps.mkdir(parents=True, exist_ok=True)
    browsers = browsers_dir()
    browsers.mkdir(parents=True, exist_ok=True)

    _bootstrap_pip(log)

    log("Installing: " + ", ".join(CLEARANCE_PIP_PACKAGES))
    _run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--upgrade",
            *CLEARANCE_PIP_PACKAGES,
            "-t",
            str(deps),
        ],
        log=log,
    )

    ensure_runtime_paths()
    env = os.environ.copy()
    env["PLAYWRIGHT_BROWSERS_PATH"] = str(browsers)
    env["PYTHONPATH"] = str(deps) + os.pathsep + env.get("PYTHONPATH", "")

    log("Downloading Chromium (large) …")
    _run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        env=env,
        log=log,
    )
    log(f"Chromium under {browsers}")
