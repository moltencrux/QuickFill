# QuickFill Configuration Guide (`config.json`)

How to define sources that QuickFill uses to fill note fields.

**File location**: add-on package → `config.json`  
**Edit via**: Tools → Add-ons → QuickFill → Config (GUI overview + row editor, or raw JSON)

---

## Top-level structure

```json
{
  "models": {
    "Note Type Name": [
      { "...source 1..." },
      { "...source 2..." }
    ],
    "Another Note Type": [
      { "..." }
    ]
  }
}
```

- Each key under `"models"` must match an Anki note type name exactly (case-sensitive).
- Each value is a **list** of source configs for that note type.
- The first source is the default; the editor remembers the last choice per note type for the session.

---

## Source object

```json
{
  "name": "Friendly label",
  "fetcher": "cambridge_en_tc",
  "source_field": 0,
  "mapping": {
    "word": 0,
    "pronunciation": 1,
    "definition": 2
  },
  "config": { },
  "mask_fields": [2],
  "mask_mode": "tag"
}
```

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Optional | Label in the source dropdown (defaults to `fetcher`) |
| `fetcher` | string | Yes | Fetcher id (`source_name()`), see table below |
| `source_field` | int | Optional | Field **index** of the lookup word (default `0`) |
| `mapping` | object | Yes | Fetcher output key → target field **index**. Use `-1` to skip a key |
| `config` | object | Optional | Fetcher-specific options (paths, audio, Oxford flags, …) |
| `deck` | string | Optional | Stored by the GUI for display; fill path is still **model-only** |
| `mask_fields` | list[int] | Optional | Field indices to run headword stem-masking on |
| `mask_mode` | string | Optional | `"tag"` (default) or `"replace"` |
| `mask_tag` | string | Optional | HTML tag when `mask_mode` is `"tag"` (default `"span"`) |
| `mask_class` | string | Optional | CSS class when tagging (default `"qf-headword"`) |
| `mask_placeholder` | string | Optional | Replacement text when `mask_mode` is `"replace"` (default `"#$#"`) |

**Mapping values are indices**, not field names. The config GUI resolves names to indices when saving.

Composite identity of a source (uniqueness in the GUI) is effectively note type + display name + fetcher; keep `name` distinct when you have several rows for the same fetcher.

---

## Built-in fetchers

| Fetcher | `fetcher` value | Typical `config` keys |
|---------|-----------------|------------------------|
| Cambridge EC (EN→ZH-TW) | `cambridge_en_tc` | `parser`, `audio_region`, `append_audio_to_pronunciation`, `use_site_session` / `use_cloudscraper` |
| Cambridge EJ (EN→JA) | `cambridge_en_ja` | same family as Cambridge EC |
| Yahoo EC (EN→ZH-TW) | `yahoo_en_tc` | same family; HTML scrape |
| Oxford Learner’s | `oxford` | `dictionary`, `audio_region`, `max_definitions`, `max_examples_per_sense`, `include_extra_examples`, `include_grammar`, `homographs`, `append_audio_to_pronunciation` |
| Merriam-Webster | `mw` | `audio_region`, `append_audio_to_pronunciation`, session/clearance flags |
| Merriam-Webster Kids | `mw_kids` | same as `mw` |
| Local CSV | `local_csv` | `csv_path`, `csv_search_field`, `csv_sorted`, `delimiter` |

Custom fetchers: implement `source_name()` / `get_fields()` / `fetch()` and drop the module under `fetchers/` — see [`FETCHERS.md`](../../FETCHERS.md).

---

## Audio (shared)

Dictionary fetchers may expose these **mapping keys** (list only those you map):

| Key | Meaning |
|-----|---------|
| `audio` | Preferred-region audio → downloaded to `[sound:…]` |
| `audio_us` / `audio_uk` | Force US or UK |
| `audio_url` / `audio_us_url` / `audio_uk_url` | Remote URL string only (not downloaded) |
| `audio_inflections` | Related-form / run-on audio (e.g. MW *castability*), separate from headword `audio` |

Under the source’s **`config`** object:

| Key | Values | Default | Effect |
|-----|--------|---------|--------|
| `audio_region` | `"us"` \| `"uk"` \| `"all"` | `"us"` | Which region fills the generic `audio` key |
| `append_audio_to_pronunciation` | bool | false | Append resolved `[sound:…]` to the pronunciation field even if `audio` is not mapped |

Resolution runs in the registry after `fetch()` (needs the collection media API). Standalone fetcher tests see raw audio refs, not `[sound:]` tags.

---

## Stem masking

After a successful fill, optional masking rewrites chosen fields so the headword (and same-stem variants) is less obvious — useful in example sentences.

```json
"mask_fields": [6, 7],
"mask_mode": "tag",
"mask_tag": "span",
"mask_class": "qf-headword",
"mask_placeholder": "#$#"
```

- **`tag`**: wrap matches in `<span class="qf-headword">…</span>` (or your tag/class) for CSS styling on the card.
- **`replace`**: substitute `mask_placeholder` for matches.

Leave `mask_fields` empty or omit it to disable.

---

## Example: Cambridge + audio + mask

```json
{
  "name": "Cambridge EC",
  "fetcher": "cambridge_en_tc",
  "source_field": 0,
  "mapping": {
    "word": 0,
    "pronunciation": 1,
    "pos": -1,
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
}
```

---

## Example: Oxford

```json
{
  "name": "Oxford",
  "fetcher": "oxford",
  "source_field": 0,
  "mapping": {
    "word": 0,
    "pronunciation": 1,
    "definition": 2,
    "examples": 3,
    "inflections": 4,
    "pos": 5,
    "etymology": 6,
    "cefr": -1,
    "audio": 7
  },
  "config": {
    "dictionary": "english",
    "audio_region": "uk",
    "max_examples_per_sense": 2,
    "include_extra_examples": false,
    "homographs": true
  }
}
```

`mapping` keys for Oxford include: `word`, `pos`, `pronunciation`, `inflections`, `definition`, `examples`, `etymology`, `cefr`, plus the audio keys above.

- `dictionary`: `"english"` (default, OALD) or `"american_english"`.
- Homographs (e.g. `recreation_1` vs `recreation_2`) are merged by default: definitions numbered continuously, shared fields combined. Set `"homographs": false` for the first entry only, or an integer to cap extra entries (default 5). Each extra entry is another request.

---

## Example: Merriam-Webster

```json
{
  "name": "MW",
  "fetcher": "mw",
  "source_field": 0,
  "mapping": {
    "word": 0,
    "pos": 1,
    "pronunciation": 2,
    "definition": 3,
    "examples": 4,
    "audio": 5,
    "audio_inflections": 6
  },
  "config": {
    "audio_region": "us"
  }
}
```

Kids edition uses `"fetcher": "mw_kids"` with the same mapping/audio shape. Headword audio stays under `audio*`; related forms (uros / run-ons) go to `audio_inflections` so they are not mixed in.

---

## Example: Local CSV

```json
{
  "name": "EC - Local CSV",
  "fetcher": "local_csv",
  "source_field": 0,
  "mapping": {
    "word": 0,
    "phonetic": 1,
    "translation": 6,
    "pos": 8
  },
  "config": {
    "csv_path": "/path/to/your.csv",
    "csv_search_field": "word",
    "csv_sorted": true,
    "delimiter": ","
  }
}
```

Mapping keys are **CSV column names** (from the header). `get_fields()` for CSV returns `[]`, so the GUI leaves keys free-text. Set `csv_sorted` true only when the file is sorted on the search column (enables binary search).

---

## Format history (brief)

| Older | Current |
|-------|---------|
| Nested `"decks"` under models | Model-only list of sources (`deck` key is optional UI metadata) |
| Single source per model/deck | Multiple sources per model |
| `"source"` | `"fetcher"` |
| `field_mappings` / field **names** | `"mapping"` → field **indices** |

---

## Tips

- Prefer the **Config GUI** for mapping: it lists `get_fields()` for the selected fetcher and stores indices correctly.
- After editing raw JSON, restart the add-on or Anki so the registry reloads config.
- Empty or failed fetches should return meta (`status` / `message`); the UI surfaces “did you mean …?” when `alternatives` is present — see [`FETCHERS.md`](../../FETCHERS.md).
- Bulk fill uses the same per-model selected source as the editor.
