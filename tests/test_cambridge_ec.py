#!/usr/bin/env python3 -B
import os
import sys

# sys.path.append(os.path.abspath(os.path.dirname(__file__)) + '/src')
sys.path.append(os.path.abspath(os.path.dirname(__file__) + '/../src'))

import quickfill
from quickfill.fetchers import CambridgeECFetcher
from pprint import pprint


if __name__ == "__main__":
    fetcher = CambridgeECFetcher()
    word = "traditional"
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

