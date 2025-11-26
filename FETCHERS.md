# Creating New Fetchers for the QuickFill Add-on

This guide explains how to create new fetcher classes for the QuickFill add-on, which integrates with Anki (version 25.09.2+) to populate note fields in the Add Cards dialog. Fetchers retrieve data from various sources (e.g., CSV files, APIs) and map it to Anki note fields based on the configuration in `config.json`.

## Overview

The QuickFill add-on uses a `Fetcher` base class (`base_fetcher.py`) that defines the interface for all fetchers. Subclasses like `CSVFetcher` and `YahooFetcher` implement specific data retrieval logic. The `FetcherRegistry` (`fetcher.py`) loads all fetchers listed in `fetchers/__init__.py` (in the `all_fetchers` list) and uses them to fetch data based on the `source` specified in `config.json`. Each fetcher must implement:

- A `source_name` **static method** to identify the fetcher.
- A `fetch` method to retrieve and format data.
- An `__init__` (Opitional for many) sets up the `message_callback` facility and any other setup required for your fetcher

## Steps to Create a New Fetcher

### 1. Create the Fetcher Class

Create a new Python file in the `fetchers` directory of the add-on folder (e.g., *`quickfill`*`/fetchers/my_fetcher.py`). The class must inherit from `Fetcher` in `base_fetcher.py`.

```python
from .. import Fetcher

class MyFetcher(Fetcher):
    def __init__(self, message_callback=None):
        super().__init__(message_callback)

    @staticmethod
    def source_name():
        return "my_fetcher"

    def fetch(self, word, config):
        # Your logic here
        return {}  # dict: {field_index: value, ...}
```

- **File Location**: Place the file in *`quickfill`*`/fetchers/` (e.g., *`quickfill`*`/fetchers/my_fetcher.py`).
- **Class Name**: Use a descriptive name (e.g., `MyFetcher`) that reflects the data source.
- **Inheritance**: Inherit from `Fetcher` to ensure compatibility with `FetcherRegistry`.

### 2. Implement `__init__` (Optional)

The `__init__` method may be simply omitted in many cases. However, if your class requires special initialization, you should be sure to make a call to `super().__init()__` in order to initialize the `message_callback`, which is used to display messages to the user (e.g., errors or warnings via `aqt.utils.showInfo`).

```python
def __init__(self, message_callback=None):
    super().__init__(message_callback)
```

- **Parameters**:
  - `message_callback`: A function (e.g., `showInfo`) to display messages to the user. It’s optional and defaults to `None`.
- **Purpose**: Stores `message_callback` as `self.message_callback` for use in `fetch` (e.g., to notify about missing data).
- **Example**:
  ```python
  self.message_callback(f"No data found for '{word}'")
  ```

### 3. Implement `source_name()` (Required)

The `source_name()` static method returns a unique string identifier for the fetcher, which matches the `fetcher` field in `config.json`.

```python
@staticmethod
def source_name():
    return "my_fetcher"  # ← must match config.json
```

- **Return Value**: A string (e.g., `"my_source"`) that identifies the fetcher in `config.json`.
- **Usage**: The `FetcherRegistry` uses `source_name()` to map the fetcher to the `source` specified in `config.json` (e.g., `"fetcher": "my_source"`).
- **Example**:
  - If `source_name()` returns `"my_source"`, the `config.json` should include:
    ```json
    "fetcher": "my_source"
    ```

### 4. Implement `fetch()` (Required)

The `fetch` method retrieves data for a given word and maps it to Anki note field indices based on the configuration. It’s the core method for data retrieval and processing.

```python
def fetch(self, word, config):
    # Example: Fetch data from a source (e.g., API, database)
    # config is the full source dict from config.json
    # e.g. config["mapping"], config.get("config", {})

    if not word:
        return {}

    # Example: show user message
    if self.message_callback:
        self.message_callback(f"Fetching from MyFetcher: {word}")

    # ... your fetching logic ...

    if not data:
        return {}

    # Map to field indices
    result = {}
    for src_key, target_field in config.get("mapping", {}).items():
        if src_key in data and isinstance(target_field, (str, int)) and int(target_field) >= 0:
            result[int(target_field)] = data[src_key]

    return result
```
**Return**: A single dict `{field_index: value}` (not a list). QuickFill applies it directly.

### 5. Fetcher Registration (Automatic)

The process adding new fetchers to the `FetcherRegistry` is largely automated, provided that your class inherits `Fetcher`, is defined in the top level namespae of your module, and the source properly located in *`quickfill`*`/fetchers/` . 


- **File**: *`quickfill`*`/fetchers/__init__.py`
- **Purpose**: Iteraes over modules in *`quickfill`*`/fetchers/`, adding subclasses of `Fetcher` to `all_fetchers` that is read by the `FetcherRegistry` during initialization.

### 6. Update `config.json`

Configure the fetcher in `config.json` to specify its source and field mappings for a given model and deck.

```json
{
  "models": {
    "Note Type": [
      {
        "name": "My Source",
        "fetcher": "my_fetcher",
        "source_field": 0,
        "mapping": {
          "definition": 1,
          "example": 2,
          "word": 0
        },
        "config": {
          "api_key": "abc123"
        }
      }
    ]
  }
}
```

### 7. Testing

You may create a standalone test script to test and run your fetcher outside of
Anki, making it easier to debug. Below is a sample script that tests the
`cambridge_en_tc` fetcher. It should be placed in the top level directory of the
repo.

```python
#!/usr/bin/env python3 -B
import os
import sys

sys.path.append(os.path.abspath(os.path.dirname(__file__)) + '/src')

import quickfill
from quickfill.fetchers import CambridgeECFetcher
from pprint import pprint


if __name__ == "__main__":
    fetcher = CambridgeECFetcher()
    word = "memorize"
    cfg = {
        "name": "cambridge_en_tc",
        "config": {
            "parser": "html.parser",
        },
        "mapping": {
            "word": 0,
            "pronunciation": 1,
            "pos": 2,
            "inflections": 3,
            "def_zh": 4,
            "examples": 5,
        },
    }
    result = fetcher.fetch(word, cfg)
    pprint(result)
```

### 8. Best Practices

- Return `{}` on error or no data (never `None` or `[]`)
- Use `self.message_callback` for user-facing messages
- **Logging**: Add `print` or logging statements with `Debug:` prefix for troubleshooting.
- Use field **indices** in `mapping` — currently only numeric indices are supported
- **Config Flexibility**: Allow `config` to include source-specific settings (e.g., file paths, API keys).
- **Field Mapping**: Ensure `field_map` in `config.json` matches the data structure of your source.
- Keep fetchers fast — they block the UI

### 9. File Locations

- **Fetcher File**: *`quickfill`*`/fetchers/my_fetcher.py`
- **Base class**: `quickfill/fetchers/base_fetcher.py`
- **Config**: *`quickfill`*`/config.json`
- **Anki Add-on Directory**: The add-on folder is typically located at `~/.local/share/Anki2/addons21/`*`quickfill`*`/` on Linux, where *`quickfill`* is either the folder name or a numeric ID (e.g., **`834079017`**
) if installed via the Anki add-on website.


## Conclusion

Creating a new fetcher is simple:
1. Inherit from `Fetcher`
2. Implement `source_name()` and `fetch()`
3. Return a dict mapping field indices → values
4. Drop the file in `fetchers/`

No manual registration needed. Works instantly after restart.
