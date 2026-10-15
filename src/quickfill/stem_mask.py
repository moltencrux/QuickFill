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
# Word tokens in plain text only.
_WORD_RE = re.compile(r"\w+", re.UNICODE)
# Split into HTML tags (or comments) vs everything else (text content).
# Tags/comments are copied unchanged so we never alter tag names, class,
# id, or other attribute values.
_HTML_SPLIT_RE = re.compile(
    r"(<!--.*?-->|<[^>]+>)",
    re.DOTALL,
)

# Common English particles / prepositions that form phrasal verbs.
# Used only for headword *classification*, not as free-standing mask targets.
_PARTICLES = frozenset({
    "up", "out", "off", "in", "on", "down", "over", "away", "back",
    "through", "around", "about", "along", "aside", "by", "for", "with",
    "into", "onto", "across", "after", "against", "ahead", "apart",
    "behind", "forward", "together", "under", "upon", "without",
})


def unify(word: str) -> str:
    """Return the Porter stem of *word* (lower-cased)."""
    return _stemmer.stem(word)


def _split_words(phrase: str) -> list[str]:
    """Alphabetic word tokens of a headword / phrase."""
    return [m.group() for m in _WORD_RE.finditer(phrase) if m.group().isalpha()]


def classify_headword(headword: str) -> str:
    """
    Classify a headword for masking strategy.

    Returns:
        "single"  – one content word (default stem matching)
        "phrasal" – verb + particle(s), e.g. "look up", "get away with"
        "multi"   – other multi-word entries, e.g. "high school", "in spite of"
    """
    words = _split_words(headword)
    if len(words) <= 1:
        return "single"
    # Phrasal: first token is not itself a particle, and at least one
    # later token is a known particle (look up, run out of, put up with).
    if words[0].lower() not in _PARTICLES and any(
        w.lower() in _PARTICLES for w in words[1:]
    ):
        return "phrasal"
    return "multi"


def _wrap(fragment: str, *, mode: str, tag: str, css_class: str, placeholder: str) -> str:
    if mode == "replace":
        return placeholder
    return f'<{tag} class="{css_class}">{fragment}</{tag}>'


def _mask_stems_plain(
    text: str,
    target_stems: set[str],
    *,
    mode: str,
    tag: str,
    css_class: str,
    placeholder: str,
) -> str:
    """Single-word style: mask each token whose stem is in *target_stems*."""
    parts: list[str] = []
    last_end = 0

    for m in _WORD_RE.finditer(text):
        word = m.group()
        parts.append(text[last_end:m.start()])

        if word.isalpha() and unify(word) in target_stems:
            parts.append(
                _wrap(word, mode=mode, tag=tag, css_class=css_class, placeholder=placeholder)
            )
        else:
            parts.append(word)

        last_end = m.end()
    parts.append(text[last_end:])
    return "".join(parts)


def _mask_phrase_plain(
    text: str,
    patterns: list[list[str]],
    *,
    mode: str,
    tag: str,
    css_class: str,
    placeholder: str,
    verb_stem_first: bool,
) -> str:
    """
    Mask contiguous multi-word spans.

    *patterns* is a list of word-sequences (already lowercased tokens).
    If *verb_stem_first* is True (phrasal verbs), the first token of each
    pattern is matched by Porter stem; remaining tokens are exact
    case-insensitive matches (particles). Otherwise every token is matched
    by stem (multi-word entries).
    """
    matches = list(_WORD_RE.finditer(text))
    if not matches or not patterns:
        return text

    # Precompute stems for the first token when needed
    # Mark which match indices are the start of a hit, and the end index.
    hit_ranges: list[tuple[int, int]] = []  # inclusive match-index ranges
    n = len(matches)
    for i in range(n):
        for pat in patterns:
            plen = len(pat)
            if i + plen > n:
                continue
            ok = True
            for j, want in enumerate(pat):
                got = matches[i + j].group()
                if not got.isalpha():
                    ok = False
                    break
                if j == 0 and verb_stem_first:
                    if unify(got) != want:  # want already a stem
                        ok = False
                        break
                elif verb_stem_first:
                    if got.lower() != want:
                        ok = False
                        break
                else:
                    # multi-word: stem-match each part
                    if unify(got) != want:
                        ok = False
                        break
            if ok:
                hit_ranges.append((i, i + plen - 1))
                break

    if not hit_ranges:
        return text

    # Resolve overlaps by preferring earlier, then longer spans
    hit_ranges.sort(key=lambda r: (r[0], -(r[1] - r[0])))
    chosen: list[tuple[int, int]] = []
    occupied: set[int] = set()
    for start, end in hit_ranges:
        if any(k in occupied for k in range(start, end + 1)):
            continue
        chosen.append((start, end))
        occupied.update(range(start, end + 1))
    chosen.sort()

    parts: list[str] = []
    last_end = 0
    chosen_i = 0
    for idx, m in enumerate(matches):
        if chosen_i < len(chosen) and idx == chosen[chosen_i][0]:
            start_i, end_i = chosen[chosen_i]
            # verbatim span from first word start to last word end
            span = text[matches[start_i].start():matches[end_i].end()]
            parts.append(text[last_end:matches[start_i].start()])
            parts.append(
                _wrap(span, mode=mode, tag=tag, css_class=css_class, placeholder=placeholder)
            )
            last_end = matches[end_i].end()
            chosen_i += 1
        elif idx in occupied:
            continue  # already consumed inside a span
        else:
            parts.append(text[last_end:m.start()])
            parts.append(m.group())
            last_end = m.end()
    parts.append(text[last_end:])
    return "".join(parts)


def _patterns_for_headword(
    headword: str,
    kind: str,
    extra_forms: Iterable[str] | None,
) -> tuple[list[list[str]], bool]:
    """
    Build match patterns for *headword*.

    Returns (patterns, verb_stem_first).
    Each pattern is a list of tokens: for phrasal, [verb_stem, particle, ...];
    for multi, [stem, stem, ...].
    """
    patterns: list[list[str]] = []

    def add_phrase(phrase: str) -> None:
        words = _split_words(phrase)
        if not words:
            return
        if kind == "phrasal":
            patterns.append([unify(words[0]), *[w.lower() for w in words[1:]]])
        else:
            patterns.append([unify(w) for w in words])

    add_phrase(headword)
    if extra_forms:
        for form in extra_forms:
            if form:
                add_phrase(form)

    return patterns, (kind == "phrasal")


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
    Scan *text* and wrap/replace occurrences of *headword* (and *extra_forms*).

    Strategy depends on headword shape:

    - **single** word: mask every token with the same Porter stem
      (run / running / runs).
    - **phrasal** verb (verb + particle): mask contiguous spans where the
      verb matches by stem and particles match exactly
      (look up / looked up; bare "up" is *not* masked).
    - **multi** word (other phrases): mask contiguous spans where each
      part matches by stem (high school).

    Only text *outside* HTML tags/comments is modified. Spacing is preserved.

    mode="tag"     → <span class="qf-headword">…</span>
    mode="replace" → #$#
    """
    if not text or not headword:
        return text

    kind = classify_headword(headword)
    kwargs = dict(mode=mode, tag=tag, css_class=css_class, placeholder=placeholder)

    pieces = _HTML_SPLIT_RE.split(text)
    out: list[str] = []

    if kind == "single":
        target_stems = {unify(headword)}
        if extra_forms:
            # only single-token extras for stem set
            for f in extra_forms:
                words = _split_words(f) if f else []
                if len(words) == 1:
                    target_stems.add(unify(words[0]))
                elif words:
                    # multi-word extra alongside a single headword: rare; ignore here
                    pass
        for piece in pieces:
            if not piece:
                continue
            if piece.startswith("<"):
                out.append(piece)
            else:
                out.append(_mask_stems_plain(piece, target_stems, **kwargs))
        return "".join(out)

    patterns, verb_stem_first = _patterns_for_headword(headword, kind, extra_forms)
    for piece in pieces:
        if not piece:
            continue
        if piece.startswith("<"):
            # HTML tag or comment — never alter
            out.append(piece)
        else:
            out.append(
                _mask_phrase_plain(
                    piece, patterns, verb_stem_first=verb_stem_first, **kwargs
                )
            )
    return "".join(out)


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
