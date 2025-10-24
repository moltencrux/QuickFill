import sys
import os
import importlib.util

addon_dir = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, addon_dir)

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