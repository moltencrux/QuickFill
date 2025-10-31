import requests
from bs4 import BeautifulSoup
import urllib.parse
from .. import Fetcher

class YahooFetcher(Fetcher):
    """Fetcher for Yahoo Dictionary (Taiwan)."""

    @staticmethod
    def source_name():
        return "yahoo_en_tc"

    def fetch(self, word, config):
        """Scrape word data from Yahoo Dictionary and map to field indices."""
        parser = config.get("parser", "html.parser")
        field_map = config.get("field_mappings", {})

        base_url = "https://tw.dictionary.search.yahoo.com/search?p="
        url = base_url + urllib.parse.quote(word)

        headers = {
            "User-Agent":
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        }

        # ------------------------------------------------------------------ #
        # 1. HTTP request
        # ------------------------------------------------------------------ #
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
        except requests.RequestException as e:
            self.message_callback(f"Network error: {e}")
            return {}

        # ------------------------------------------------------------------ #
        # 2. Parse HTML
        # ------------------------------------------------------------------ #
        try:
            soup = BeautifulSoup(resp.text, parser)
        except Exception as e:
            self.message_callback(f"Parse error: {e}")
            return {}

        data = {}

        # ------------------------------------------------------------------ #
        # 3. Main dictionary card
        # ------------------------------------------------------------------ #
        main_card = soup.find("div", class_="dictionaryWordCard")
        if not main_card:
            self.message_callback(f"No entry for '{word}'")
            return {}

        # Word
        entry_word = (
            main_card.find("span", class_="fz-24")
            .get_text(strip=True)
            if main_card.find("span", class_="fz-24")
            else word
        )

        # Pronunciation (KK only)
        pronunciation = ""
        pron_ul = main_card.find("div", class_="compList d-ib")
        if pron_ul:
            first_li = pron_ul.find("li")
            if first_li and first_li.get_text(strip=True).startswith("KK"):
                pronunciation = first_li.get_text(strip=True).replace("KK", "", 1).strip()

        # Inflections
        inflections = ""
        infl_ul = main_card.find("ul", class_="compArticleList")
        if infl_ul:
            h4 = infl_ul.find("h4")
            if h4:
                inflections = h4.get_text(strip=True)

        # ------------------------------------------------------------------ #
        # 4: Chinese translations
        # ------------------------------------------------------------------ #
        def_zh_tag = main_card.find('div', class_="compList mb-25 p-rel")

        def_list_zh = []

        for li in def_zh_tag.ul.find_all("li"):
            pos_li = li.find("div", class_="pos_button")
            pos_elem = '' if not pos_li else pos_li.text.strip()
            def_elem = li.find("div", class_="dictionaryExplanation").text.strip()

            if pos_elem or def_elem:
                def_list_zh.append(f"{pos_elem} {def_elem}")

        def_zh_str = '<br>'.join(def_list_zh)

        # ------------------------------------------------------------------ #
        # 5. 釋義 Examples / Explanations
        # ------------------------------------------------------------------ #
        explanation_div = soup.find("div", class_="grp-tab-content-explanation")
        pos = ""
        examples_str = ""

        if explanation_div:
            # Strip out all tag attributes
            for t in explanation_div.find_all(True):
                for a in list(t.attrs):
                    if a in ("class","role","id","style") or a.startswith("aria-"):
                        del t.attrs[a]

            examples_str = explanation_div.decode_contents()

        # ------------------------------------------------------------------ #
        # 6. Map everything to note-field indices
        # ------------------------------------------------------------------ #
        main_mapped = {}

        for key, idx in field_map.items():
            if idx < 0:
                continue
            data[idx] = {
                "word": entry_word,
                "pronunciation": pronunciation,
                "pos": pos,
                "inflections": inflections,
                "def_zh": def_zh_str,
                "examples": examples_str,
            }.get(key, "")

        # data.append(main_mapped)

        # ------------------------------------------------------------------ #
        # 7. Related words (optional)
        # ------------------------------------------------------------------ #
        # if config.get("include_related_words", False):
        #     related_div = soup.find("div", class_="grp-tab-content-algo")
        #     if related_div:
        #         for title in related_div.find_all("h3", class_="title"):
        #             a = title.find("a")
        #             if not a:
        #                 continue
        #             rel_word = a.get_text(strip=True)

        #             # definition block that follows the title
        #             next_div = a.find_parent().find_next_sibling("div", class_="compTextList")
        #             if not next_div:
        #                 continue
        #             li = next_div.find("ul").find("li")
        #             if not li:
        #                 continue

        #             pos_tag = li.find("div", class_="pos_button")
        #             rel_pos = pos_tag.get_text(strip=True) if pos_tag else ""

        #             # English + Chinese in same pattern
        #             en_span = li.find("span", class_="d-i fz-14 lh-20")
        #             en_def = en_span.get_text(strip=True) if en_span else ""
        #             zh_span = None
        #             if en_span:
        #                 for sibling in en_span.parent.find_next_siblings():
        #                     if sibling.name == "span" and "ml-1" in sibling.get("class", []):
        #                         zh_span = sibling
        #                         break
        #             zh_def = zh_span.get_text(strip=True) if zh_span else ""
        #             rel_def = f"{en_def} {zh_def}".strip() if zh_def else en_def

        #             rel_mapped = {}
        #             for key, idx in field_map.items():
        #                 if idx < 0:
        #                     continue
        #                 rel_mapped[idx] = {
        #                     "word": rel_word,
        #                     "pos": rel_pos,
        #                     "def_zh": f"{rel_pos} {rel_def}".strip() if rel_pos else rel_def,
        #                 }.get(key, "")
        #             data.append(rel_mapped)

        # print(f"Debug: YahooFetcher fetched data for '{word}': {data}")
        return data

if __name__ == "__main__":
    fetcher = YahooFetcher()
    cfg = {
        "parser": "html.parser",
        "field_mappings": {
            "word": 0,
            "pronunciation": 1,
            "pos": 2,
            "inflections": 3,
            "def_zh": 4,
            "examples": 5,
        },
        "include_related_words": False,
    }
    result = fetcher.fetch("memorize", cfg)
    print(result)

