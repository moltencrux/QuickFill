#!/usr/bin/env python3 -B
import os
import sys

sys.path.append(os.path.abspath(os.path.dirname(__file__) + '/../src'))

import quickfill
from quickfill.fetchers import MWKidsFetcher
from pprint import pprint


if __name__ == "__main__":
    fetcher = MWKidsFetcher()
    word = "memorize"
    cfg = {
        "fetcher": "mw_kids",
        "name": "MW Kids",
        "config": {
            "parser": "html.parser",
        },
        "mapping": {

            "definition": 2,
            "etymology": 5,
            "examples": 7,
            "inflections": 6,
            "pos": 7,
            "pronunciation": 1,
            "word": 0
        },
    }
    result = fetcher.fetch(word, cfg)
    pprint(result)

"""
                {
                "config": {
                    "parser": "html.parser"
                },
                "fetcher": "mw_kids",
                "mapping": {
                    "definition": 2,
                    "etymology": -1,
                    "examples": 7,
                    "inflections": -1,
                    "pos": -1,
                    "pronunciation": 1,
                    "word": 0
                },
                "mask_class": "qf-headword",
                "mask_fields": [
                    2,
                    7,
                    8
                ],
                "mask_mode": "tag",
                "name": "MW Kids",
                "source_field": 0
            }

"""

