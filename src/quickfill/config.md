# QuickFill Dictionary Autofill Configuration

Open `Tools > Add-ons > Yahoo Dictionary Autofill > Config` to adjust settings.

## Options
- `NOTE_TYPE`: (string, default: "YahooDictionary") - Name of the note type to use or create when `USE_DEFAULT_TEMPLATE` is true. Includes fields: Word, Pronunciation, POS, Inflections, Definition_ZH, Examples.
- `USE_DEFAULT_TEMPLATE`: (boolean, default: true) - If true, switches to or creates the note type specified in `NOTE_TYPE`.
- `SOURCE_FIELD`: (integer, default: 0) - Zero-based index of the field containing the word to scrape (e.g., 0 for the first field).
- `WORD_FIELD`: (integer, default: -1) - Field for the scraped word (if different from source; -1 to skip).
- `PRONUNCIATION_FIELD`: (integer, default: 1) - Field for pronunciation (KK phonetic transcription, e.g., `[ˋholɪ]`).
- `POS_FIELD`: (integer, default: 2) - Field for part of speech.
- `INFLECTIONS_FIELD`: (integer, default: 3) - Field for inflections (e.g., plural).
- `DEFINITION_ZH_FIELD`: (integer, default: 4) - Field for Chinese definition.
- `EXAMPLES_FIELD`: (integer, default: 5) - Field for examples.
- `INCLUDE_RELATED_WORDS`: (boolean, default: false) - If true, creates separate notes for related words/phrases.
- `DECK_NAME`: (string, default: "Default") - Deck for new cards (used for related words).
- `PARSER`: (string, default: "html.parser") - Parser for HTML scraping. Options: "html.parser" (built-in, no extra install) or "lxml" (faster, requires `lxml` package).

## Usage
1. For default behavior, keep `USE_DEFAULT_TEMPLATE` as `true` and set `NOTE_TYPE` to your preferred note type name (e.g., "YahooDictionary" or "Vocabulary").
2. For custom note types, set `USE_DEFAULT_TEMPLATE` to `false` and configure field indices to match your note type.
3. Set `PARSER` to "lxml" for faster parsing if you’ve installed the `lxml` package; otherwise, use "html.parser".
4. The plugin fills fields silently on success. Popups appear only for errors (e.g., network issues, invalid field indices).
5. The Pronunciation field contains the KK phonetic transcription (e.g., `[ˋholɪ]` for "holy") without KK or DJ labels.
6. If errors occur, delete `config.json` in the add-on folder to reset to defaults.

## Dependencies
The plugin requires `requests` and `beautifulsoup4`. For `PARSER: "lxml"`, you also need `lxml`. Install in Anki’s Flatpak Python environment:
1. Open a terminal and run: