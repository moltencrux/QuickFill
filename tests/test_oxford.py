#!/usr/bin/env python3 -B
"""Tests for the Oxford Learner's Dictionaries fetcher.

    python tests/test_oxford.py          # offline, parses a fixture
    python tests/test_oxford.py --live   # hits the real site, prints result

The fixture is hand-written from the OALD markup (class names as used by the
AutoDefine add-on plus the newer ``unbox``/``cefr`` attributes).  If Oxford
changes its markup, refresh it from a saved page.
"""
import os
import sys
import unittest

sys.path.append(os.path.abspath(os.path.dirname(__file__) + "/../src"))

from bs4 import BeautifulSoup

import quickfill
from quickfill.fetchers import OxfordFetcher

FIXTURE = """
<html><body><div id="entryContent"><div class="entry" id="memorize_1">
<div class="top-container"><div class="webtop">
  <h1 class="headword">memorize<span class="hm">1</span></h1>
  <span class="pos">verb</span>
  <span class="symbols"><a href="#"><span class="ox3ksym_b1"></span></a></span>
  <span class="phonetics">
    <div class="phons_br" geo="br"><span class="phon">/ˈmeməraɪz/</span></div>
    <div class="phons_n_am" geo="n_am"><span class="phon">/ˈmeməraɪz/</span></div>
  </span>
</div></div>
<span class="unbox" unbox="verb_forms"><table class="verb_forms_table">
 <tr class="verb_form" form="root"><td class="verb_form">
   <span class="vf_prefix">present simple I / you / we / they</span> memorize
   <div class="phons_br"><span class="phon">/ˈmeməraɪz/</span></div></td></tr>
 <tr class="verb_form" form="third"><td class="verb_form">
   <span class="vf_prefix">he / she / it</span> memorizes
   <div class="phons_br"><span class="phon">/ˈmeməraɪzɪz/</span></div></td></tr>
 <tr class="verb_form" form="past"><td class="verb_form">
   <span class="vf_prefix">past simple</span> memorized</td></tr>
 <tr class="verb_form" form="ing"><td class="verb_form">
   <span class="vf_prefix">-ing form</span> memorizing</td></tr>
</table></span>
<ol class="senses_single sense_single">
 <li class="sense" cefr="b1">
  <span class="sensetop"><span class="grammar">[transitive]</span>
   <span class="def">memorize something to learn something carefully so that
   you can remember it exactly</span></span>
  <ul class="examples">
   <li><span class="x">to memorize a poem</span></li>
   <li><span class="x">She memorized the <a href="#">whole</a> list.</span></li>
  </ul>
  <span class="unbox" unbox="extra_examples"><ul class="examples">
   <li><span class="unx">Please memorize your PIN number immediately.</span></li>
  </ul></span>
  <span class="unbox" unbox="colloc" title="Oxford Collocations Dictionary">
   <ul class="examples"><li><span class="x">detail</span></li></ul></span>
 </li>
 <li class="sense">
  <span class="labels">(informal)</span>
  <span class="def">to remember something</span>
 </li>
</ol>
<span class="unbox" unbox="wordorigin"><span class="box_title">Word Origin</span>
 <span class="body">late 15th cent.: from Latin memorabilis.</span></span>
</div></div></body></html>
"""

CFG = {
    "fetcher": "oxford",
    "mapping": {
        "word": 0, "pronunciation": 1, "definition": 2, "examples": 3,
        "inflections": 4, "pos": 5, "etymology": 6, "cefr": 7, "unused": -1,
    },
    "config": {},
}


NOT_FOUND = ("<html><body><title>Oxford Learner's Dictionaries</title>"
             "<div>Page not found</div></body></html>")


class OfflineFetcher(OxfordFetcher):
    """Serves fixtures instead of touching the network.

    ``pages`` maps a URL's last path segment ('recreation_2') to HTML;
    anything else gets a not-found page.  ``requested`` records the lookups.
    """

    def __init__(self, html=FIXTURE, pages=None):
        super().__init__()
        self.html = html
        self.pages = pages or {}
        self.requested = []
        self.messages = []
        self.message_callback = self.messages.append

    def acquire_soup(self, url, config=None, **kw):
        return BeautifulSoup(self.html, "html.parser")

    def _get_soup(self, url, config=None, **kw):
        key = url.rstrip("/").rsplit("/", 1)[-1]
        self.requested.append(key)
        return BeautifulSoup(self.pages.get(key, NOT_FOUND), "html.parser")


def recreation_page(n, related=True):
    """Two-homograph page in the shape of the real recreation_1/_2 entries."""
    if n == 1:
        pron, defs, origin = "/ˌriːkriˈeɪʃn/", (
            '<li class="sense"><span class="def">the act or process of making '
            'something exist again</span><ul class="examples"><li><span '
            'class="x">a recreation of the sights and sounds of his '
            'childhood</span></li></ul></li>'), ""
    else:
        pron, defs = "/ˌrekriˈeɪʃn/", (
            '<li class="sense"><span class="grammar">[uncountable]</span>'
            '<span class="def">the fact of people doing things for pleasure'
            '</span><ul class="examples"><li><span class="x">land for '
            'recreation</span></li></ul></li>'
            '<li class="sense"><span class="grammar">[countable]</span>'
            '<span class="def">a particular activity that somebody does when '
            'they are not working</span><ul class="examples"><li><span '
            'class="x">His recreations include golf.</span></li></ul>'
            '<span class="unbox" unbox="synonyms"><ul class="examples"><li>'
            '<span class="x">live entertainment seven nights a week</span>'
            '</li></ul></span></li>')
        origin = ('<span class="unbox" unbox="wordorigin"><span class='
                  '"box_title">Word Origin</span><span class="body">late '
                  'Middle English: from Latin recreatio.</span></span>')
    side = ""
    if related:
        side = ('<div id="rightcolumn"><div id="relatedentries"><dl><dd><ul>'
                '<li><a href="https://www.oxfordlearnersdictionaries.com/'
                'definition/english/recreation_1">recreation</a></li>'
                '<li><a href="/definition/english/recreation_2">recreation'
                '</a></li><li><a href="/definition/english/recreation-ground">'
                'recreation ground</a></li></ul></dd></dl></div></div>')
    return (
        f'<html><body><div id="entryContent"><div class="entry" '
        f'id="recreation_{n}"><div class="webtop"><h1 class="headword">'
        f'recreation</h1><span class="pos">noun</span>'
        f'<div class="phons_br"><span class="phon">{pron}</span></div>'
        f'<div class="phons_n_am"><span class="phon">{pron}</span></div>'
        f'</div><ol class="senses_multiple">{defs}</ol>{origin}</div></div>'
        f'{side}</body></html>'
    )


class OxfordTests(unittest.TestCase):
    def run_fetch(self, **opts):
        cfg = {**CFG, "config": opts}
        return OfflineFetcher().fetch("memorize", cfg)

    def test_registered(self):
        from quickfill.fetchers import all_fetchers
        self.assertIn(OxfordFetcher, all_fetchers)
        self.assertEqual(OxfordFetcher.source_name(), "oxford")

    def test_basic_fields(self):
        r = self.run_fetch()
        self.assertEqual(r[0], "memorize")            # .hm stripped
        self.assertEqual(r[1], "/ˈmeməraɪz/")         # BrE == NAmE → folded
        self.assertEqual(r[4], "memorizes; memorized; memorizing")
        self.assertEqual(r[5], "verb")
        self.assertEqual(r[7], "B1")
        self.assertEqual(r[6], "late 15th cent.: from Latin memorabilis.")
        self.assertNotIn(-1, r)

    def test_definitions(self):
        r = self.run_fetch()
        lines = r[2].split("<br>")
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[0].startswith("1. memorize something to learn"))
        self.assertNotIn("[transitive]", lines[0])
        self.assertEqual(lines[1], "2. (informal) to remember something")
        self.assertNotIn("  ", r[2])                  # whitespace collapsed

    def test_grammar_option(self):
        r = self.run_fetch(include_grammar=True)
        self.assertIn("[transitive] memorize something", r[2])

    def test_examples(self):
        r = self.run_fetch()
        self.assertEqual(
            r[3], "to memorize a poem<br>She memorized the whole list."
        )
        self.assertNotIn("detail", r[3])               # collocation box
        self.assertNotIn("PIN", r[3])                  # extra examples off

    def test_extra_examples_and_cap(self):
        r = self.run_fetch(include_extra_examples=True)
        self.assertTrue(r[3].endswith("Please memorize your PIN number immediately."))
        r = self.run_fetch(include_extra_examples=True, max_examples_per_sense=1)
        self.assertEqual(
            r[3],
            "to memorize a poem<br>Please memorize your PIN number immediately.",
        )

    def test_definition_options(self):
        r = self.run_fetch(max_definitions=1)
        self.assertEqual(r[2].count("<br>"), 0)
        self.assertFalse(r[2].startswith("1."))        # single def: no number
        r = self.run_fetch(number_definitions=False)
        self.assertTrue(r[2].startswith("memorize something"))

    def test_split_accents(self):
        html = FIXTURE.replace(
            '<div class="phons_n_am" geo="n_am"><span class="phon">/ˈmeməraɪz/',
            '<div class="phons_n_am" geo="n_am"><span class="phon">/ˈmɛməraɪz/',
        )
        f = OfflineFetcher(html)
        r = f.fetch("memorize", {**CFG, "config": {}})
        self.assertEqual(r[1], "BrE /ˈmeməraɪz/<br>NAmE /ˈmɛməraɪz/")
        r = f.fetch("memorize", {**CFG, "config": {"accent": "us"}})
        self.assertEqual(r[1], "/ˈmɛməraɪz/")

    # ---- homographs (recreation_1 / recreation_2) -------------------------

    def recreation(self, related=True, **opts):
        pages = {
            "recreation_1": recreation_page(1, related),
            "recreation_2": recreation_page(2, related),
        }
        f = OfflineFetcher(pages["recreation_1"], pages)
        cfg = {**CFG, "config": opts}
        return f, f.fetch("recreation", cfg)

    def test_homographs_merged(self):
        f, r = self.recreation()
        lines = r[2].split("<br>")
        self.assertEqual(len(lines), 3)
        self.assertTrue(lines[0].startswith("1. the act or process"))
        self.assertTrue(lines[1].startswith("2. the fact of people"))
        self.assertTrue(lines[2].startswith("3. a particular activity"))
        self.assertNotIn("n.", r[2])           # same POS → no tag
        self.assertEqual(r[5], "noun")
        # both pronunciations, in entry order
        self.assertEqual(r[1], "/ˌriːkriˈeɪʃn/<br>/ˌrekriˈeɪʃn/")
        self.assertIn("late Middle English", r[6])
        # page links told us what exists: no blind probing of _3
        self.assertEqual(f.requested, ["recreation_2"])

    def test_homograph_examples_skip_thesaurus_box(self):
        _, r = self.recreation()
        self.assertEqual(
            r[3],
            "a recreation of the sights and sounds of his childhood<br>"
            "land for recreation<br>His recreations include golf.",
        )
        self.assertNotIn("live entertainment", r[3])

    def test_homographs_disabled(self):
        f, r = self.recreation(homographs=False)
        self.assertEqual(f.requested, [])
        self.assertEqual(r[2].count("<br>"), 0)
        self.assertIn("making something exist again", r[2])

    def test_homograph_probe_without_related_block(self):
        f, r = self.recreation(related=False)
        self.assertEqual(r[2].count("<br>"), 2)
        self.assertEqual(f.requested, ["recreation_2", "recreation_3"])

    def test_homograph_cap_and_landing_on_later_entry(self):
        pages = {"recreation_1": recreation_page(1, False),
                 "recreation_2": recreation_page(2, False)}
        # user landed on _2 (e.g. via search): _1 must still be merged first
        f = OfflineFetcher(pages["recreation_2"], pages)
        r = f.fetch("recreation", CFG)
        self.assertTrue(r[2].startswith("1. the act or process"))
        self.assertEqual(r[2].count("<br>"), 2)

    def test_redirect_to_base_is_not_duplicated(self):
        # Oxford may answer an unknown _N with the base page again.
        page = recreation_page(2, False)
        f = OfflineFetcher(page, {"recreation_3": page})
        r = f.fetch("recreation", CFG)
        self.assertEqual(r[2].count("<br>"), 1)   # only its own 2 senses

    def test_mixed_pos_gets_tags(self):
        a = recreation_page(1).replace(">noun<", ">adjective<")
        b = recreation_page(2).replace(">noun<", ">verb<")
        f = OfflineFetcher(a, {"recreation_1": a, "recreation_2": b})
        r = f.fetch("recreation", CFG)
        self.assertTrue(r[2].startswith("1. adj. the act"))
        self.assertIn("v. the fact", r[2])
        self.assertEqual(r[5], "adjective; verb")


    def test_not_found(self):
        f = OfflineFetcher("<html><body><div id='search-results'>"
                           "<h1>No exact match found for 'zzzq'</h1></div></body></html>")
        self.assertEqual(f.fetch("zzzq", CFG), {})
        self.assertTrue(any("No Oxford entry" in m for m in f.messages))

    def test_page_ok_accepts_not_found_pages(self):
        f = OxfordFetcher()
        pad = "x" * 600
        self.assertTrue(f.page_ok("<title>Oxford Learner's</title>" + pad))
        self.assertFalse(f.page_ok("<html>Just a moment...</html>"))


if __name__ == "__main__":
    if "--live" in sys.argv:
        from pprint import pprint
        word = next((a for a in sys.argv[1:] if not a.startswith("-")), "memorize")
        pprint(OxfordFetcher(print).fetch(word, CFG))
    else:
        unittest.main()
