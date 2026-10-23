import sys
import os
from pathlib import Path
import importlib.util

_root = Path(__file__).resolve().parent

os.environ.setdefault(
    "PLAYWRIGHT_BROWSERS_PATH",
    str(Path(__file__).resolve().parent / "user_files" / "ms-playwright"),
)

vendor_dir = _root / "vendor"
if vendor_dir.is_dir():
    sys.path.insert(0, str(vendor_dir))

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
