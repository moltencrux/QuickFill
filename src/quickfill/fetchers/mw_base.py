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

from ..http_fetcher import HttpFetcher


class MWFetcherBase(HttpFetcher):
    """Shared Merriam-Webster scrape logic.

    Intermediate base – skipped by the auto-loader because
    ``source_name()`` raises ``NotImplementedError``.
    HTTP / clearance policy comes from ``HttpFetcher``.
    """

    site_host = "www.merriam-webster.com"
    base_url = "https://www.merriam-webster.com/dictionary/"
    warmup_url = "https://www.merriam-webster.com/"

    # Cloudflare is picky; look like a normal browser navigation.
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
        "Referer": "https://www.merriam-webster.com/",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Sec-Ch-Ua": (
            '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"'
        ),
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
    }

    # Subclasses override these
    edition_label = "Merriam-Webster"

    @staticmethod
    def source_name():
        raise NotImplementedError(
            "MWFetcherBase is an abstract base; subclasses must implement source_name()"
        )

    def _find_entry(self, soup):
        """Return the root element for this edition, or None."""
        raise NotImplementedError

    def _extract_pos(self, entry):
        """Return part-of-speech string from the entry root."""
        raise NotImplementedError

    def _extract_etymology(self, soup, entry):
        """Return etymology / word-history text."""
        raise NotImplementedError

    def page_ok(self, html):
        # Main entry and/or kids block both indicate a real dictionary page.
        h = html or ""
        return (
            "entry-word-section-container" in h
            or 'id="dictionary-entry-1"' in h
            or 'id="kidsdictionary"' in h
        )

    def _fetch_soup(self, word, config=None):
        url = self.base_url + urllib.parse.quote(word.lower().strip())

        # Warmup is only meaningful on the legacy path; site_session keeps cookies.
        if not (config or {}).get("config", {}).get("use_site_session", True):
            try:
                self._legacy_session(config).get(self.warmup_url, timeout=10)
            except requests.RequestException:
                pass

        return self._get_soup(url, config=config, timeout=15)

    def _parse_pronunciation(self, entry):
        syllables_el = entry.select_one("span.word-syllables-entry")
        syllables = syllables_el.get_text(strip=True) if syllables_el else ""
        # Clean zero-width spaces that MW inserts in syllable breaks
        syllables = syllables.replace("\u200b", "")

        pron_text = ""
        pron_badge = entry.select_one(
            "a.play-pron-v2, span.prons-entries-list-inline"
        )
        if pron_badge:
            # Prefer the title / data attributes; fall back to visible text
            raw = pron_badge.get_text(" ", strip=True)
            # Strip the "How to pronounce … (audio)" label
            raw = re.sub(r"How to pronounce.*", "", raw, flags=re.I).strip()
            pron_text = raw

        return " ".join(p for p in (syllables, pron_text) if p)

    def _parse_inflections(self, entry):
        infl_el = entry.select_one("span.vg-ins")
        if not infl_el:
            return ""
        parts = [t.get_text(strip=True) for t in infl_el.select("span.if")]
        if not parts:
            return re.sub(r"\s*;\s*", "; ", infl_el.get_text(" ", strip=True))
        return "; ".join(parts)

    def _parse_senses(self, entry):
        """Return (definition_lines, example_lines) from sense markup."""
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

        return def_lines, example_lines

    def _parse_page_examples(self, soup, config, example_lines):
        """Append curated (and optional web) sentences from #examples."""
        examples_widget = soup.find(id="examples")
        if not examples_widget:
            return example_lines

        curated = examples_widget.select(
            ".in-sentences .ex-sent, "
            ".in-sentences-container .ex-sent, "
            ".in-sentences .t"
        )
        seen_ids = set()
        curated_nodes = []
        for node in curated:
            nid = id(node)
            if nid in seen_ids:
                continue
            seen_ids.add(nid)
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
            if not ex_text or ex_text.startswith(("—", "–", "-")):
                continue
            ex_text = re.split(r"\s+[—–]\s+", ex_text, maxsplit=1)[0].strip()
            if ex_text and ex_text not in example_lines:
                example_lines.append(ex_text)

        return example_lines

    def fetch(self, word, config):
        """Scrape the configured MW edition and map to field indices."""
        field_map = config.get("mapping", {})

        try:
            soup = self._fetch_soup(word, config)
        except requests.RequestException as e:
            self.message_callback(f"Network error: {e}")
            return {}
        except Exception as e:
            self.message_callback(f"Parse error: {e}")
            return {}

        entry = self._find_entry(soup)
        if not entry:
            self.message_callback(
                f"No {self.edition_label} entry for '{word}'"
            )
            return {}

        hword_el = entry.select_one("h1.hword, p.hword, .hword")
        entry_word = hword_el.get_text(strip=True) if hword_el else word

        pos = self._extract_pos(entry)
        pronunciation = self._parse_pronunciation(entry)
        inflections = self._parse_inflections(entry)
        def_lines, example_lines = self._parse_senses(entry)
        example_lines = self._parse_page_examples(soup, config, example_lines)
        etymology = self._extract_etymology(soup, entry)

        payload = {
            "word": entry_word,
            "pos": pos,
            "pronunciation": pronunciation,
            "inflections": inflections,
            "definition": "<br>".join(def_lines),
            "examples": "<br>".join(example_lines),
            "etymology": etymology,
        }

        data = {}
        for key, idx in field_map.items():
            if idx is None or (isinstance(idx, int) and idx < 0):
                continue
            data[idx] = payload.get(key, "")

        if not data:
            self.message_callback(
                f"{self.edition_label} entry found for '{word}' "
                "but no fields mapped"
            )
        return data

