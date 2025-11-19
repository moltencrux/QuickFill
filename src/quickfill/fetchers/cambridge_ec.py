import requests
from bs4 import BeautifulSoup
import urllib.parse
from .. import Fetcher

from urllib.parse import urljoin
import re, unicodedata


class CambridgeECFetcher(Fetcher):
    """Fetcher for Cambridge English-Chinese Dictionary."""
    base_url = 'https://dictionary.cambridge.org/dictionary/english-chinese-traditional/'

    # HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; script/1.0)"}

    headers = {
        "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
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
        "verb": "v."
    }

    @staticmethod
    def source_name():
        return "cambridge_en_tc"

    def _fetch_soup(self, word):
        r = requests.get(urljoin(self.base_url, word), headers=self.headers, timeout=10)
        r.raise_for_status()
        return BeautifulSoup(r.text, "html.parser")

    def _fetch_entry_file(self):
        filename = '/home/agc/dev/QuickFill/tmp/https___dictionary.cambridge.org_dictionary_english-chinese-traditional_train.html'
        with open(filename) as f:
            text = f.read()
        return BeautifulSoup(text, "html.parser")

    def fetch(self, word, config):
        """Scrape word data from Yahoo Dictionary and map to field indices."""
        parser = config.get("config", {}).get("parser", "html.parser")
        field_map = config.get("mapping", {})

        url = self.base_url + urllib.parse.quote(word)

        # ------------------------------------------------------------------ #
        # 1. Fetch URL and and parse HTML
        # ------------------------------------------------------------------ #
        try:
            soup = self._fetch_soup(word)
        except Exception as e:
            self.message_callback(f"Parse error: {e}")
            return {}

        parsed = self._parse_cambridge(soup)

        # Build pronunciation & audio
        pronunciation = []
        pron_set = set()
        audio = []

        all_prons = [pron for pos in parsed['pos_sections'] for pron in pos['prons']]
        for pron in all_prons:
            pron['pos'] = self.pos_abbrev.get(pron["pos"], pron["pos"])

        folded = self.fold_prons(all_prons)
        # (region, pos, pron)
        for reg, pos, pron in folded:
            line = f'{reg}{reg and ":"}{pos and "(" + pos + ")"}{pron}'
            pronunciation.append(line)



        # for pos in parsed['pos_sections']:
        #     for pron in pos['prons']:
        #         line = '{region}:{phonetic}'.format(**pron)
        #         pronunciation.append(line)
        #         audio.append(pron['audio'])
            
        pronunciation = '<br>'.join(sorted(set(pronunciation)))

        # Build translations and examples
        translation = []
        examples = []


        for pos in parsed['pos_sections']:
            for sense in pos['senses']:
                for def_ in sense['defs']:
                    if def_["translation"]:
                        pos_tag = self.pos_abbrev.get(pos["pos"], pos["pos"])
                        line = f'{pos_tag} {def_["translation"]}'
                        translation.append(line)
                    examples.extend(def_['examples'])

        translation = '<br>'.join(translation)
        examples = '<br>'.join(examples)

        data = {}

        # ------------------------------------------------------------------ #
        # 6. Map everything to note-field indices
        # ------------------------------------------------------------------ #
        main_mapped = {}

        for key, idx in field_map.items():
            if idx < 0:
                continue
            data[idx] = {
                "word": word,
                "pronunciation": pronunciation,
                "pos": '',
                "inflections": '',
                "def_zh": translation,
                "examples": examples,
            }.get(key, "")

        return data

    def _extract_pronunciations(self, scope, base=None):
        base = self.base_url if base is None else base
        seen = set()
        items = []

        for p in scope.select("span.dpron-i"):
            # region
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
            # phonetic
            pron_span = p.select_one("span.pron.dpron, span.pron")
            phonetic = norm(pron_span.get_text(" ", strip=True)) if pron_span else norm(p.get_text(" ", strip=True))

            # audio
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
            items.append({"region": region, "phonetic": phonetic, "audio": audio})
        return items


    def _parse_cambridge(self, soup):
        result = {"word": None, "pos_sections": []}

        # headword fallback
        h = soup.select_one("article.english-chinese-traditional div.di-title h1 b.tb.ttn")
        if h:
            result["word"] = norm(h.get_text(" ", strip=True))

        # restrict to canonical entry-body__el if present
        canonical = soup.select_one("div.entry-body")
        if canonical:
            scope = canonical
        else:
            scope = soup

        scope = soup

        # POS sections
        pos_blocks = scope.select("div.entry div.entry-body__el")

        pos_seen = set()
        for pb in pos_blocks:
            pos_entry = {'prons':[], 'senses': []}
            result['pos_sections'].append(pos_entry)
            # dsense_pos = pb.select_one("h3.dsense_h span.pos.dsense_pos, span.pos.dsense_pos, .pos")
            pos_header = pb.select_one('div.entry div.entry-body div.pos-header')

            dsense_pos = pos_header.select_one('.pos.dpos')

            pos_label = norm(dsense_pos.get_text(" ", strip=True)) if dsense_pos else ""
            pos_entry["pos"] = pos_label

            prons = self._extract_pronunciations(pb)
            for pron in prons:
                pron['pos'] = pos_label
            pos_entry['prons'].extend(prons)

            # collect senses within this POS block
            senses = pos_entry['senses']
            # sense_seen = set()
            for sb in pb.select("div.sense-body.dsense_b"):
                sense = {'defs':[]}
                for defb in sb.select("div.def-block.ddef_block"):
                    defb_entry = {"examples": []}
                    trans_el = defb.select_one(":not(.examp) > span.trans.dtrans.dtrans-se.break-cj")
                    defb_entry['translation'] = trans_el and trans_el.get_text(strip=True)
                    for exb in defb.select("div.examp.dexamp"):
                        defb_entry['examples'].append(exb.get_text(' ', strip=True))
                    sense['defs'].append(defb_entry)
                senses.append(sense)

        return result

    @staticmethod
    def fold_prons(prons):
        pron_set = {(p['region'], p['pos'], p['phonetic']) for p in prons}
        all_regions = set(p[0] for p in pron_set)
        all_pos = set(p[1] for p in pron_set)

        for p in [*pron_set]:
            if all((r, *p[1:]) in pron_set for r in all_regions):
                pron_set.difference_update(((r, *p[1:]) for r in all_regions))
                pron_set.add(('', *p[1:]))

        for p in [*pron_set]:
            if all((p[0], pos, *p[2:]) in pron_set for pos in all_pos):
                pron_set.difference_update(((p[0], pos, *p[2:]) for pos in all_pos))
                pron_set.add((p[0], '', *p[2:]))

        return pron_set

_ws_re = re.compile(r"\s+")

def norm(s, collapse_spaces=True):
    if s is None:
        return ""
    s = unicodedata.normalize("NFC", str(s))
    if collapse_spaces:
        s = _ws_re.sub(" ", s).strip()
    return s




if __name__ == "__main__":
    word = "example"  # replace as needed
    soup = fetch_entry_file()
    parsed = parse_cambridge(soup)
    import json
    print(json.dumps(parsed, ensure_ascii=False, indent=2))

