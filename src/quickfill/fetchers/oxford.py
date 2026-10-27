"""Oxford Learner's Dictionaries fetcher.

Scrapes https://www.oxfordlearnersdictionaries.com/ (OALD, or the Oxford
Advanced American Dictionary) and maps the result onto note-field indices.

URL scheme (confirmed against the live site and the AutoDefine add-on):

  /definition/english/<slug>            Oxford Advanced Learner's Dictionary
  /definition/american_english/<slug>   Oxford Advanced American Dictionary
  /definition/english/<slug>_2          2nd homograph (e.g. content_1 / content_2)
  /search/english/?q=<word>             fallback for unknown slugs / inflections

Selectors follow the markup used by the AutoDefine add-on
(https://github.com/artyompetrov/AutoDefine_oxfordlearnersdictionaries,
itself derived from NearHuscarl/oxford-dictionary-api, BSD-3-Clause), with
fallbacks for the current ``unbox`` / ``cefr`` attributes.

``mapping`` keys understood by this fetcher::

    word, pos, pronunciation, inflections, definition, examples,
    etymology, cefr

``config`` options (all optional)::

    "dictionary":               "english" (default) | "american_english"
    "accent":                   "both" (default) | "uk" | "us"
    "max_definitions":          int, cap on definitions (default: no cap)
    "max_examples_per_sense":   int, cap on examples per sense (default: no cap)
    "include_extra_examples":   bool, add the "Extra Examples" box (default false)
    "include_grammar":          bool, prefix [transitive] etc. (default false)
    "number_definitions":       bool, "1. ", "2. " prefixes (default true)
    "homographs":               true (default) | false | int.  Words with several
                                numbered entries (recreation_1, recreation_2)
                                are fetched and merged into one result.  An int
                                caps the number of *extra* entries (default 5).
"""

import copy
import re
import urllib.parse

from ..clearance_install import is_clearance_needed_error
from ..http_fetcher import HttpFetcher

_ws_re = re.compile(r"\s+")

# Blocks that look like definitions/examples but are not part of the entry
# proper (kept in sync with AutoDefine's ``Word.get``).
_NOISE_SELECTORS = (
    '[title="Oxford Collocations Dictionary"]',
    '[title="British/American"]',
    '[title="Express Yourself"]',
    '[title="Collocations"]',
    '[unbox="colloc"]',
    '[unbox="snippet"]',
)

# Senses living under these containers belong to idioms / phrasal verbs,
# which have their own entries; keep them out of the main definition list.
_SUBENTRY_CLASSES = ("idioms", "idm-g", "pv-gs", "pv-g", "phrasal_verb_links")

_POS_ABBREV = {
    "adjective": "adj.",
    "adverb": "adv.",
    "conjunction": "conj.",
    "determiner": "det.",
    "exclamation": "exclam.",
    "modal verb": "modal v.",
    "auxiliary verb": "aux. v.",
    "noun": "n.",
    "number": "num.",
    "phrasal verb": "phrv.",
    "preposition": "prep.",
    "pronoun": "pron.",
    "verb": "v.",
}


def _txt(el):
    """Visible text of *el* with whitespace collapsed ('' for None).

    Deliberately no separator: Oxford wraps cross-refs and punctuation in
    inline tags, and ``get_text(" ")`` would produce 'foo , bar'.
    """
    if el is None:
        return ""
    return _ws_re.sub(" ", el.get_text()).strip()


def _slug(word):
    return urllib.parse.quote(
        re.sub(r"\s+", "-", word.strip().lower()), safe="-'"
    )


class OxfordFetcher(HttpFetcher):
    """Oxford Learner's Dictionaries (English → English)."""

    site_host = "www.oxfordlearnersdictionaries.com"
    base_url = "https://www.oxfordlearnersdictionaries.com"

    headers = {
        **HttpFetcher.headers,
        "Referer": "https://www.oxfordlearnersdictionaries.com/",
    }

    @staticmethod
    def source_name():
        return "oxford"

    # ------------------------------------------------------------------ HTTP

    def page_ok(self, html):
        # Accept *any* genuine Oxford page, including "not found" and search
        # result pages.  site_session treats small pages that fail page_ok as
        # a bot challenge and may launch a browser, which is the wrong
        # reaction to a misspelled word.
        if not super().page_ok(html):
            return False
        h = html.lower()
        return (
            'id="entrycontent"' in h
            or 'id="search-results"' in h
            or "oxford learner" in h
        )

    def _opts(self, config):
        return (config or {}).get("config") or {}

    def _dict_path(self, config):
        d = self._opts(config).get("dictionary", "english")
        return d if d in ("english", "american_english") else "english"

    def _definition_url(self, slug, config):
        return f"{self.base_url}/definition/{self._dict_path(config)}/{slug}"

    def _search_url(self, word, config):
        q = urllib.parse.quote_plus(word.strip())
        return f"{self.base_url}/search/{self._dict_path(config)}/?q={q}"

    @staticmethod
    def _entry_root(soup):
        """The ``.entry`` element, or None if this is not a definition page."""
        content = soup.select_one("#entryContent")
        if content is None:
            return None
        return content.select_one(".entry") or content

    @staticmethod
    def _clean(soup):
        for sel in _NOISE_SELECTORS:
            for tag in soup.select(sel):
                tag.decompose()

    def _load_entry_soup(self, word, config):
        """Return a soup for *word*'s definition page, or None.

        Tries the direct slug first, then falls back to the site search to
        resolve inflected forms ('went' → go) and alternative spellings.
        """
        soup = self.acquire_soup(
            self._definition_url(_slug(word), config),
            config,
            timeout=15,
            error_label="Oxford",
        )
        if soup is None:  # hard failure, already reported by acquire_soup
            return None
        if self._entry_root(soup) is not None:
            return soup

        # We got a page back, but not a definition (404 / "not found").
        try:
            search = self._get_soup(
                self._search_url(word, config), config=config, timeout=15
            )
        except Exception as e:
            if is_clearance_needed_error(e):
                raise
            self.message_callback(f"Oxford error: {e}")
            return None

        # A unique match redirects straight to the definition page.
        if self._entry_root(search) is not None:
            return search

        # Otherwise pick a *close* result; never guess from "did you mean".
        results = search.select_one("#search-results")
        if results is None:
            return None
        heading = results.select_one("h1")
        if heading and "no exact match" in _txt(heading).lower():
            return None

        target = word.strip().lower()
        for a in results.select("a[href*='/definition/']"):
            label = re.sub(r"[\d\s]+$", "", _txt(a).lower())
            if label.split(" ")[0] == target.split(" ")[0]:
                nxt = self._get_soup_quiet(
                    urllib.parse.urljoin(self.base_url, a["href"]), config
                )
                if nxt is not None and self._entry_root(nxt) is not None:
                    return nxt
        return None

    def _get_soup_quiet(self, url, config):
        """``_get_soup`` that swallows ordinary failures (not clearance)."""
        try:
            return self._get_soup(url, config=config, timeout=15)
        except Exception as e:
            if is_clearance_needed_error(e):
                raise
            print(f"Debug: Oxford fetch failed for {url}: {e}")
            return None

    # --------------------------------------------------------------- parsing

    def _parse_headword(self, root):
        h = root.select_one(".webtop h1.headword, h1.headword, .headword")
        if h is None:
            return ""
        h = copy.copy(h)
        for junk in h.select(".hm, sup"):
            junk.decompose()
        return _txt(h)

    def _parse_pos(self, root):
        return _txt(root.select_one(".webtop .pos, .top-container .pos, .pos"))

    def _parse_cefr(self, root):
        webtop = root.select_one(".webtop, .top-container")
        m = re.search(r"sym_([abc][12])\b", str(webtop)) if webtop else None
        if m:
            return m.group(1).upper()
        for el in root.select("[cefr]"):
            if el.get("cefr"):
                return el["cefr"].upper()
        return ""

    def _parse_pronunciation(self, root, accent):
        """Return ['BrE /…/', 'NAmE /…/'] (folded to one line if identical)."""

        def one(geo):
            el = root.select_one(f".phons_{geo} .phon, [geo={geo}] .phon")
            s = _txt(el).strip("/ ")
            return f"/{s}/" if s else ""

        want = {"uk": ("br",), "us": ("n_am",)}.get(accent, ("br", "n_am"))
        found = {geo: one(geo) for geo in want}
        found = {g: p for g, p in found.items() if p}

        if not found:  # American dictionary / unexpected markup
            s = _txt(root.select_one(".webtop .phon, .phon")).strip("/ ")
            return f"/{s}/" if s else ""

        if len(set(found.values())) == 1:
            return next(iter(found.values()))
        labels = {"br": "BrE", "n_am": "NAmE"}
        return "<br>".join(f"{labels[g]} {p}" for g, p in found.items())

    def _parse_inflections(self, root, headword):
        forms = []

        for row in root.select("tr.verb_form[form], .verb_forms_table tr"):
            td = row.select_one("td.verb_form") or row
            td = copy.copy(td)
            for junk in td.select(
                ".vf_prefix, .phons_br, .phons_n_am, .phonetics, .phon, .sound"
            ):
                junk.decompose()
            form = _txt(td)
            if form:
                forms.append(form)

        if not forms:
            infl = root.select_one(".webtop .inflections, .inflections")
            if infl:
                for f in infl.select(".inflected_form"):
                    forms.append(_txt(f))
                if not forms:
                    forms.append(_txt(infl).strip("() "))

        seen, out = set(), []
        for f in forms:
            if f and f.lower() != (headword or "").lower() and f not in seen:
                seen.add(f)
                out.append(f)
        return "; ".join(out)

    @staticmethod
    def _own(sense, cls):
        """First element of class *cls* belonging to *sense* itself.

        Skips matches nested inside example lists / unboxes (examples can
        carry their own labels and grammar).
        """
        for el in sense.find_all(class_=cls):
            if el.find_parent("ul", class_="examples") is None and (
                el.find_parent(attrs={"unbox": True}) is None
            ):
                return el
        return None

    def _parse_senses(self, root, opts):
        """Return (definition_lines, example_lines)."""
        max_ex = opts.get("max_examples_per_sense")
        extra = bool(opts.get("include_extra_examples"))
        grammar = bool(opts.get("include_grammar"))

        senses = root.select("li.sense") or root.select(".sense")
        defs, examples = [], []

        for sense in senses:
            if sense.find_parent(class_=list(_SUBENTRY_CLASSES)):
                continue

            d = _txt(self._own(sense, "def"))
            # Cross-reference-only senses ("see ...") have no <span class=def>
            if not d:
                continue

            prefix = []
            if grammar:
                prefix.append(_txt(self._own(sense, "grammar")))
            prefix.append(_txt(self._own(sense, "labels")))
            prefix.append(_txt(self._own(sense, "dis-g")))
            line = " ".join(p for p in prefix + [d] if p)
            defs.append(line)

            sense_ex = []
            for ul in sense.find_all("ul", class_="examples"):
                box = ul.find_parent(attrs={"unbox": True})
                in_extra = bool(box and box.get("unbox") == "extra_examples")
                # Thesaurus / synonym / collocation boxes carry their own
                # example sentences; only the Extra Examples box is wanted.
                if box is not None and not (in_extra and extra):
                    continue
                for li in ul.find_all("li", recursive=False):
                    x = li.select_one(".x, .unx") or li
                    t = _txt(x)
                    if t:
                        sense_ex.append((bool(in_extra), t))

            regular = [t for is_extra, t in sense_ex if not is_extra]
            more = [t for is_extra, t in sense_ex if is_extra]
            if max_ex is not None:
                regular = regular[: int(max_ex)]
            examples.extend(regular + more)

        return defs, examples

    def _parse_origin(self, root):
        el = root.select_one('[unbox="wordorigin"], [title="Word Origin"]')
        if el is None:
            return ""
        body = el.select_one(".body") or el
        return re.sub(r"^Word Origin\s*", "", _txt(body))

    def _parse_entry(self, soup, config):
        opts = self._opts(config)
        root = self._entry_root(soup)
        if root is None:
            return None

        origin = self._parse_origin(root)
        self._clean(root)

        headword = self._parse_headword(root)
        defs, examples = self._parse_senses(root, opts)
        return {
            "id": self._entry_id(soup),
            "word": headword,
            "pos": self._parse_pos(root),
            "cefr": self._parse_cefr(root),
            "pronunciation": self._parse_pronunciation(
                root, opts.get("accent", "both")
            ),
            "inflections": self._parse_inflections(root, headword),
            "definitions": defs,
            "examples": examples,
            "etymology": origin,
        }

    # ---------------------------------------------------------------- merge

    @staticmethod
    def _uniq(items):
        seen, out = set(), []
        for i in items:
            if i and i not in seen:
                seen.add(i)
                out.append(i)
        return out

    def _combine(self, entries, opts):
        """Merge one or more homograph entries into a single payload."""
        # Tag definitions with their part of speech only when the merged
        # entries differ in POS (content: adj. vs v.); recreation_1/_2 are
        # both nouns, where the tag would just be noise.
        mixed_pos = len({e["pos"] for e in entries}) > 1
        def_lines = []
        for e in entries:
            tag = _POS_ABBREV.get(e["pos"], e["pos"])
            for d in e["definitions"]:
                def_lines.append(f"{tag} {d}" if (mixed_pos and tag) else d)

        max_defs = opts.get("max_definitions")
        if max_defs is not None:
            def_lines = def_lines[: int(max_defs)]
        if opts.get("number_definitions", True) and len(def_lines) > 1:
            def_lines = [f"{i}. {d}" for i, d in enumerate(def_lines, 1)]

        first = entries[0]
        return {
            "word": first["word"],
            "pos": "; ".join(self._uniq(e["pos"] for e in entries)),
            "cefr": first["cefr"],
            "pronunciation": "<br>".join(
                self._uniq(e["pronunciation"] for e in entries)
            ),
            "inflections": "; ".join(
                self._uniq(e["inflections"] for e in entries)
            ),
            "definition": "<br>".join(def_lines),
            "examples": "<br>".join(
                self._uniq(x for e in entries for x in e["examples"])
            ),
            "etymology": "<br>".join(
                self._uniq(e["etymology"] for e in entries)
            ),
        }

    # ---------------------------------------------------------------- fetch

    def _entry_id(self, soup):
        """The page's own entry id, e.g. 'recreation_2' ('' if unknown)."""
        root = self._entry_root(soup)
        return ((root.get("id") if root is not None else "") or "").strip()

    @staticmethod
    def _homograph_limit(opts):
        """Max number of *extra* entries to merge (0 = disabled)."""
        h = opts.get("homographs", True)
        if h is False or h is None:
            return 0
        if h is True:
            return 5
        return max(int(h), 0)

    def _sibling_numbers(self, soup, stem):
        """Homograph numbers the page itself links to (e.g. {1, 2}).

        Returns (numbers, has_related_block).  The "other results" column
        lists every numbered entry of the same headword, so when it exists
        we can avoid probing the site blindly.
        """
        pat = re.compile(
            r"/definition/[^/]+/%s_(\d+)(?:[#?/]|$)" % re.escape(stem),
            re.I,
        )
        nums = set()
        for a in soup.select("a[href]"):
            m = pat.search(a["href"])
            if m:
                nums.add(int(m.group(1)))
        has_block = soup.select_one("#relatedentries, #rightcolumn") is not None
        return nums, has_block

    def _collect_homographs(self, soup, first, word, config, limit):
        """Fetch the other numbered entries of *word*, in numeric order."""
        m = re.match(r"^(.*)_(\d+)$", first.get("id") or "")
        stem, have = (m.group(1), int(m.group(2))) if m else (_slug(word), 1)

        nums, has_block = self._sibling_numbers(soup, stem)
        seen_ids = {first.get("id")} if first.get("id") else set()
        found = {have: first}

        def load(n):
            nxt = self._get_soup_quiet(
                self._definition_url(f"{stem}_{n}", config), config
            )
            parsed = self._parse_entry(nxt, config) if nxt else None
            # Oxford may redirect an unknown number back to the base page;
            # an id we've already merged means "no such entry".
            if parsed is None or (parsed["id"] and parsed["id"] in seen_ids):
                return None
            if parsed["id"]:
                seen_ids.add(parsed["id"])
            return parsed

        if nums:
            # The page told us exactly which entries exist.
            for n in sorted(nums - {have})[:limit]:
                parsed = load(n)
                if parsed:
                    found[n] = parsed
        elif not has_block:
            # No signal on the page: probe lower numbers (we may have landed
            # on _2) and then upwards until the first miss.
            budget = limit
            for n in range(1, have):
                if budget <= 0:
                    break
                parsed = load(n)
                if parsed:
                    found[n] = parsed
                    budget -= 1
            n = have + 1
            while budget > 0:
                parsed = load(n)
                if parsed is None:
                    break
                found[n] = parsed
                budget -= 1
                n += 1
        # else: related-results block present but lists no siblings → single.

        return [found[n] for n in sorted(found)]

    def fetch(self, word, config):
        """Scrape Oxford Learner's Dictionaries and map to field indices."""
        if not word or not word.strip():
            return {}
        field_map = config.get("mapping", {})
        opts = self._opts(config)

        soup = self._load_entry_soup(word, config)
        if soup is None:
            self.message_callback(f"No Oxford entry for '{word}'")
            return {}

        entry = self._parse_entry(soup, config)
        if entry is None or not (entry["definitions"] or entry["word"]):
            self.message_callback(f"No Oxford entry data for '{word}'")
            return {}

        limit = self._homograph_limit(opts)
        entries = (
            self._collect_homographs(soup, entry, word, config, limit)
            if limit > 0
            else [entry]
        )

        payload = self._combine(entries, opts)

        data = {}
        for key, idx in field_map.items():
            if not isinstance(idx, int) or idx < 0:
                continue
            data[idx] = payload.get(key, "")

        if not data:
            self.message_callback(
                f"Oxford entry found for '{word}' but no fields mapped"
            )
        return data
