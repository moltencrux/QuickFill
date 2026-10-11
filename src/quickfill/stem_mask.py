"""
stem_mask.py – Lightweight English stemmer + headword masking for QuickFill.

Uses a pure-Python Porter stemmer (no NLTK dependency) so the add-on stays
self-contained.  Matches the approach used by AutoDefine Oxford.

Config keys (optional, under each source in config.json):

  "mask_fields" : [6, 7]          # field indices to process (default: [])
  "mask_mode"   : "tag"           # "tag" | "replace"  (default: "tag")
  "mask_tag"    : "span"          # HTML tag when mode=tag (default: "span")
  "mask_class"  : "qf-headword"   # CSS class when mode=tag (default: "qf-headword")
  "mask_placeholder" : "#$#"      # replacement text when mode=replace
"""

from __future__ import annotations
import re
from typing import Iterable


# ---------------------------------------------------------------------------
# Compact Porter Stemmer (faithful to the original algorithm)
# ---------------------------------------------------------------------------

class PorterStemmer:
    """Porter stemming algorithm – pure Python, no external deps."""

    def stem(self, word: str) -> str:
        if not word or len(word) <= 2:
            return word.lower()
        word = word.lower()
        # Step 1a
        if word.endswith("sses"):
            word = word[:-2]
        elif word.endswith("ies"):
            word = word[:-2]
        elif word.endswith("ss"):
            pass
        elif word.endswith("s"):
            word = word[:-1]
        # Step 1b
        if word.endswith("eed"):
            if self._m(word[:-3]) > 0:
                word = word[:-1]
        else:
            flag = False
            if word.endswith("ed") and self._has_vowel(word[:-2]):
                word = word[:-2]
                flag = True
            elif word.endswith("ing") and self._has_vowel(word[:-3]):
                word = word[:-3]
                flag = True
            if flag:
                if word.endswith(("at", "bl", "iz")):
                    word += "e"
                elif self._double_cons(word) and word[-1] not in "lsz":
                    word = word[:-1]
                elif self._m(word) == 1 and self._cvc(word):
                    word += "e"
        # Step 1c
        if word.endswith("y") and self._has_vowel(word[:-1]):
            word = word[:-1] + "i"
        # Step 2
        for suf, repl in (
            ("ational", "ate"), ("tional", "tion"), ("enci", "ence"),
            ("anci", "ance"), ("izer", "ize"), ("abli", "able"),
            ("alli", "al"), ("entli", "ent"), ("eli", "e"),
            ("ousli", "ous"), ("ization", "ize"), ("ation", "ate"),
            ("ator", "ate"), ("alism", "al"), ("iveness", "ive"),
            ("fulness", "ful"), ("ousness", "ous"), ("aliti", "al"),
            ("iviti", "ive"), ("biliti", "ble"),
        ):
            if word.endswith(suf):
                stem = word[: -len(suf)]
                if self._m(stem) > 0:
                    word = stem + repl
                break
        # Step 3
        for suf, repl in (
            ("icate", "ic"), ("ative", ""), ("alize", "al"),
            ("iciti", "ic"), ("ical", "ic"), ("ful", ""), ("ness", ""),
        ):
            if word.endswith(suf):
                stem = word[: -len(suf)]
                if self._m(stem) > 0:
                    word = stem + repl
                break
        # Step 4
        for suf in (
            "al", "ance", "ence", "er", "ic", "able", "ible", "ant",
            "ement", "ment", "ent", "ou", "ism", "ate", "iti", "ous",
            "ive", "ize",
        ):
            if word.endswith(suf):
                stem = word[: -len(suf)]
                if self._m(stem) > 1:
                    word = stem
                break
        else:
            if word.endswith("ion") and len(word) > 3 and word[-4] in "st":
                stem = word[:-3]
                if self._m(stem) > 1:
                    word = stem
        # Step 5a
        if word.endswith("e"):
            stem = word[:-1]
            m = self._m(stem)
            if m > 1 or (m == 1 and not self._cvc(stem)):
                word = stem
        # Step 5b
        if self._m(word) > 1 and self._double_cons(word) and word.endswith("l"):
            word = word[:-1]
        return word

    # --- helpers ---
    def _is_cons(self, word: str, i: int) -> bool:
        ch = word[i]
        if ch in "aeiou":
            return False
        if ch == "y":
            return i == 0 or not self._is_cons(word, i - 1)
        return True

    def _m(self, word: str) -> int:
        """Measure (number of VC sequences)."""
        n = i = 0
        L = len(word)
        while i < L and self._is_cons(word, i):
            i += 1
        while i < L:
            while i < L and not self._is_cons(word, i):
                i += 1
            if i >= L:
                break
            n += 1
            while i < L and self._is_cons(word, i):
                i += 1
        return n

    def _has_vowel(self, word: str) -> bool:
        return any(not self._is_cons(word, i) for i in range(len(word)))

    def _double_cons(self, word: str) -> bool:
        return len(word) >= 2 and word[-1] == word[-2] and self._is_cons(word, len(word) - 1)

    def _cvc(self, word: str) -> bool:
        if len(word) < 3:
            return False
        return (
            self._is_cons(word, len(word) - 1)
            and not self._is_cons(word, len(word) - 2)
            and self._is_cons(word, len(word) - 3)
            and word[-1] not in "wxy"
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_stemmer = PorterStemmer()
_TOKEN_RE = re.compile(r"\w+|[^\w\s]", re.UNICODE)


def unify(word: str) -> str:
    """Return the Porter stem of *word* (lower-cased)."""
    return _stemmer.stem(word)


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text)


def mask_same_stem(
    text: str,
    headword: str,
    *,
    mode: str = "tag",
    tag: str = "span",
    css_class: str = "qf-headword",
    placeholder: str = "#$#",
    extra_forms: Iterable[str] | None = None,
) -> str:
    """
    Scan *text* and either wrap or replace every token whose stem matches
    the stem of *headword* (plus any *extra_forms*).

    mode="tag"     → <span class="qf-headword">running</span>
    mode="replace" → #$#
    """
    if not text or not headword:
        return text

    target_stems = {unify(headword)}
    if extra_forms:
        target_stems.update(unify(f) for f in extra_forms if f)

    tokens = _tokenize(text)
    out: list[str] = []

    for tok in tokens:
        if tok.isalpha() and unify(tok) in target_stems:
            if mode == "replace":
                out.append(placeholder)
            else:
                out.append(f'<{tag} class="{css_class}">{tok}</{tag}>')
        else:
            out.append(tok)

    # Re-join: no space before punctuation
    result = ""
    for i, tok in enumerate(out):
        if i == 0:
            result = tok
        elif re.match(r"^[.,;:!?\)]$", tok):
            result += tok
        elif result and result[-1] in "(<":
            result += tok
        else:
            result += " " + tok
    return result


def apply_mask_to_fields(
    data: dict,
    headword: str,
    config: dict,
) -> dict:
    """
    Post-process the dict returned by a fetcher.

    Reads mask_* keys from *config* (the per-source config dict).
    Returns a new dict with the same keys; only listed fields are altered.
    """
    mask_fields = config.get("mask_fields") or []
    if not mask_fields:
        return data

    mode = config.get("mask_mode", "tag")
    tag = config.get("mask_tag", "span")
    css_class = config.get("mask_class", "qf-headword")
    placeholder = config.get("mask_placeholder", "#$#")
    extra = config.get("mask_extra_forms")

    result = dict(data)
    for idx in mask_fields:
        key = idx
        if key not in result and str(idx).isdigit() and int(idx) in result:
            key = int(idx)
        if key not in result:
            continue
        value = result[key]
        if isinstance(value, str) and value.strip():
            result[key] = mask_same_stem(
                value,
                headword,
                mode=mode,
                tag=tag,
                css_class=css_class,
                placeholder=placeholder,
                extra_forms=extra,
            )
    return result
