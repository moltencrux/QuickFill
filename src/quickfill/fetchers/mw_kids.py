"""Merriam-Webster dictionary fetchers.

Shared HTTP + parse logic for the collegiate entry and the Kids
(Student / Elementary) block on the same page:

  https://www.merriam-webster.com/dictionary/<word>

Subclasses only differ in which entry container they read and how
they resolve POS / etymology.
"""

import re
import urllib.parse

import requests
from bs4 import BeautifulSoup

from .mw_base import MWFetcherBase


class MWKidsFetcher(MWFetcherBase):
    """Kids / Student / Elementary definition (#kidsdictionary)."""

    warmup_url = "https://www.merriam-webster.com/kids"
    headers = {
        **MWFetcherBase.headers,
        "Referer": "https://www.merriam-webster.com/kids",
    }
    edition_label = "Kids Definition"

    @staticmethod
    def source_name():
        return "mw_kids"

    def _find_entry(self, soup):
        kids = soup.find(id="kidsdictionary")
        if not kids:
            return None
        return (
            kids.select_one(".entry-word-section-container-supplemental")
            or kids
        )

    def _extract_pos(self, entry):
        pos_el = entry.select_one(
            "span.important-blue-link, h2.parts-of-speech, .parts-of-speech"
        )
        return pos_el.get_text(strip=True) if pos_el else ""

    def _extract_etymology(self, soup, entry):
        et_el = soup.select_one(
            "#kidsdictionary p.et, "
            "#kidsdictionary .etymology-content-section .et, "
            "#kidsdictionary .et"
        )
        return et_el.get_text(" ", strip=True) if et_el else ""

