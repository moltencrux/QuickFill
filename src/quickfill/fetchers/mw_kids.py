"""Fetcher for Merriam-Webster Kids (Student / Elementary) Dictionary.

Scrapes the "Kids Definition" section that appears on
https://www.merriam-webster.com/dictionary/<word> under #kidsdictionary.
"""

import re
import urllib.parse

import requests
from bs4 import BeautifulSoup

from .. import Fetcher


class MWKidsFetcher(Fetcher):
    """Fetcher for Merriam-Webster Student Dictionary for Kids."""

    base_url = "https://www.merriam-webster.com/dictionary/"
    kids_home = "https://www.merriam-webster.com/kids"

    # Cloudflare is picky; look like a normal browser navigation from /kids.
    # Do NOT request br encoding — requests may not decompress it and CF can
    # also treat incomplete client hints as a bot signal.
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;"
            "q=0.9,image/avif,image/webp,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
        "Referer": "https://www.merriam-webster.com/kids",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Sec-Ch-Ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
    }

    @staticmethod
    def source_name():
        return "mw_kids"

    def _session(self):
        """Shared session so CF cookies from a warmup hit carry over."""
        if not hasattr(self, "_http"):
            self._http = requests.Session()
            self._http.headers.update(self.headers)
        return self._http

    def _fetch_soup(self, word):
        session = self._session()
        url = self.base_url + urllib.parse.quote(word.lower().strip())

        # Warm cookies from the kids landing page (same-origin referer path).
        try:
            session.get(self.kids_home, timeout=10)
        except requests.RequestException:
            pass  # non-fatal; still try the dictionary URL

        r = session.get(url, timeout=12)
        if r.status_code == 403:
            raise requests.HTTPError(
                "403 Forbidden from Merriam-Webster (Cloudflare). "
                "Try again later, or from a different network. "
                f"URL: {url}",
                response=r,
            )
        r.raise_for_status()
        return BeautifulSoup(r.text, "html.parser")

    def fetch(self, word, config):
        """Scrape Kids Definition from MW dictionary page and map to field indices."""
        field_map = config.get("mapping", {})

        try:
            soup = self._fetch_soup(word)
        except requests.RequestException as e:
            self.message_callback(f"Network error: {e}")
            return {}
        except Exception as e:
            self.message_callback(f"Parse error: {e}")
            return {}

        kids = soup.find(id="kidsdictionary")
        if not kids:
            self.message_callback(f"No Kids Definition for '{word}'")
            return {}

        entry = kids.select_one(".entry-word-section-container-supplemental") or kids

        # Headword
        hword_el = entry.select_one("p.hword, .hword")
        entry_word = hword_el.get_text(strip=True) if hword_el else word

        # Part of speech
        pos_el = entry.select_one("span.important-blue-link")
        pos = pos_el.get_text(strip=True) if pos_el else ""

        # Syllables + pronunciation
        syllables_el = entry.select_one("span.word-syllables-entry")
        syllables = syllables_el.get_text(strip=True) if syllables_el else ""
        # Clean zero-width spaces that MW inserts in syllable breaks
        syllables = syllables.replace("\u200b", "")

        pron_text = ""
        pron_badge = entry.select_one("a.play-pron-v2, span.prons-entries-list-inline")
        if pron_badge:
            # Prefer the title / data attributes; fall back to visible text
            raw = pron_badge.get_text(" ", strip=True)
            # Strip the "How to pronounce … (audio)" label
            raw = re.sub(r"How to pronounce.*", "", raw, flags=re.I).strip()
            pron_text = raw

        pronunciation = " ".join(p for p in (syllables, pron_text) if p)

        # Inflections (e.g. happier; happiest)
        infl_el = entry.select_one("span.vg-ins")
        inflections = ""
        if infl_el:
            parts = [t.get_text(strip=True) for t in infl_el.select("span.if")]
            if not parts:
                inflections = re.sub(r"\s*;\s*", "; ", infl_el.get_text(" ", strip=True))
            else:
                inflections = "; ".join(parts)

        # Definitions + examples
        def_lines = []
        example_lines = []

        for item in entry.select(".vg-sseq-entry-item"):
            label_el = item.select_one(".vg-sseq-entry-item-label")
            label = label_el.get_text(strip=True) if label_el else ""

            # Each sense / sub-sense
            for sense in item.select(".sense"):
                dt = sense.select_one(".dtText")
                if not dt:
                    continue
                def_text = dt.get_text(" ", strip=True)
                # Normalize leading ": "
                def_text = re.sub(r"^:\s*", "", def_text).strip()
                if not def_text:
                    continue

                # Sub-sense letter (a, b, …) if present
                sn_el = sense.select_one("span.sn")
                sn = sn_el.get_text(strip=True) if sn_el else ""

                prefix_parts = [p for p in (label, sn) if p]
                prefix = " ".join(prefix_parts)
                line = f"{prefix} {def_text}".strip() if prefix else def_text
                def_lines.append(line)

                for ex in sense.select(".ex-sent"):
                    # Skip author/attribution noise
                    if ex.select_one(".aq, .auth"):
                        continue
                    ex_text = ex.get_text(" ", strip=True)
                    if ex_text:
                        example_lines.append(ex_text)

        # Page-level "Examples of <word> in a Sentence" (#examples).
        # This is the tab behind ?ref=kidsdictionary#examples — separate from
        # the Kids Definition block, which often has no inline examples.
        #
        # Layout:
        #   #examples
        #     .in-sentences / .in-sentences-container  → curated dictionary examples
        #     .on-web                                 → news-corpus "Recent Examples"
        #
        # Always take every curated sentence. Optionally include web examples
        # when config["config"]["include_web_examples"] is true, or when there
        # are no curated ones at all.
        examples_widget = soup.find(id="examples")
        if examples_widget:
            # Broad curated selectors — MW markup varies slightly by entry.
            curated = examples_widget.select(
                ".in-sentences .ex-sent, "
                ".in-sentences-container .ex-sent, "
                ".in-sentences .t"
            )
            # De-dupe nodes (same element can match multiple selectors)
            seen_ids = set()
            curated_nodes = []
            for node in curated:
                nid = id(node)
                if nid in seen_ids:
                    continue
                seen_ids.add(nid)
                # Skip anything that actually lives under the web-corpus block
                if node.find_parent(class_=lambda c: c and "on-web" in c):
                    continue
                curated_nodes.append(node)

            web_nodes = examples_widget.select(".on-web .ex-sent")
            include_web = bool(
                (config.get("config") or {}).get("include_web_examples")
            )
            if curated_nodes:
                pool = curated_nodes + (web_nodes if include_web else [])
            else:
                pool = web_nodes

            for ex in pool:
                content = (
                    ex.select_one(".thread-anchor-content")
                    or ex.select_one(".d-block")
                    or ex
                )
                ex_text = content.get_text(" ", strip=True)
                # Drop empty / pure attribution lines
                if not ex_text or ex_text.startswith(("—", "–", "-")):
                    continue
                # Strip trailing "— Author, Publication, date" if present
                ex_text = re.split(r"\s+[—–]\s+", ex_text, maxsplit=1)[0].strip()
                if ex_text and ex_text not in example_lines:
                    example_lines.append(ex_text)

        definition = "<br>".join(def_lines)
        examples = "<br>".join(example_lines)

        # Optional etymology (present on some entries; lives under kids root)
        et_el = kids.select_one("p.et, .etymology-content-section .et, .et")
        etymology = et_el.get_text(" ", strip=True) if et_el else ""

        # Map to note-field indices
        payload = {
            "word": entry_word,
            "pos": pos,
            "pronunciation": pronunciation,
            "inflections": inflections,
            "definition": definition,
            "examples": examples,
            "etymology": etymology,
        }

        data = {}
        for key, idx in field_map.items():
            if idx is None or (isinstance(idx, int) and idx < 0):
                continue
            data[idx] = payload.get(key, "")

        if not data:
            self.message_callback(f"Kids entry found for '{word}' but no fields mapped")
        return data
