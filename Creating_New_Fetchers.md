# Creating New Fetchers for the QuickFill Add-on

This guide explains how to create new fetcher classes for the QuickFill add-on, which integrates with Anki (version 25.09.2) to populate note fields in the Add Cards dialog. Fetchers retrieve data from various sources (e.g., CSV files, APIs) and map it to Anki note fields based on the configuration in `config.json`. This document covers the structure of a fetcher, required methods, how to implement/overload them, and what they should return. Paths are relative to the add-on folder, referred to as `*quickfill*`, which may be a numeric string (e.g., `123456789`) if installed from the Anki add-on website.

## Overview

The QuickFill add-on uses a `Fetcher` base class (`base_fetcher.py`) that defines the interface for all fetchers. Subclasses like `CSVFetcher` and `YahooFetcher` implement specific data retrieval logic. The `FetcherRegistry` (`fetcher.py`) loads all fetchers listed in `fetchers/__init__.py` (in the `all_fetchers` list) and uses them to fetch data based on the `source` specified in `config.json`. Each fetcher must implement:

- A `source_name` static method to identify the fetcher.
- A `fetch` method to retrieve and format data.
- An `__init__` method that supports a `message_callback` for user notifications.

## Steps to Create a New Fetcher

### 1. Create the Fetcher Class

Create a new Python file in the `fetchers` directory of the add-on folder (e.g., `*quickfill*/fetchers/my_fetcher.py`). The class must inherit from `Fetcher` in `base_fetcher.py`.

```python
from .base_fetcher import Fetcher

class MyFetcher(Fetcher):
    def __init__(self, message_callback=None):
        super().__init__(message_callback)

    @staticmethod
    def source_name():
        pass

    def fetch(self, word, config):
        pass
```

- **File Location**: Place the file in `*quickfill*/fetchers/` (e.g., `*quickfill*/fetchers/my_fetcher.py`).
- **Class Name**: Use a descriptive name (e.g., `MyFetcher`) that reflects the data source.
- **Inheritance**: Inherit from `Fetcher` to ensure compatibility with `FetcherRegistry`.

### 2. Implement `__init__`

The `__init__` method must call the superclass (`Fetcher`) `__init__` to initialize the `message_callback`, which is used to display messages to the user (e.g., errors or warnings via `aqt.utils.showInfo`).

```python
def __init__(self, message_callback=None):
    super().__init__(message_callback)
```

- **Parameters**:
  - `message_callback`: A function (e.g., `showInfo`) to display messages to the user. It’s optional and defaults to `None`.
- **Purpose**: Stores `message_callback` as `self.message_callback` for use in `fetch` (e.g., to notify about missing data).
- **Example**:
  ```python
  if self.message_callback:
      self.message_callback(f"No data found for '{word}'")
  ```

### 3. Implement `source_name`

The `source_name` static method returns a unique string identifier for the fetcher, which matches the `source` field in `config.json`.

```python
@staticmethod
def source_name():
    return "my_source"
```

- **Return Value**: A string (e.g., `"my_source"`) that identifies the fetcher in `config.json`.
- **Usage**: The `FetcherRegistry` uses `source_name()` to map the fetcher to the `source` specified in `config.json` (e.g., `"source": "my_source"`).
- **Example**:
  - If `source_name()` returns `"my_source"`, the `config.json` should include:
    ```json
    "source": "my_source"
    ```

### 4. Implement `fetch`

The `fetch` method retrieves data for a given word and maps it to Anki note field indices based on the configuration. It’s the core method for data retrieval and processing.

```python
def fetch(self, word, config):
    # Example: Fetch data from a source (e.g., API, database)
    # Replace with actual data retrieval logic
    data = self._fetch_data(word, config)
    if not data:
        if self.message_callback:
            self.message_callback(f"No data found for '{word}' in MyFetcher")
        print(f"Debug: No data found for '{word}'")
        return []

    # Map data to note field indices
    field_mappings = config.get("my_field_mappings", {})
    data_list = []
    for item in data:
        mapped_data = {}
        for field_name, note_field_idx in field_mappings.items():
            if field_name in item and note_field_idx >= 0:
                mapped_data[note_field_idx] = item[field_name]
                print(f"Debug: Mapping {field_name} to note field {note_field_idx}: {item[field_name]}")
        data_list.append(mapped_data)
    print(f"Debug: MyFetcher fetched data for '{word}': {data_list}")
    return data_list
```

- **Parameters**:
  - `word`: The string to search for (e.g., `"memory"`), typically from the note’s source field (e.g., field 0).
  - `config`: A dictionary from `config.json` for the specific model and deck, containing:
    - Source-specific settings (e.g., API keys, file paths).
    - Field mappings (e.g., `my_field_mappings`).
- **Return Value**:
  - A list of dictionaries, where each dictionary maps note field indices (integers) to values (strings). For example:
    ```python
    [
        {0: "memory", 1: "'memәri", 6: "n. 記憶, 記憶力, 回憶, 紀念, 存儲\nn. 內存\n[計] 存儲器, 內存, 查看內存實用程序", 8: "", 10: "891"}
    ]
    ```
  - Each dictionary represents one set of field assignments for the note.
  - Invalid indices (e.g., `-1`) are ignored by `FetcherRegistry.fill_note`.
  - Return an empty list (`[]`) if no data is found.
- **Example**:
  - For a word `"memory"`, the fetcher might retrieve data from an API or database and return:
    ```python
    [
        {
            0: "memory",
            1: "'memәri",
            6: "n. 記憶, 記憶力, 回憶, 紀念, 存儲\nn. 內存\n[計] 存儲器, 內存, 查看內存實用程序",
            8: "",
            10: "891"
        }
    ]
    ```
- **Notes**:
  - Use `self.message_callback` to notify users of errors (e.g., missing data).
  - Log debug information with `print` statements for troubleshooting.
  - Access `config` for source-specific settings (e.g., `config.get("api_key")`).
  - Map fields using a configuration like `my_field_mappings` (similar to `csv_field_mappings`).

### 5. Register the Fetcher

Add the new fetcher class to the `all_fetchers` list in `fetchers/__init__.py` to ensure `FetcherRegistry` loads it.

```python
from .csv_fetcher import CSVFetcher
from .yahoo_fetcher import YahooFetcher
from .my_fetcher import MyFetcher

all_fetchers = [CSVFetcher, YahooFetcher, MyFetcher]
```

- **File**: `*quickfill*/fetchers/__init__.py`
- **Purpose**: The `FetcherRegistry` iterates over `all_fetchers` to instantiate fetchers during initialization.

### 6. Update `config.json`

Configure the fetcher in `config.json` to specify its source and field mappings for a given model and deck.

```json
{
  "models": {
    "ESL Vocabulary": {
      "decks": {
        "Default": {
          "source": "my_source",
          "source_field": 0,
          "my_field_mappings": {
            "term": 0,
            "definitions": 6,
            "notes": 8,
            "examples": 7
          },
          "api_key": "your_api_key_here"
        }
      }
    }
  }
}
```

- **File**: `*quickfill*/config.json`
- **Fields**:
  - `"source"`: Matches the `source_name()` return value (e.g., `"my_source"`).
  - `"source_field"`: The note field index (e.g., `0`) containing the input word.
  - `"my_field_mappings"`: Maps source field names to note field indices.
  - Additional fields (e.g., `"api_key"`): Source-specific settings for `fetch`.

### 7. Example Implementation: Dictionary API Fetcher

Below is a complete example of a fetcher that retrieves data from a hypothetical dictionary API.

```python
import requests
from .base_fetcher import Fetcher

class DictionaryAPIFetcher(Fetcher):
    def __init__(self, message_callback=None):
        super().__init__(message_callback)

    @staticmethod
    def source_name():
        return "dictionary_api"

    def fetch(self, word, config):
        api_key = config.get("api_key")
        api_url = config.get("api_url", "https://api.example.com/dictionary")
        if not api_key:
            if self.message_callback:
                self.message_callback("API key not provided in config")
            print("Debug: API key not provided")
            return []

        try:
            response = requests.get(f"{api_url}/{word}", headers={"Authorization": f"Bearer {api_key}"})
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            if self.message_callback:
                self.message_callback(f"Failed to fetch data for '{word}': {str(e)}")
            print(f"Debug: API request failed: {str(e)}")
            return []

        if not data.get("results"):
            if self.message_callback:
                self.message_callback(f"No data found for '{word}' in Dictionary API")
            print(f"Debug: No data found for '{word}'")
            return []

        field_mappings = config.get("api_field_mappings", {})
        data_list = []
        for item in data["results"]:
            mapped_data = {}
            for field_name, note_field_idx in field_mappings.items():
                if field_name in item and note_field_idx >= 0:
                    mapped_data[note_field_idx] = item[field_name]
                    print(f"Debug: Mapping {field_name} to note field {note_field_idx}: {item[field_name]}")
            data_list.append(mapped_data)
        print(f"Debug: DictionaryAPIFetcher fetched data for '{word}': {data_list}")
        return data_list
```

- **File**: `*quickfill*/fetchers/dictionary_api_fetcher.py`
- **Configuration in `config.json`**:
  ```json
  {
    "models": {
      "ESL Vocabulary": {
        "decks": {
          "Default": {
            "source": "dictionary_api",
            "source_field": 0,
            "api_url": "https://api.example.com/dictionary",
            "api_key": "your_api_key_here",
            "api_field_mappings": {
              "word": 0,
              "definition": 6,
              "example": 7,
              "note": 8
            }
          }
        }
      }
    }
  }
  ```

- **Register in `fetchers/__init__.py`**:
  ```python
  from .csv_fetcher import CSVFetcher
  from .yahoo_fetcher import YahooFetcher
  from .dictionary_api_fetcher import DictionaryAPIFetcher

  all_fetchers = [CSVFetcher, YahooFetcher, DictionaryAPIFetcher]
  ```

### 8. Testing the New Fetcher

1. **Standalone Test**:
   ```bash
   cd *quickfill*
   python3 -c "from quickfill import fetchers; print('Fetcher import successful', fetchers.all_fetchers)"
   python3 -c "from quickfill.fetchers.my_fetcher import MyFetcher; f = MyFetcher(message_callback=print); config = {'my_field_mappings': {'term': 0, 'definitions': 6, 'notes': 8, 'examples': 7}}; print(f.fetch('memory', config))"
   ```
   Expected (for `DictionaryAPIFetcher`):
   ```plaintext
   Fetcher import successful [<class 'quickfill.fetchers.csv_fetcher.CSVFetcher'>, <class 'quickfill.fetchers.yahoo_fetcher.YahooFetcher'>, <class 'quickfill.fetchers.dictionary_api_fetcher.DictionaryAPIFetcher'>]
   Debug: DictionaryAPIFetcher fetched data for 'memory': [{0: 'memory', 6: 'definition text', 7: 'example text', 8: 'note text'}]
   ```

2. **Anki Test**:
   - Restart Anki.
   - Open Add Cards, select `ESL Vocabulary`, `Default` deck.
   - Enter `memory` in field 0.
   - Click "QuickFill" or press `Ctrl+Alt+E`.
   - Verify fields are populated (e.g., fields 0, 6, 7, 8).
   - Check `Tools > Add-ons > View Log`:
     - `Debug: Registered fetchers: ['local_csv', 'yahoo', 'dictionary_api']`
     - `Debug: DictionaryAPIFetcher fetched data for 'memory': [...]`
     - `Debug: Editor refreshed with loadNoteKeepingFocus`

3. **Debugging**:
   - If the fetcher fails:
     ```bash
     python3 -c "from quickfill.fetcher import FetcherRegistry; from aqt.utils import showInfo; registry = FetcherRegistry(); registry.load_fetchers()"
     ```
   - Share logs from `Tools > Add-ons > View Log`.

### 9. Best Practices

- **Error Handling**: Use `try-except` in `fetch` to handle source-specific errors (e.g., network issues, invalid data).
- **Logging**: Add `print` statements with `Debug:` prefix for troubleshooting.
- **Config Flexibility**: Allow `config` to include source-specific settings (e.g., file paths, API keys).
- **Field Mapping**: Ensure `field_mappings` in `config.json` matches the data structure of your source.
- **Testing**: Test standalone with `python3 -c` commands before integrating with Anki.

### 10. File Locations

- **Fetcher File**: `*quickfill*/fetchers/my_fetcher.py`
- **Registration**: `*quickfill*/fetchers/__init__.py`
- **Config**: `*quickfill*/config.json`
- **Anki Add-on Directory**: The add-on folder is typically located at `~/.local/share/Anki2/addons21/*quickfill*/` on Linux, where `*quickfill*` is either the folder name or a numeric ID (e.g., `123456789`) if installed via the Anki add-on website.

### 11. Example Config for Multiple Fetchers

To use multiple fetchers for different decks or models, update `config.json`:

```json
{
  "models": {
    "ESL Vocabulary": {
      "decks": {
        "Default": {
          "source": "local_csv",
          "csv_path": "/path/to/your/dictionary.csv",
          "csv_sorted": true,
          "delimiter": "\t",
          "csv_search_field": "term",
          "source_field": 0,
          "csv_field_mappings": {
            "term": 0,
            "definitions": 6,
            "notes": 8,
            "examples": 7,
            "other": -1
          }
        },
        "API Deck": {
          "source": "dictionary_api",
          "source_field": 0,
          "api_url": "https://api.example.com/dictionary",
          "api_key": "your_api_key_here",
          "api_field_mappings": {
            "word": 0,
            "definition": 6,
            "example": 7,
            "note": 8
          }
        }
      }
    }
  }
}
```

- **Note**: Replace `/path/to/your/dictionary.csv` with the actual path to your CSV file.

## Conclusion

Creating a new fetcher involves defining a class that inherits from `Fetcher`, implementing `__init__`, `source_name`, and `fetch`, and registering it in `fetchers/__init__.py`. The `fetch` method must return a list of dictionaries mapping note field indices to values, using `config` for settings and `message_callback` for user notifications. Follow the example of `DictionaryAPIFetcher` for a robust implementation, and test thoroughly both standalone and within Anki.