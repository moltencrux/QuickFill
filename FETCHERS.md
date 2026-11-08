# Creating New Fetchers for the QuickFill Add-on

This guide explains how to create new fetcher classes for the QuickFill add-on, which integrates with Anki (version 25.09.2+) to populate note fields in the Add Cards dialog. Fetchers retrieve data from various sources (e.g., CSV files, web dictionaries) and map it to Anki note fields based on the configuration in `config.json`.

## Overview

The QuickFill add-on uses a `Fetcher` base class (`base_fetcher.py`) that defines the interface for all fetchers. Concrete classes (e.g. `CSVFetcher`, `YahooFetcher`, Cambridge / MW / Oxford subclasses) implement data retrieval. The `FetcherRegistry` (`fetcher.py`) loads every subclass of `Fetcher` found under `fetchers/` and dispatches by the `fetcher` key in `config.json`.

Each fetcher must implement:

- `source_name()` — **static** method; unique string id matching `config.json`
- `get_fields()` — **class** method; ordered list of mapping keys this fetcher can produce
- `fetch(word, config)` — instance method; retrieve data and return a result dict
- `__init__` — optional; call `super().__init__(message_callback)` if you override it

## Steps to Create a New Fetcher

### 1. Create the Fetcher Class

Create a new Python file in `src/quickfill/fetchers/` (e.g. `my_fetcher.py`). The class must inherit from `Fetcher` in `base_fetcher.py`.

```python
from .. import Fetcher

class MyFetcher(Fetcher):
    def __init__(self, message_callback=None):
        super().__init__(message_callback)

    @staticmethod
    def source_name():
        return "my_fetcher"

    @classmethod
    def get_fields(cls):
        return [
            "word",
            "definition",
            "example",
            # include audio keys if your source provides them:
            # "audio", "audio_us", "audio_uk", "audio_url",
        ]

    def fetch(self, word, config):
        # Your logic here
        return {}  # see "Return value of fetch()" below
```

- **File location**: `src/quickfill/fetchers/my_fetcher.py`
- **Inheritance**: subclass `Fetcher` so automatic registration works

### 2. Implement `__init__` (Optional)

You can omit `__init__` in many cases. If you override it, call `super().__init__(message_callback)` so `self.message_callback` is set. That callback is used for user-facing messages (errors, warnings). Prefer returning structured meta (below) over relying on the callback alone; the registry also routes `message_callback` through a thread-safe sink when running inside `QueryOp`.

```python
def __init__(self, message_callback=None):
    super().__init__(message_callback)
```

### 3. Implement `source_name()` (Required)

Static method returning the unique string id used as `"fetcher"` in `config.json`.

```python
@staticmethod
def source_name():
    return "my_fetcher"
```

### 4. Implement `get_fields()` (Required)

Class method returning the **stable, ordered** list of mapping keys this fetcher can produce. These are the strings used as keys in a source’s `mapping` dict (`output key → note field index`). The config GUI calls `get_fields()` to populate the field-mapping dropdown.

```python
@classmethod
def get_fields(cls):
    return [
        "word",
        "pos",
        "pronunciation",
        "definition",
        "examples",
        "audio",
        "audio_us",
        "audio_uk",
        "audio_url",
    ]
```

Notes:

- Keys should match what `fetch()` actually puts into its intermediate payload before applying `mapping`.
- For sources with a dynamic schema (e.g. CSV column names), return `[]`. The GUI then leaves the mapping key editable as free text.
- Audio-related reserved keys are documented in the Audio section below; list any you support so they appear in the GUI.

### 5. Implement `fetch()` (Required)

```python
def fetch(self, word, config):
    # config is the full source entry from config.json
    # e.g. config["mapping"], config.get("config", {}), config.get("source_field"), ...
    ...
```

#### Return value of `fetch()`

Return a **single dict**. Keys are either:

1. **Integer field indices** — values written into the note (`{0: "…", 1: "…"}`).
2. **String meta keys** — never written as fields; consumed by the registry:

| Meta key        | Purpose |
|-----------------|---------|
| `status`        | `"ok"` \| `"not_found"` \| `"error"` (optional). Empty field map with no status is treated as not found. |
| `message`       | Human-readable explanation (shown on not-found / error). |
| `alternatives`  | Optional list of suggested spellings / related terms (surfaced as “did you mean …?”). |

`FetcherRegistry.split_fetch_result()` separates int keys (fields) from the meta keys above before writing the note. Unknown non-int keys are ignored (except the internal audio-append marker; see Audio).

**Success example** (after applying `mapping`):

```python
return {
    0: "memorize",
    1: "/ˈmem.ə.raɪz/",
    2: "to learn by heart",
    "status": "ok",  # optional
}
```

**Not found**:

```python
return {
    "status": "not_found",
    "message": f"No entry for '{word}'",
    "alternatives": ["memorise", "memory"],  # optional
}
```

**Error**:

```python
return {
    "status": "error",
    "message": f"Network error: {exc}",
}
```

Typical pattern inside a dictionary fetcher:

```python
def fetch(self, word, config):
    if not word:
        return {}

    field_map = config.get("mapping", {})
    # ... retrieve + parse into a name→value payload ...
    value_by_key = {
        "word": word,
        "definition": definition,
        "examples": examples,
        **audio_payload,  # see Audio
    }

    data = {}
    for key, idx in field_map.items():
        if not isinstance(idx, int) or idx < 0:
            continue
        data[idx] = value_by_key.get(key, "")

    if not any(data.values()):
        msg = f"No data for '{word}'"
        self.message_callback(msg)
        return {"status": "not_found", "message": msg}

    return data
```

Return `{}` (or a meta-only dict) on failure — never `None` or a list.

### 6. Audio (optional but recommended for dictionary sources)

Fetchers do **not** download media themselves. They return **audio refs**; the registry calls `resolve_audio_in_result()` (in `audio_media.py`) on the background thread and turns refs into `[sound:filename]` tags written via `col.media.write_data`.

#### Reserved mapping keys

| Key                 | Meaning |
|---------------------|---------|
| `audio`             | Preferred-region audio (respects config `audio_region`) |
| `audio_us`          | US pronunciation only |
| `audio_uk`          | UK / GB pronunciation only |
| `audio_url`         | Remote URL string, **not** downloaded |
| `audio_us_url` / `audio_uk_url` | Region-specific URL strings (not downloaded) |
| `audio_inflections` | Related-form / run-on audio (e.g. MW *castability*); kept separate from headword `audio` |

#### Config (under the source’s `config` object)

- `audio_region`: `"us"` | `"uk"` | `"all"` (default `"us"`) — which region fills the generic `audio` key
- `append_audio_to_pronunciation`: bool — if true, append resolved `[sound:…]` tags to the pronunciation field even when `audio` is not mapped to its own field

#### Building refs

Prefer the helpers in `audio_media.py`:

```python
from ..audio_media import audio_ref, build_region_audio_payload, AUDIO_APPEND_META

# Single ref
ref = audio_ref("https://example.com/word_us.mp3", filename="qf_word_us.mp3")

# Or from a region → [url, …] map (used by Cambridge / Oxford / MW):
urls_by_region = {"us": ["https://…/us.mp3"], "uk": ["https://…/uk.mp3"]}
audio_payload = build_region_audio_payload(
    urls_by_region,
    region_pref=(config.get("config") or {}).get("audio_region", "us"),
    word=word,
)
# → may contain audio, audio_us, audio_uk, audio_url, audio_us_url, audio_uk_url

value_by_key = { ..., **audio_payload }

# So append-to-pronunciation still works when the user did not map `audio`:
if audio_payload.get("audio"):
    data[AUDIO_APPEND_META] = audio_payload["audio"]
```

An audio ref is a dict:

```python
{
    "__qf_audio__": True,
    "url": "https://…/word.mp3",
    "filename": "optional_preferred_name.mp3",  # basename only
}
```

or a list of such dicts. Plain `http(s)` URL strings that look like media (`.mp3`, `.ogg`, …) are also accepted.

Include the audio keys you support in `get_fields()` so the config GUI offers them.

### 7. Fetcher Registration (Automatic)

No manual list edit is required. `fetchers/__init__.py` imports modules under `fetchers/` and collects subclasses of `Fetcher` into `all_fetchers`, which `FetcherRegistry` loads at startup.

Requirements:

- Class inherits `Fetcher`
- Defined at module top level
- File lives under `src/quickfill/fetchers/`

### 8. Update `config.json`

```json
{
  "models": {
    "Note Type": [
      {
        "name": "My Source",
        "fetcher": "my_fetcher",
        "source_field": 0,
        "mapping": {
          "word": 0,
          "definition": 1,
          "example": 2,
          "audio": 3
        },
        "config": {
          "api_key": "abc123",
          "audio_region": "us",
          "append_audio_to_pronunciation": true
        }
      }
    ]
  }
}
```

`mapping` values are **field indices** (integers). The config GUI stores them that way.

### 9. Testing

Standalone script (repo root) is useful for debugging outside Anki:

```python
#!/usr/bin/env python3 -B
import os
import sys

sys.path.append(os.path.abspath(os.path.dirname(__file__)) + "/src")

from pprint import pprint
from quickfill.fetchers.cambridge_ec import CambridgeECFetcher

if __name__ == "__main__":
    fetcher = CambridgeECFetcher()
    word = "memorize"
    cfg = {
        "name": "cambridge_en_tc",
        "config": {
            "parser": "html.parser",
            "audio_region": "us",
        },
        "mapping": {
            "word": 0,
            "pronunciation": 1,
            "pos": 2,
            "inflections": 3,
            "def_zh": 4,
            "examples": 5,
            "audio": 6,
        },
    }
    result = fetcher.fetch(word, cfg)
    pprint(result)
```

Note: audio refs are resolved only inside Anki (needs `col.media`). In a standalone run you will see the raw ref dicts / URLs.

### 10. Best Practices

- Implement `get_fields()` with every key you document for the GUI
- On miss / failure return meta (`status` + `message`, optional `alternatives`), not only `{}`
- Never return `None` or a list from `fetch()`
- Use `self.message_callback` for progressive status if needed; prefer structured meta for the final outcome
- Keep mapping values as **integer** field indices
- Put source-specific options under `config["config"]`
- Prefer `build_region_audio_payload` / `audio_ref` over ad-hoc audio structures
- Keep fetchers reasonably fast — they run on a background thread but still affect perceived latency
- Prefix debug prints with `Debug:` when useful

### 11. File Locations

| What | Path |
|------|------|
| Fetcher modules | `src/quickfill/fetchers/*.py` |
| Base class | `src/quickfill/base_fetcher.py` |
| Registry / `split_fetch_result` | `src/quickfill/fetcher.py` |
| Audio helpers | `src/quickfill/audio_media.py` |
| Default config | `src/quickfill/config.json` |
| HTTP / site session helpers | `src/quickfill/http_fetcher.py`, `site_session.py` |

Anki add-on directory (after install) is typically under `addons21/` (folder name or numeric id such as **`834079017`**).

## Conclusion

1. Inherit from `Fetcher`
2. Implement `source_name()`, `get_fields()`, and `fetch()`
3. Return a dict of field-index → value, plus optional `status` / `message` / `alternatives`
4. For audio, return refs (or use `build_region_audio_payload`) and list the keys in `get_fields()`
5. Drop the file in `fetchers/` — registration is automatic after restart
