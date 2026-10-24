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


class MWDictionaryFetcher(MWFetcherBase):
    """Standard collegiate dictionary entry (#dictionary-entry-1)."""

    edition_label = "Merriam-Webster"

    @staticmethod
    def source_name():
        return "mw"

    def _find_entry(self, soup):
        # Prefer the explicit main entry id; fall back to the first entry
        # container that is not nested under the Kids block.
        main = soup.find(id="dictionary-entry-1")
        if main:
            return main
        for cont in soup.select(".entry-word-section-container"):
            if cont.find_parent(id="kidsdictionary"):
                continue
            return cont
        return None

    def _extract_pos(self, entry):
        # Collegiate headword POS is an <h2 class="parts-of-speech">.
        # Avoid bare .fl — it also marks POS on run-ons / related forms.
        header = entry.select_one(
            ".entry-header-content, .entry-header, .row.entry-header"
        )
        scope = header or entry
        pos_el = scope.select_one(
            "h2.parts-of-speech, .parts-of-speech, "
            "span.important-blue-link"
        )
        return pos_el.get_text(strip=True) if pos_el else ""

    def _extract_etymology(self, soup, entry):
        # Collegiate word-history widget on the same page.
        # Body mixes "Etymology …", "First Known Use …", and a
        # "Time Traveler" promo — keep the useful bits only.
        hist = soup.find(id="word-history") or soup.select_one(".word-history")
        if not hist:
            et_el = entry.select_one("p.et, .et")
            return et_el.get_text(" ", strip=True) if et_el else ""

        body = hist.select_one(".content-section-body") or hist
        text = body.get_text(" ", strip=True)
        text = re.sub(r"^Word History\s*", "", text, flags=re.I).strip()
        # Cut off Time Traveler / "See more words…" chrome
        text = re.split(
            r"\bTime Traveler\b|\bSee more words from the same\b",
            text,
            maxsplit=1,
            flags=re.I,
        )[0].strip()
        return text
