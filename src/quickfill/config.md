# **QuickFill Configuration Guide** (`config.json`)  

---

## Purpose of `config.json`
This file defines **how QuickFill behaves per Anki note type (model) and deck pair**. It enables **fine-grained control**:
- **Per model-deck**: Different sources (e.g., Yahoo online vs. local CSV) and field mappings for the same note type in different decks.
- Which **fields** receive data
- Which **source** (fetcher) to use
- Global defaults for shared settings

> **File Location**: Root of the add-on (`QuickFillAddon/config.json`)  
> **Editable via**: `Tools → Add-ons → QuickFill → Config` (GUI) **or directly in JSON**  
> **Key Insight**: Configurations are **model-deck specific** via nested `"decks"` under each model. This allows overriding per deck without duplicating model setups.

---

## Top-Level Structure

```json
{
  "models": { ... },
  "parser": "html.parser"
}
```

| Field | Type | Required | Description |
|------|------|----------|-------------|
| `models` | dict | Yes | **Per-model** rules, each with nested **decks** for overrides |
| `parser` | str | No | Default HTML parser for online sources (`"html.parser"` or `"lxml"`) |


---

## 1. `models` — Per Model (with Deck Subsections)

Each **top-level key** = **Anki note type name** (exact match, case-sensitive).  
Under each model: **`"decks"` dict** for deck-specific overrides.  
- If no deck match: Falls back to model defaults (if any) or global `default_note_type`.
- Decks apply to **any deck using that model**.

```json
"models": {
  "ESL Vocabulary": {
    "decks": {
      "Default": {
        "source": "local_csv",
        "source_field": 0,
        "csv_path": "/path/to/dictionary.csv",
        "csv_search_field": "term",
        "csv_sorted": true,
        "delimiter": "\t",
        "csv_field_mappings": {
          "term": 0,
          "definitions": 6,
          "examples": 7
        }
      },
      "English to Chinese Deck": {
        "source": "yahoo_en_tc",
        "source_field": 0,
        "field_mappings": {
          "word": 0,
          "pronunciation": 1,
          "pos": 2,
          "def_zh": 6
        }
      }
    }
  }
}
```

### Model-Level Fields (Optional Defaults)
- `decks`: dict — **Required for per-deck config**. Keys = exact deck names (e.g., `"Default"`, `"EC CSV"`).

### Deck Config Fields (Per Model-Deck Pair)

| Field | Type | Required | Description |
|------|------|----------|-------------|
| `source` | str | Yes | Source type (e.g., `"local_csv"`, `"yahoo_en_tc"`) |
| `source_field` | int/str | Yes | Index/name of field with the **word to look up** (e.g., `0` or `"Word"`) |
| `field_mappings` | dict | Conditional | For online/non-CSV: `target_field` → `data_key` (e.g., `"def_zh": "definition"`) |
| `csv_field_mappings` | dict | Conditional (CSV only) | For `"local_csv"`: `target_key` → column index (e.g., `"definitions": 6`) |
| `csv_path` | str | Conditional (CSV only) | **Absolute path** to CSV file (relative to Anki addons dir often used) |
| `csv_search_field` | str | Conditional (CSV only) | Column key to search (e.g., `"term"`, `"word"`) |
| `csv_sorted` | bool | No | Enable binary search (requires sorted CSV by search field) |
| `delimiter` | str | No | CSV separator (default: `"\t"`) |
| `fallback` | str | No | Fallback source if primary fails |
| `enabled` | bool | `true` | Disable this deck config |
| `options` | dict | No | Source-specific (e.g., Yahoo `timeout`, CSV `encoding`) |

> **CSV vs. Online**:
> - `"local_csv"`: Uses `csv_field_mappings`, `csv_path`, etc.
> - `"yahoo_en_tc"`: Uses `field_mappings` for normalized data keys.
> 
> **Source**: `fetchers/csv_fetcher.py` for CSV opts; `yahoo.py` for online. Loaded in `__init__.py` via `config.get(model).get(deck)`.

---

## Supported Sources (via `"source"`)

| Source | Module | Use Case | Key Options |
|--------|--------|---------|-------------|
| `"local_csv"` | `fetchers/csv_fetcher.py` | Offline CSV lookup (binary search if sorted) | `csv_path` (abs path), `delimiter`, `csv_sorted`, `encoding` (default UTF-8), `case_sensitive` (default false) |
| `"yahoo_en_tc"` | `fetchers/yahoo.py` | Online: Yahoo Dict TW (Eng → Trad Chinese) | `base_url` (default TW), `timeout` (default 10s), `headers`, `retry` |

> **Custom Sources**: Add via `fetchers/my_source.py` → use `"source": "my_source"`.

---

## Data Keys (Standardized Output)

Sources return a dict for mapping:

| Key | Type | Example |
|-----|------|--------|
| `word` | str | `"hello"` |
| `pronunciation` | str | `"/həˈloʊ/"` |
| `pos` | str | `"noun"` |
| `definition` / `def_zh` | str | `"A greeting... (ZH: 問候)"` |
| `examples` | str/list | `"Hello, world!"` |
| `inflections` | list[str] | `["hellos"]` |
| `notes` / `other` | str | `"Etymology: Old English"` |
| `exchanges` / `frq` | str/num | `"Frequency: 1500"` (CSV-specific) |

> **Source**: `BaseFetcher.normalize()` in `fetchers/__init__.py`.

---

## Global Options

| Option | Default | Notes |
|-------|--------|------|
| `parser` | `"html.parser"` | For Yahoo; `"lxml"` faster if installed |


---

## Creating a Custom Source

See [`FETCHERS.md`](https://github.com/moltencrux/QuickFill/blob/dev/testing/FETCHERS.md).

**Steps**:
1. Add `fetchers/my_source.py` inheriting `BaseFetcher`.
2. Implement `fetch(word)` → normalized dict.
3. Use `"source": "my_source"` in deck config.

---

## Example: Full `config.json`

```json
{
  "parser": "html.parser",

  "models": {
    "ESL Vocabulary": {
      "decks": {
        "Default": {
          "source": "local_csv",
          "source_field": 0,
          "csv_path": "/home/agc/.var/app/net.ankiweb.Anki/data/Anki2/addons21/quickfill/data/dictionary.csv",
          "csv_search_field": "term",
          "csv_sorted": true,
          "delimiter": "\t",
          "csv_field_mappings": {
            "definitions": 6,
            "examples": 7,
            "notes": 8,
            "other": -1,
            "term": 0
          },
          "transform": {
            "definitions": "clean_html"
          }
        },
        "Default EC": {
          "source": "yahoo_en_tc",
          "source_field": 0,
          "field_mappings": {
            "def_zh": 6,
            "examples": 7,
            "inflections": 3,
            "pos": 2,
            "pronunciation": 1,
            "word": 0
          }
        },
        "EC CSV": {
          "source": "local_csv",
          "source_field": 0,
          "csv_path": "/home/agc/.var/app/net.ankiweb.Anki/data/Anki2/addons21/quickfill/data/ecdict_trad.csv",
          "csv_search_field": "word",
          "csv_sorted": true,
          "delimiter": ",",
          "csv_field_mappings": {
            "exchanges": 3,
            "frq": 10,
            "phonetic": 1,
            "pos": 8,
            "translation": 6,
            "word": 0
          }
        }
      }
    }
  }
}
```

---

## Validation Tips

- **Deck/Note names**: Exact match from Anki (case-sensitive).
- **Paths**: Absolute for CSVs (e.g., Anki's `addons21/` dir).
- **`source_field`**: Must match a valid field index/name.
- Use **JSON validator**; test in Anki GUI.
- Sorted CSVs: Ensure **ascending by search field** for binary search.

---

## Reload Config

After edits:
1. **Restart Anki** or
2. **QuickFill → Reload Config** (via GUI menu).

---

