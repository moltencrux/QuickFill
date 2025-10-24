import importlib
import inspect
from pathlib import Path

# Import Fetcher from parent package
from ..base_fetcher import Fetcher

__all__ = ['all_fetchers']
all_fetchers = []

def _load_fetchers():
    """Dynamically load all Fetcher subclasses from the fetchers/ directory."""
    fetchers = {}
    package_name = __name__
    package_path = Path(__file__).parent
    print(f"Debug: Loading fetchers from {package_path}")

    # List all .py files in fetchers/
    py_files = [f.name for f in package_path.glob('*.py') if f.name != '__init__.py']
    print(f"Debug: Found Python files in fetchers/: {py_files}")

    for file_path in package_path.glob('*.py'):
        if file_path.name == '__init__.py':
            continue
        module_name = file_path.stem
        try:
            # Import module relative to quickfill.fetchers
            module = importlib.import_module(f"{package_name}.{module_name}")
            print(f"Debug: Successfully imported module {module_name}")
            # Find Fetcher subclasses
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if isinstance(attr, type) and issubclass(attr, Fetcher) and attr != Fetcher:
                    fetchers[attr_name] = attr

        except Exception as e:
            print(f"Debug: Failed to import module {module_name}: {str(e)}")

    return fetchers

# Load fetchers and update globals
for name, obj in _load_fetchers().items():
    globals()[name] = obj
    if name not in __all__:
        __all__.append(name)
        all_fetchers.append(obj)

