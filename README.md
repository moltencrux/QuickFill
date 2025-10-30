# QuickFill – Smart Dictionary Autofill for Anki

**QuickFill** is an extensible **Anki add-on** that lets you **instantly fill note fields** with rich dictionary data (pronunciation, definitions, examples, inflections, and more) from configurable sources (online, local CSV, etc.) — by typing a word and pressing a button.

No more copy-pasting. No more manual formatting.  
Just **one click** to **perfectly structured Anki cards**.

---

## Features

- **One-click dictionary lookup** directly in the Anki editor
- Supports **multiple dictionary sources** (configurable per model, deck pair)
- **Custom field mapping** via config
- Supports fetching from **Local CSV files** (with fast binary search for sorted CSVs)
- Supports fetching from online sources:
- **Pluggable fetcher system** – add your own sources
- **Open source** – fully extensible and transparent

---

## Supported Online Dictionaries

| Source | Language Pair | Notes |
|--------|---------------|-------|
| **Yahoo Dictionary (Taiwan)** | English -> Traditional Chinese (英文->繁體中文)| Full POS, examples, inflections|
| *(Add your own!)* | — | See [`FETCHERS.md`](#creating-new-fetchers) |
---

## Installation

1. **Clone** the QuickFill repo:
    ```
    git clone https://github.com/moltencrux/QuickFill`
    ```
2. Recursively copy QuickFill/QuickFillAddon to your Anki addon folder

    Linux (non-flatpak):
    ```sh
    cp -rT QuickFill/ ~/.local/share/Anki2/addons21/addons21/quickfill/
    ```
    Linux (flatpak):
    ```sh
    cp -rT QuickFill/ ~/.var/app/ ~/.var/app/net.ankiweb.Anki/data/Anki2/addons21/quickfill/
    ```
    Windows
    ```cmd
    mkdir "%APPDATA%\Anki2\addons21\quickfill" 2>nul && xcopy "QuickFill\QuickFillAddon\*.*" "%APPDATA%\Anki2\addons21\quickfill\" /E /Y /I
    ```
    MacOS
    ```sh
    mkdir -p ~/Library/Application\ Support/Anki2/addons21/quickfill && cp -r QuickFill/QuickFillAddon/* ~/Library/Application\ Support/Anki2/addons21/quickfill/
    ```

3. **Restart Anki**

> Or install via AnkiWeb (coming soon)

---

## Usage

1. Open the **Add Cards** dialog (`A`)
2. Type a word in your **source field** (default: first field)
3. Click the **QuickFill button** (dictionary icon) or press **`Ctrl+Shift+F`**
4. Done! All fields are auto-filled.

### Configure (Optional)

Go to:  
**`Tools` to `Add-ons` to `QuickFill` to `Config`**

```json
{
  "SOURCE_FIELD": 0,
  "NOTE_TYPE": "Vocabulary",
  "USE_DEFAULT_TEMPLATE": true,
  "PARSER": "html.parser",
  "field_mappings": {
    "word": 0,
    "pronunciation": 1,
    "pos": 2,
    "inflections": 3,
    "def_zh": 4,
    "examples": 5
  },
  "include_related_words": false
}
```

---

## Creating New Fetchers

Want to add support for your fadictionar or custom API?
See the full guide: [**`FETCHERS.md`**](FETCHERS.md)


---

## Project Structure

```
QuickFill/
├── __init__.py
├── config.json
├── fetchers/
│   ├── __init__.py
│   ├── yahoo.py
│   └── csv_fetcher.py
├── images/
│   └── quickfill.svg
├── README.md
├── FETCHERS.md
└── LICENSE
```

---

## Contributing

We welcome contributions!  
Whether it's a new fetcher, bug fix, or UI improvement:

1. Fork the repo
2. Create a branch (`feat/your-feature`)
3. Commit your changes
4. Open a Pull Request

---

## License

**GNU General Public License v2.0**

This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation.

See the full license: [**`LICENSE`**](LICENSE)

---

## Acknowledgments
The QuickFill Anki Add-On was buitl with inpiration from 
- [AutoDefine Anki Add-On](https://github.com/z1lc/AutoDefine)

---


**Made with love for language learners**  
