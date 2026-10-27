# **QuickFill Configuration Guide** (`config.json`)

This file documents how to **define and configure the sources** that
**QuickFill** uses to fill note fields.

## Configuration Structure

Multiple sources can be defined per note type (aka model). The user selects a
source for the current note type via the dropdown arrow button.


**File location**: Add-on root → `config.json`  
**Edit via**: `Tools → Add-ons → QuickFill → Config`

---

### Top-Level Structure

```json
{
  "models": {
    "Note Type Name": [
      { ...source 1... },
      { ...source 2... },
      { ...source 3... }
    ],
    "Another Note Type": [
      { ... }
    ]
  }
}
```

Each **key** under `"models"` must exactly match an Anki note type name (case-sensitive).

Each **value** is a **list** of source configurations available for that note type.

---
### Source element Structure

```json
{
  "name": " ... ",
  "fetcher": "fetcher",
  "source_field": 0,
  "config": { ...  },
  "mapping": { ...  }
}

```

### Source Configuration Fields

| Field            | Type       | Required? | Description |
|------------------|------------|-----------|-------------|
| `name`           | `str`      | Optional  | Friendly name shown in dropdown (defaults to fetcher name) |
| `fetcher`        | `str`      | Yes       | Fetcher identifier (e.g., `"local_csv"`, `"cambridge_en_tc"`, `"yahoo_en_tc"`) |
| `source_field`   | `int` | Optional | Field index containing the word to look up. Indexing starts from `0`. |
| `mapping`        | `dict`     | Yes       | Maps fetcher output keys → target field **indices**<br>Example: `"definition": 1` |
| `config`         | `dict`     | Optional  | Fetcher-specific settings (API keys, CSV path, language, etc.) |

---

### Example `config.json` (Current Format)

```json
{
  "models": {
    "ESL Vocabulary": [
      {
        "config": {
          "parser": "html.parser"
        },  
        "fetcher": "cambridge_en_tc",
        "mapping": {
          "def_zh": 6,
          "examples": 7,
          "inflections": 3,
          "pos": -1, 
          "pronunciation": 1,
          "word": 0
        },
        "name": "Cambridge EC",
        "source_field": 0
      },

      {
        "config": {
          "csv_path": "/path/to/your/csv",
          "csv_search_field": "word",
          "csv_sorted": true,
          "delimiter": ","
        },
        "fetcher": "local_csv",
        "mapping": {
          "exchanges": 3,
          "frq": 10,
          "phonetic": 1,
          "pos": 8,
          "translation": 6,
          "word": 0
        },
        "name": "EC - Local CSV",
        "source_field": 0
      }
    ],
    "Another note type": [
      {
        "config": {
          "parser": "html.parser"
        },
        "fetcher": "yahoo_en_tc",
        "mapping": {
          "def_zh": 6,
          "examples": 7,
          "inflections": 3,
          "pos": -1,
          "pronunciation": 1,
          "word": 0
        },
        "name": "Yahoo EC",
        "source_field": 0
      }
    ],
    "Basic": [
      {
        "name": "My Dictionary - Local CSV",
        "source_field": 0
        "config": {
          "csv_path": "/path/to/your/csv",
          "csv_search_field": "word",
          "csv_sorted": true,
          "delimiter": ","
        },
        "fetcher": "local_csv",
        "mapping": {
          "definition": 1,
          "word": 0
        },
      },
    ]
  }
}

```

---

### Key Changes from Old Format

| Old (pre-v1.3)              | New (current)                     |
|------------------------------------|---------------------------------------|
| Nested `"decks"` under models  | Removed — now model-only |
| Single source per model-deck   | Multiple sources per model |
| `"source"` field               | Now called `"fetcher"`               |
| `field_mappings`               | Unified into `"mapping"`   |

---

### Supported Fetchers (built-in)

| Fetcher           | `fetcher` value       | Common `config` keys                     |
|-------------------|-----------------------|------------------------------------------|
| Cambridge EC Dictionary | `cambridge_en_tc` | |
| Yahoo EC Dictionary     | `yahoo_en_tc`     | |
| Oxford Learner's Dictionaries | `oxford`    | `"dictionary"`, `"accent"`, `"max_definitions"`, `"max_examples_per_sense"`, `"include_extra_examples"`, `"include_grammar"`, `"homographs"` |
| Local CSV               | `local_csv`       | `"csv_path"`, `"delimiter"`, `"csv_sorted"` |

See [`FETCHERS.md`](./FETCHERS.md) for creating custom fetchers.

---

### Tips

- The **first source** in the list is selected by default.
- Selected source is remembered per note type (session-only).
- Reload add-on after config changes.

#### Oxford example

```json
{
  "name": "Oxford",
  "fetcher": "oxford",
  "source_field": 0,
  "mapping": {
    "word": 0, "pronunciation": 1, "definition": 2, "examples": 3,
    "inflections": 4, "pos": 5, "etymology": 6, "cefr": -1
  },
  "config": {
    "accent": "both",
    "max_examples_per_sense": 2,
    "include_extra_examples": false,
    "homographs": true
  }
}
```

`mapping` keys: `word`, `pos`, `pronunciation`, `inflections`, `definition`,
`examples`, `etymology`, `cefr` (use `-1` to skip a key). `dictionary` may be
`"english"` (default, OALD) or `"american_english"`.

Words with several numbered entries (e.g. `recreation_1` "re-creation" and
`recreation_2` "leisure") are fetched and **merged automatically**:
definitions are numbered continuously, pronunciations / examples / word
origin are combined, and definitions get a part-of-speech tag only if the
entries differ in POS. Set `"homographs": false` to read only the first
entry, or an integer to cap how many extra entries are merged (default 5).
Each extra entry costs one more request.
