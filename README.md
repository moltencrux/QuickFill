# QuickFill – Smart Dictionary Autofill for Anki

**QuickFill** is an extensible **Anki add-on** that fills note fields with dictionary data (pronunciation, definitions, examples, inflections, audio, and more) from configurable sources — online dictionaries or local CSV — with one click in the editor.

No more copy-pasting. No more manual formatting.

---

## Features

- **One-click lookup** in the Add/Edit dialog (button or `Ctrl+Shift+F`)
- **Per–note-type** sources and field mapping (several sources per model)
- **Built-in sources**: Cambridge (EN→ZH / EN→JA), Yahoo (EN→ZH), Oxford Learner’s, Merriam-Webster (collegiate + kids), local CSV
- **Audio**: download region-specific MP3s into the collection as `[sound:…]` tags
- **Stem masking**: optionally hide the headword in example/definition fields
- **Bulk fill**: Browser → Edit → “QuickFill in bulk…” for selected notes
- **Config GUI**: overview + row editor (`Tools → Add-ons → QuickFill → Config`)
- **Pluggable fetchers** — add your own (see [`FETCHERS.md`](FETCHERS.md))

---

## Supported Sources

| Source | `fetcher` id | Notes |
|--------|--------------|--------|
| **Cambridge EC** | `cambridge_en_tc` | English → Traditional Chinese |
| **Cambridge EJ** | `cambridge_en_ja` | English → Japanese |
| **Yahoo Dictionary (Taiwan)** | `yahoo_en_tc` | English → Traditional Chinese |
| **Oxford Learner’s Dictionaries** | `oxford` | EN definitions, BrE/NAmE audio, verb forms, CEFR, etymology |
| **Merriam-Webster** | `mw` | Collegiate; headword + related-form audio |
| **Merriam-Webster Kids** | `mw_kids` | Learner-oriented MW edition |
| **Local CSV** | `local_csv` | Configurable path, delimiter, search column; binary search when sorted |
| *(Custom)* | your `source_name()` | See [`FETCHERS.md`](FETCHERS.md) |

---

## Installation

### AnkiWeb

1. Tools → Add-ons → Get Add-ons  
2. Code **`834079017`**  
3. Restart Anki  

### Manual

1. Clone the repo:
   ```sh
   git clone https://github.com/moltencrux/QuickFill.git
   ```
2. Copy the **add-on package** (`src/quickfill/`) into your Anki `addons21` folder as `quickfill` (or keep the numeric id folder if replacing an existing install).

   Linux (non-Flatpak):
   ```sh
   cp -r src/quickfill ~/.local/share/Anki2/addons21/quickfill
   ```
   Linux (Flatpak):
   ```sh
   cp -r src/quickfill ~/.var/app/net.ankiweb.Anki/data/Anki2/addons21/quickfill
   ```
   Windows:
   ```cmd
   xcopy "src\quickfill" "%APPDATA%\Anki2\addons21\quickfill\" /E /Y /I
   ```
   macOS:
   ```sh
   mkdir -p ~/Library/Application\ Support/Anki2/addons21/quickfill
   cp -r src/quickfill/* ~/Library/Application\ Support/Anki2/addons21/quickfill/
   ```
3. Restart Anki.

Some sites use anti-bot challenges. When clearance is required, QuickFill can prompt to install optional Playwright / curl dependencies into the add-on user files; follow the on-screen prompt if it appears.

---

## Configuration

Configuration is **note-type (model) based**. Each model has a list of sources; the editor dropdown picks which one is active.

### Open config

- **GUI**: Tools → Add-ons → QuickFill → Config  
- **JSON**: same dialog’s raw editor, or the add-on’s `config.json`

Full field reference: [`src/quickfill/config.md`](src/quickfill/config.md).

### Minimal example

```json
{
  "models": {
    "Note Type": [
      {
        "name": "Cambridge EC",
        "fetcher": "cambridge_en_tc",
        "source_field": 0,
        "mapping": {
          "word": 0,
          "pronunciation": 1,
          "inflections": 3,
          "def_zh": 6,
          "examples": 7,
          "audio": 8
        },
        "config": {
          "parser": "html.parser",
          "audio_region": "us",
          "append_audio_to_pronunciation": false
        },
        "mask_fields": [7],
        "mask_mode": "tag",
        "mask_class": "qf-headword"
      },
      {
        "name": "Oxford",
        "fetcher": "oxford",
        "source_field": 0,
        "mapping": {
          "word": 0,
          "pronunciation": 1,
          "definition": 2,
          "examples": 3,
          "audio": 4
        },
        "config": {
          "dictionary": "english",
          "audio_region": "uk",
          "homographs": true
        }
      }
    ]
  }
}
```

### Source fields (summary)

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Optional | Label in the source dropdown |
| `fetcher` | Yes | Id from the table above (`source_name()`) |
| `source_field` | Optional | Field **index** of the lookup word (default `0`) |
| `mapping` | Yes | Fetcher output key → note field **index** (use `-1` to skip) |
| `config` | Optional | Fetcher-specific options (paths, `audio_region`, Oxford flags, …) |
| `mask_fields` / `mask_mode` / … | Optional | Stem-masking of the headword in chosen fields |

`mapping` values are **indices**, not field names. The GUI stores indices for you.

Audio keys (`audio`, `audio_us`, `audio_uk`, `audio_url`, …) and stem-mask options are documented in `config.md` and `FETCHERS.md`.

---

## Usage

1. Open **Add** or **Edit**.  
2. Type the word in the configured **source field**.  
3. Click the QuickFill button (dictionary icon) or press **`Ctrl+Shift+F`**.  
4. Use the adjacent dropdown to switch source for this note type.

**Bulk**: in the Browser, select notes → Edit → **QuickFill in bulk…**. Each note uses the current source for its model. If an anti-bot challenge appears, the bulk run stops and reuses the same install prompt as single-note fill.

---

## Creating New Fetchers

See the full guide: [**`FETCHERS.md`**](FETCHERS.md).

In short: subclass `Fetcher`, implement `source_name()`, `get_fields()`, and `fetch()`, return field-index → value plus optional `status` / `message` / `alternatives`, and (optionally) audio refs. Drop the module under `src/quickfill/fetchers/` — registration is automatic.

---

## Project Structure

```
QuickFill/
├── FETCHERS.md
├── README.md
├── LICENSE
├── src/
│   └── quickfill/          ← Anki add-on package
│       ├── __init__.py
│       ├── quickfill_addon.py
│       ├── base_fetcher.py
│       ├── fetcher.py
│       ├── audio_media.py
│       ├── config.json
│       ├── config.md
│       ├── config_gui.py
│       ├── stem_mask.py
│       ├── http_fetcher.py
│       ├── site_session.py
│       ├── fetchers/
│       │   ├── cambridge_*.py
│       │   ├── oxford.py
│       │   ├── mw*.py
│       │   ├── yahoo_scraper.py
│       │   └── csv_fetcher.py
│       └── images/
└── tests/
```

---

## Contributing

1. Fork the repo  
2. Branch from the relevant `dev/…` line of work  
3. Keep fetchers and docs in sync (`get_fields()`, return shape, audio)  
4. Open a pull request  

---

## License

**GNU General Public License v2.0** — see [`LICENSE`](LICENSE).

---

## Acknowledgments

Inspired by [AutoDefine](https://github.com/z1lc/AutoDefine).

**Made for language learners.**
