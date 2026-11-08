"""Download dictionary pronunciation audio into Anki's media collection.

Fetchers may return **audio refs** instead of plain strings for mapping keys
such as ``audio``, ``audio_us``, ``audio_uk``.  ``resolve_audio_refs`` turns
those refs into ``[sound:filename.mp3]`` tags by writing the bytes through
``col.media.write_data``.

An audio ref is a dict shaped like::

    {
        "__qf_audio__": True,
        "url": "https://…/word.mp3",
        "filename": "optional_preferred_name.mp3",  # basename only
    }

or a list of such dicts (multiple regions / variants).  Plain http(s) URL
strings are also accepted for convenience.

Reserved mapping keys
---------------------
* ``audio``              – preferred region (see config ``audio_region``)
* ``audio_us``           – US pronunciation only
* ``audio_uk``           – UK / GB pronunciation only
* ``audio_url``          – remote URL string, **not** downloaded
* ``audio_inflections``  – related-form / run-on audio (e.g. MW *castability*),
  kept separate from headword ``audio`` so it is not mixed in

Config (under the source's ``config`` object)
---------------------------------------------
* ``audio_region``: ``"us"`` | ``"uk"`` | ``"all"`` (default ``"us"``)
* ``append_audio_to_pronunciation``: bool – if true and both pronunciation
  and audio are available, append ``[sound:…]`` to the pronunciation field
"""

from __future__ import annotations

import os
import re
from typing import Any, Callable, Iterable
from urllib.parse import unquote, urlparse

import requests

AUDIO_MARKER = "__qf_audio__"

# Meta key fetchers may set so append-to-pronunciation works even when
# ``audio`` is not mapped to its own field.
AUDIO_APPEND_META = "_qf_audio_refs"

# Mapping keys that mean "download this into [sound:]"
_DOWNLOAD_KEYS = frozenset({
    "audio",
    "audio_us",
    "audio_uk",
    # Related-form / run-on audio (kept separate from headword ``audio``)
    "audio_inflections",
})
# Mapping keys that stay as a raw URL string
_URL_KEYS = frozenset({"audio_url", "audio_us_url", "audio_uk_url"})

_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def audio_ref(url: str, filename: str | None = None) -> dict:
    """Build a single audio-ref dict for fetcher payloads."""
    return {AUDIO_MARKER: True, "url": url, "filename": filename or ""}


def is_audio_ref(value: Any) -> bool:
    if isinstance(value, dict) and value.get(AUDIO_MARKER):
        return True
    if isinstance(value, list) and value and all(is_audio_ref(v) for v in value):
        return True
    if isinstance(value, str) and value.startswith(("http://", "https://")):
        # Only treat as audio when the path looks like media
        path = urlparse(value).path.lower()
        return path.endswith((".mp3", ".ogg", ".wav", ".m4a", ".aac", ".opus"))
    return False


def _basename_from_url(url: str) -> str:
    path = unquote(urlparse(url).path or "")
    name = os.path.basename(path) or "audio.mp3"
    return name


def safe_filename(preferred: str | None, url: str, prefix: str = "qf") -> str:
    """Pick a collection-safe basename (no path separators)."""
    raw = (preferred or "").strip() or _basename_from_url(url)
    raw = os.path.basename(raw.replace("\\", "/"))
    stem, ext = os.path.splitext(raw)
    if not ext:
        # Infer from URL path
        url_ext = os.path.splitext(_basename_from_url(url))[1]
        ext = url_ext or ".mp3"
    stem = _SAFE_NAME_RE.sub("_", stem).strip("._") or prefix
    # Keep names reasonably short
    if len(stem) > 80:
        stem = stem[:80]
    return f"{stem}{ext.lower()}"


def download_audio_bytes(
    url: str,
    *,
    timeout: int = 20,
    headers: dict | None = None,
    session: requests.Session | None = None,
) -> bytes | None:
    """GET *url* and return the body, or None on failure."""
    if not url:
        return None
    try:
        if session is not None:
            r = session.get(url, timeout=timeout, headers=headers)
        else:
            r = requests.get(
                url,
                timeout=timeout,
                headers=headers
                or {
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/131.0.0.0 Safari/537.36"
                    )
                },
            )
        r.raise_for_status()
        data = r.content
        if not data or len(data) < 64:
            return None
        return data
    except Exception:
        return None


def write_audio_to_col(col, url: str, filename: str | None = None) -> str | None:
    """Download *url* and write into the collection media folder.

    Returns the (possibly renamed) filename suitable for ``[sound:…]``,
    or None if download/write failed.
    """
    data = download_audio_bytes(url)
    if not data:
        return None
    fname = safe_filename(filename, url)
    try:
        return col.media.write_data(fname, data)
    except Exception:
        return None


def sound_tag(filename: str) -> str:
    return f"[sound:{filename}]"


def refs_to_sound_tags(
    col,
    refs: Any,
    *,
    message: Callable[[str], None] | None = None,
) -> str:
    """Resolve one ref, a list of refs, or a bare URL into sound-tag text."""
    msg = message or (lambda _m: None)
    if refs is None or refs == "":
        return ""

    items: list[Any]
    if isinstance(refs, list):
        items = refs
    else:
        items = [refs]

    tags: list[str] = []
    seen: set[str] = set()
    for item in items:
        url = None
        preferred = None
        if isinstance(item, dict) and item.get(AUDIO_MARKER):
            url = item.get("url") or ""
            preferred = item.get("filename") or None
        elif isinstance(item, str) and item.startswith(("http://", "https://")):
            url = item
        else:
            continue
        if not url:
            continue
        fname = write_audio_to_col(col, url, preferred)
        if not fname:
            msg(f"Audio download failed: {url}")
            continue
        if fname in seen:
            continue
        seen.add(fname)
        tags.append(sound_tag(fname))
    return "".join(tags)


def pick_region_urls(
    urls_by_region: dict[str, list[str]],
    region: str,
) -> list[str]:
    """Select URL list for *region* (``us`` / ``uk`` / ``all``).

    *urls_by_region* keys should be normalised lowercase region codes
    (``us``, ``uk``, ``gb`` → treated as ``uk``).  Empty-string key is
    "unknown / single" region.
    """
    norm: dict[str, list[str]] = {}
    for k, v in (urls_by_region or {}).items():
        key = (k or "").lower().strip()
        if key in ("gb", "en-gb", "en_gb", "br"):
            key = "uk"
        elif key in ("en-us", "en_us", "american"):
            key = "us"
        norm.setdefault(key, [])
        for u in v or []:
            if u and u not in norm[key]:
                norm[key].append(u)

    region = (region or "us").lower().strip()
    if region == "all":
        out: list[str] = []
        for key in sorted(norm.keys()):
            for u in norm[key]:
                if u not in out:
                    out.append(u)
        return out

    if region in ("uk", "gb"):
        order = ("uk", "us", "")
    else:
        order = ("us", "uk", "")

    for key in order:
        if norm.get(key):
            return list(norm[key])
    # Any leftover region
    for v in norm.values():
        if v:
            return list(v)
    return []


def resolve_audio_in_result(
    col,
    data: dict,
    config: dict | None = None,
    *,
    message: Callable[[str], None] | None = None,
) -> dict:
    """Walk a fetcher result dict and replace audio refs with ``[sound:]`` tags.

    Also honours ``append_audio_to_pronunciation`` when pronunciation was
    mapped to an integer field index and audio was produced (via an
    ``audio*`` mapping key or the ``_qf_audio_refs`` meta entry).
    """
    if not data:
        return data

    cfg = (config or {}).get("config") or {}
    append = bool(cfg.get("append_audio_to_pronunciation"))
    field_map = (config or {}).get("mapping") or {}

    # Inverse: field index → mapping key (first wins)
    idx_to_key: dict[int, str] = {}
    for key, idx in field_map.items():
        if isinstance(idx, int) and idx >= 0 and idx not in idx_to_key:
            idx_to_key[idx] = key

    out: dict = {}
    audio_tags_for_append: list[str] = []
    pronunciation_idx: int | None = None
    meta_refs = data.get(AUDIO_APPEND_META)

    for idx, val in data.items():
        # Drop internal meta; keep other non-int keys (status, message, …)
        if not isinstance(idx, int):
            if idx == AUDIO_APPEND_META:
                continue
            out[idx] = val
            continue

        key = idx_to_key.get(idx, "")
        if key == "pronunciation":
            pronunciation_idx = idx

        if key in _URL_KEYS:
            # Keep remote URL as plain text (no download)
            if is_audio_ref(val) and isinstance(val, dict):
                out[idx] = val.get("url") or ""
            elif isinstance(val, list) and val:
                first = val[0]
                out[idx] = (
                    first.get("url", "")
                    if isinstance(first, dict)
                    else (first if isinstance(first, str) else "")
                )
            else:
                out[idx] = val if isinstance(val, str) else ""
            continue

        if key in _DOWNLOAD_KEYS or is_audio_ref(val):
            tags = refs_to_sound_tags(col, val, message=message)
            out[idx] = tags
            if tags and key in ("audio", "audio_us", "audio_uk"):
                audio_tags_for_append.append(tags)
            continue

        out[idx] = val

    # If nothing was mapped to an audio field, still resolve meta for append
    if append and not audio_tags_for_append and meta_refs is not None:
        tags = refs_to_sound_tags(col, meta_refs, message=message)
        if tags:
            audio_tags_for_append.append(tags)

    if append and pronunciation_idx is not None and audio_tags_for_append:
        existing = out.get(pronunciation_idx) or ""
        if isinstance(existing, str):
            # Avoid duplicating tags already present
            extra = "".join(
                t for t in audio_tags_for_append if t and t not in existing
            )
            if extra:
                sep = "" if not existing or existing.endswith((">", "]", " ")) else " "
                out[pronunciation_idx] = f"{existing}{sep}{extra}"

    return out


def build_region_audio_payload(
    urls_by_region: dict[str, list[str]],
    *,
    region_pref: str = "us",
    word: str = "",
) -> dict[str, Any]:
    """Helper for fetchers: turn region→URL maps into payload keys.

    Returns a dict that may include ``audio``, ``audio_us``, ``audio_uk``,
    ``audio_url`` values (audio refs or strings).  Caller merges into the
    normal field payload before applying the mapping.
    """
    def _refs(urls: Iterable[str], region_label: str) -> list[dict]:
        refs = []
        for i, u in enumerate(urls):
            if not u:
                continue
            hint = ""
            if word:
                label = region_label or "x"
                hint = f"qf_{word}_{label}" + (f"_{i}" if i else "") + ".mp3"
            refs.append(audio_ref(u, hint))
        return refs

    us = pick_region_urls(urls_by_region, "us")
    uk = pick_region_urls(urls_by_region, "uk")
    preferred = pick_region_urls(urls_by_region, region_pref)

    payload: dict[str, Any] = {}
    if preferred:
        payload["audio"] = _refs(preferred, region_pref if region_pref != "all" else "all")
        payload["audio_url"] = preferred[0]
    if us:
        payload["audio_us"] = _refs(us, "us")
        payload["audio_us_url"] = us[0]
    if uk:
        payload["audio_uk"] = _refs(uk, "uk")
        payload["audio_uk_url"] = uk[0]
    return payload
