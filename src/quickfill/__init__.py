import sys
import os
from pathlib import Path
import importlib.util

_root = Path(__file__).resolve().parent

# Optional Playwright browsers (user_files; survives code updates)
os.environ.setdefault(
    "PLAYWRIGHT_BROWSERS_PATH",
    str(_root / "user_files" / "ms-playwright"),
)

# Vendor (shipped or manually installed) + user_files/pydeps (prompt installer)
for _deps in (_root / "vendor", _root / "user_files" / "pydeps"):
    if _deps.is_dir():
        _p = str(_deps)
        if _p not in sys.path:
            sys.path.insert(0, _p)

if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from .base_fetcher import Fetcher
from .csv_seeker import CSVSeeker
from . import fetchers

__all__ = [
    'Fetcher',
    'CSVSeeker',
    'fetchers'
]

# Check if this is an Anki environment or a testing/dev environment
if importlib.util.find_spec('aqt'):
    from . import quickfill_addon
    __all__.append('FetcherRegistry')
