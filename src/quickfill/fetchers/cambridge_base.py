import re
import unicodedata
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from ..base_fetcher import Fetcher

_ws_re = re.compile(r"\s+")


def norm(s, collapse_spaces=True):
    if s is None:
        return ""
    s = unicodedata.normalize("NFC", str(s))
    if collapse_spaces:
        s = _ws_re.sub(" ", s).strip()
    return s


class CambridgeFetcher(Fetcher):
    """Shared base for Cambridge Dictionary bilingual fetchers (EC, EJ, …).

    Intermediate base – not registered as a fetcher itself.
    Subclasses must set ``base_url`` and implement ``source_name()``.
    """

    # Subclasses must set these
    base_url = None
    # Key used in the mapping dict for the translation field
    # (e.g. "def_zh" for Chinese, "def_ja" for Japanese)
    translation_key = "translation"

    @staticmethod
    def source_name():
        raise NotImplementedError(
            "CambridgeFetcher is an abstract base; subclasses must implement source_name()"
        )

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    pos_abbrev = {
        "adjective": "adj.",
        "adverb": "adv.",
        "conjunction": "conj.",
        "determiner": "det.",
        "exclamation": "exclam.",
        "noun": "n.",
        "phrasal verb": "phrv.",
        "preposition": "prep.",
        "pronoun": "pron.",
        "verb": "v.",
    }

    def _fetch_soup(self, word):
        url = urljoin(self.base_url, word)
        r = requests.get(url, headers=self.headers, timeout=10)
        r.raise_for_status()
        return BeautifulSoup(r.text, "html.parser")

    def _extract_pronunciations(self, scope, base=None):
        """
        Extract pronunciations from either of the two markup styles
        Cambridge uses:

        - EC / older:  <span class=\"dpron-i uk|us\"> … </span>
        - EJ / newer:  <span class=\"pron-info dpron-info\">
                           <span class=\"uk|us dloc\">…</span>
                           <span class=\"pron dpron\">/…/</span>
                       </span>
        """
        base = self.base_url if base is None else base
        seen = set()
        items = []

        # --- style 1: dpron-i (English-Chinese etc.) ------------------------
        for p in scope.select("span.dpron-i"):
            region = None
            for c in p.get("class", []) or []:
                if c in ("uk", "us"):
                    region = c
            if not region:
                anc = p.find_parent("span")
                if anc and anc.get("class"):
                    for c in anc["class"]:
                        if c in ("uk", "us"):
                            region = c

            pron_span = p.select_one("span.pron.dpron, span.pron")
            phonetic = (
                norm(pron_span.get_text(" ", strip=True))
                if pron_span
                else norm(p.get_text(" ", strip=True))
            )

            audio = None
            btn = p.select_one("[data-src-mp3]")
            if btn and btn.get("data-src-mp3"):
                audio = urljoin(base, btn["data-src-mp3"])
            else:
                src = p.select_one("audio source, amp-audio source, source")
                if src and src.get("src"):
                    audio = urljoin(base, src["src"])

            key = (region or "", phonetic or "", audio or "")
            if key in seen:
                continue
            seen.add(key)
            items.append(
                {"region": region, "phonetic": phonetic, "audio": audio}
            )

        # --- style 2: pron-info / dpron-info (English-Japanese etc.) --------
        for p in scope.select("span.pron-info.dpron-info, span.pron-info"):
            # region lives on a child span.uk / span.us
            region = None
            loc = p.select_one("span.uk, span.us, span.dloc")
            if loc:
                for c in loc.get("class", []) or []:
                    if c in ("uk", "us"):
                        region = c
            if not region:
                # fallback: region text
                reg_el = p.select_one("span.region.dreg, span.region")
                if reg_el:
                    region = norm(reg_el.get_text(strip=True)).lower() or None

            pron_span = p.select_one("span.pron.dpron, span.pron")
            phonetic = (
                norm(pron_span.get_text(" ", strip=True))
                if pron_span
                else ""
            )

            audio = None
            btn = p.select_one("[data-src-mp3]")
            if btn and btn.get("data-src-mp3"):
                audio = urljoin(base, btn["data-src-mp3"])
            else:
                src = p.select_one("audio source, amp-audio source, source")
                if src and src.get("src"):
                    audio = urljoin(base, src["src"])

            key = (region or "", phonetic or "", audio or "")
            if key in seen:
                continue
            seen.add(key)
            items.append(
                {"region": region, "phonetic": phonetic, "audio": audio}
            )

        return items

    def _pos_blocks(self, soup):
        """
        Return the list of POS entry blocks.
        Subclasses may override if the page structure differs significantly.
        """
        # Prefer the modern entry-body__el blocks (works for both EC and EJ)
        blocks = soup.select("div.entry-body__el, div.pr.entry-body__el")
        if blocks:
            return blocks
        # Fallback: any div that contains a pos-header
        return soup.select("div.pos-header") and [
            h.find_parent("div", class_=re.compile(r"entry-body"))
            or h.parent
            for h in soup.select("div.pos-header")
        ] or []

    def _translation_selector(self):
        """
        CSS selector for the primary translation span inside a def-block.
        Subclasses can override for language-specific class differences.
        """
        # EC pages often have .break-cj; EJ pages usually do not.
        return (
            "span.trans.dtrans.dtrans-se.break-cj, "
            "span.trans.dtrans.dtrans-se, "
            "span.trans.dtrans"
        )

    def _parse_cambridge(self, soup):
        result = {"word": None, "pos_sections": []}

        # headword (best-effort)
        h = soup.select_one(
            "div.di-title h1 b.tb.ttn, "
            "div.di-title span.hw, "
            "h2.headword span.hw, "
            "span.hw.dhw"
        )
        if h:
            result["word"] = norm(h.get_text(" ", strip=True))

        pos_blocks = self._pos_blocks(soup)

        for pb in pos_blocks:
            pos_entry = {"prons": [], "senses": []}
            result["pos_sections"].append(pos_entry)

            # POS label
            pos_el = pb.select_one("span.pos.dpos, .pos.dpos, span.pos")
            pos_label = norm(pos_el.get_text(" ", strip=True)) if pos_el else ""
            pos_entry["pos"] = pos_label

            # Pronunciations belonging to this POS block
            prons = self._extract_pronunciations(pb)
            for pron in prons:
                pron["pos"] = pos_label
            pos_entry["prons"].extend(prons)

            # Senses / definitions / examples
            senses = pos_entry["senses"]
            for sb in pb.select("div.sense-body.dsense_b, div.sense-body"):
                sense = {"defs": []}
                for defb in sb.select("div.def-block.ddef_block, div.def-block"):
                    defb_entry = {"examples": []}
                    trans_el = defb.select_one(self._translation_selector())
                    # Prefer a direct child translation over ones nested in examples
                    if not trans_el:
                        # last-resort: any .trans inside the def-block that is not under .examp
                        for cand in defb.select("span.trans"):
                            if not cand.find_parent(class_=re.compile(r"examp")):
                                trans_el = cand
                                break
                    defb_entry["translation"] = (
                        trans_el.get_text(strip=True) if trans_el else None
                    )
                    for exb in defb.select("div.examp.dexamp, div.examp"):
                        defb_entry["examples"].append(
                            exb.get_text(" ", strip=True)
                        )
                    sense["defs"].append(defb_entry)
                senses.append(sense)

        return result

    @staticmethod
    def fold_prons(prons):
        """Collapse pronunciations that are identical across regions / POS."""
        # Normalise None → "" so folding works cleanly
        pron_set = {
            (p.get("region") or "", p.get("pos") or "", p.get("phonetic") or "")
            for p in prons
            if p.get("phonetic")
        }
        all_regions = {p[0] for p in pron_set if p[0]}
        all_pos = {p[1] for p in pron_set if p[1]}

        for p in list(pron_set):
            if all_regions and all((r, *p[1:]) in pron_set for r in all_regions):
                pron_set.difference_update((r, *p[1:]) for r in all_regions)
                pron_set.add(("", *p[1:]))

        for p in list(pron_set):
            if all_pos and all((p[0], pos, *p[2:]) in pron_set for pos in all_pos):
                pron_set.difference_update(
                    (p[0], pos, *p[2:]) for pos in all_pos
                )
                pron_set.add((p[0], "", *p[2:]))

        return pron_set

    def fetch(self, word, config):
        """Scrape Cambridge Dictionary and map results to note-field indices."""
        if not word or not self.base_url:
            return {}

        field_map = config.get("mapping", {})

        try:
            soup = self._fetch_soup(word)
        except Exception as e:
            self.message_callback(f"Cambridge fetch error: {e}")
            return {}

        parsed = self._parse_cambridge(soup)

        # ---- pronunciations ------------------------------------------------
        all_prons = [
            pron for pos in parsed["pos_sections"] for pron in pos["prons"]
        ]
        for pron in all_prons:
            pron["pos"] = self.pos_abbrev.get(pron["pos"], pron["pos"])

        folded = self.fold_prons(all_prons)
        pronunciation_lines = []
        for reg, pos, phonetic in folded:
            reg = reg or ""
            pos = pos or ""
            phonetic = phonetic or ""
            line = f"{reg}{':' if reg else ''}{'(' + pos + ')' if pos else ''}{phonetic}"
            if phonetic:  # skip empty entries
                pronunciation_lines.append(line)
        pronunciation = "<br>".join(sorted(set(pronunciation_lines)))

        # ---- translations & examples ---------------------------------------
        translation = []
        examples = []
        for pos in parsed["pos_sections"]:
            for sense in pos["senses"]:
                for def_ in sense["defs"]:
                    if def_["translation"]:
                        pos_tag = self.pos_abbrev.get(pos["pos"], pos["pos"])
                        line = f"{pos_tag} {def_['translation']}"
                        translation.append(line)
                    examples.extend(def_["examples"])

        translation_str = "<br>".join(translation)
        examples_str = "<br>".join(examples)

        # ---- map to field indices ------------------------------------------
        # Build a lookup that always includes both the language-specific key
        # and the generic "translation" key so configs stay flexible.
        value_by_key = {
            "word": word,
            "pronunciation": pronunciation,
            "pos": "",
            "inflections": "",
            "examples": examples_str,
            "translation": translation_str,
            self.translation_key: translation_str,
        }

        data = {}
        for key, idx in field_map.items():
            if not isinstance(idx, int) or idx < 0:
                continue
            data[idx] = value_by_key.get(key, "")

        return data
