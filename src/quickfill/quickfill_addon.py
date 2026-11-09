from aqt import gui_hooks, mw
from aqt.qt import QMenu, QAction, QIcon, QCursor, QKeySequence
from aqt.utils import tooltip, showWarning
from aqt.editor import Editor
from aqt.theme import theme_manager
import os
from .fetcher import FetcherRegistry


def _addon_package() -> str:
    return mw.addonManager.addonFromModule(__name__)


# Load config and icon
CONFIG = mw.addonManager.getConfig(_addon_package()) or {}
ICON_PATH = os.path.join(os.path.dirname(__file__), "images", "quickfill.svg")

# Manual source override per note type. Applied only when the override still
# matches the current deck *and* the deck context is the same one for which the
# user made the pick (so a stale "(any deck)" choice does not stick after the
# real deck is resolved).
_selected_source: dict[str, dict] = {}
_selected_source_deck: dict[str, str | None] = {}

# Sentinel used in config GUI / stored sources for unrestricted deck scope.
_ANY_DECK = "(any deck)"

quickfill = FetcherRegistry()


def _normalize_deck(deck: str | None) -> str:
    if not deck:
        return _ANY_DECK
    deck = deck.strip()
    return deck if deck else _ANY_DECK


def _deck_depth(deck: str | None) -> int:
    """Specificity rank: (any deck) = -1, top-level = 0, one :: = 1, …"""
    d = _normalize_deck(deck)
    if d == _ANY_DECK:
        return -1
    return d.count("::")


def deck_is_prefix(config_deck: str | None, card_deck: str | None) -> bool:
    """
    True if config_deck is a hierarchical prefix of card_deck (Anki :: paths),
    or if the source is unrestricted ((any deck) / missing).
    """
    cfg = _normalize_deck(config_deck)
    if cfg == _ANY_DECK:
        return True
    if not card_deck:
        # Specific deck scope requires a known card deck.
        return False
    card = card_deck.strip()
    return card == cfg or card.startswith(cfg + "::")


def _source_identity(src: dict) -> tuple:
    """Stable identity for matching a manual override after config reload."""
    return (
        _normalize_deck(src.get("deck")),
        (src.get("name") or "").strip(),
        src.get("fetcher"),
    )


def _find_override_in_sources(override: dict | None, sources: list) -> dict | None:
    if not override or not sources:
        return None
    # Prefer object identity (same session, no config reload).
    for s in sources:
        if s is override:
            return s
    key = _source_identity(override)
    for s in sources:
        if _source_identity(s) == key:
            return s
    return None


def _display_key(src: dict) -> str:
    """Group key so deck-scoped variants of the same label collapse together."""
    name = (src.get("name") or "").strip()
    if name:
        return name
    return str(src.get("fetcher") or "")


def sources_for_deck(
    model_name: str,
    deck_name: str | None = None,
    *,
    sources: list | None = None,
) -> list:
    """
    Sources that apply to (note type, card deck), collapsed by display name.

    For each display name, only the most-specific matching deck variant is kept.
    That way two MW rows (any-deck + Teaching::English) become one MW entry,
    while Cambridge (any-deck) still appears alongside it.
    Order follows first occurrence in config (stable).
    """
    if sources is None:
        sources = CONFIG.get("models", {}).get(model_name, [])
    if not sources:
        return []

    matching = [s for s in sources if deck_is_prefix(s.get("deck"), deck_name)]
    if not matching:
        return []

    best_by_key: dict[str, dict] = {}
    order: list[str] = []
    for s in matching:
        key = _display_key(s)
        prev = best_by_key.get(key)
        if prev is None:
            best_by_key[key] = s
            order.append(key)
        elif _deck_depth(s.get("deck")) > _deck_depth(prev.get("deck")):
            best_by_key[key] = s
    return [best_by_key[k] for k in order]


def select_source_for_deck(
    model_name: str,
    deck_name: str | None = None,
    *,
    sources: list | None = None,
) -> dict | None:
    """
    Pick the source for (note type, card deck).

    Candidates are matching sources collapsed by display name (most-specific
    deck variant per name). Manual override wins when it is still one of those
    candidates and was chosen for this same deck context; otherwise the
    most-specific candidate (by deck depth, then config order) is used.
    """
    if sources is None:
        sources = CONFIG.get("models", {}).get(model_name, [])
    candidates = sources_for_deck(model_name, deck_name, sources=sources)
    if not candidates:
        return None

    override = _find_override_in_sources(
        _selected_source.get(model_name), sources
    )
    if (
        override is not None
        and _selected_source_deck.get(model_name) == deck_name
    ):
        # Map override to the collapsed candidate with the same display key
        # (so picking "MW" stays on the Teaching::English MW row).
        okey = _display_key(override)
        for c in candidates:
            if _display_key(c) == okey:
                return c

    # Default: most-specific deck among collapsed candidates; stable on ties.
    return max(
        candidates,
        key=lambda s: (_deck_depth(s.get("deck")), -candidates.index(s)),
    )


def get_current_source(model_name: str, deck_name: str | None = None):
    """
    Resolve the source for a note type (and optional deck).

    Called from the editor and from bulk fill. When deck_name is omitted,
    only unrestricted sources match unless a manual override is set.
    """
    return select_source_for_deck(model_name, deck_name)


def _deck_name_from_id(did) -> str | None:
    if did is None or not mw.col:
        return None
    try:
        name = mw.col.decks.name(did)
        return name or None
    except Exception:
        return None


def _deck_name_from_chooser(dc) -> str | None:
    """Resolve a deck name from an aqt DeckChooser (or similar) object."""
    if dc is None:
        return None
    try:
        if hasattr(dc, "selected_deck_name"):
            name = dc.selected_deck_name()
            if name:
                return name
        # Modern AddCards DeckChooser: selected_deck_id property
        if hasattr(dc, "selected_deck_id"):
            did = dc.selected_deck_id
            name = _deck_name_from_id(did)
            if name:
                return name
        # Older Anki: selectedDeck() -> (id, name) or deck id
        if hasattr(dc, "selectedDeck"):
            sel = dc.selectedDeck()
            if isinstance(sel, (list, tuple)) and len(sel) >= 2:
                return sel[1] or None
            if isinstance(sel, int):
                return _deck_name_from_id(sel)
        if hasattr(dc, "deckName"):
            name = dc.deckName()
            if name:
                return name
    except Exception:
        pass
    return None


def _deck_name_for_note(note) -> str | None:
    """Deck name of the note's first card, if any."""
    if not note or not mw.col:
        return None
    try:
        cids = []
        if hasattr(note, "card_ids"):
            cids = list(note.card_ids())
        if not cids and hasattr(note, "cards"):
            cards = note.cards()
            if cards:
                return _deck_name_from_id(cards[0].did)
        if cids:
            card = mw.col.get_card(cids[0])
            return _deck_name_from_id(card.did)
    except Exception:
        pass
    return None


def _deck_name_for_editor(editor: Editor) -> str | None:
    """
    Deck the note is (or will be) filed under.

    Resolution order:
    1. DeckChooser on the editor (rare)
    2. DeckChooser on a parent AddCards dialog (the usual Add path —
       chooser lives on AddCards, not on Editor)
    3. Existing card deck for the note
    4. Collection current deck (mw.col.decks.current / get_current_id)
    """
    # 1. Direct attribute on editor
    dc = getattr(editor, "deckChooser", None) or getattr(editor, "deck_chooser", None)
    name = _deck_name_from_chooser(dc)
    if name:
        return name

    # 2. Walk parents for AddCards.deck_chooser / .deckChooser
    try:
        w = getattr(editor, "widget", None) or getattr(editor, "parentWindow", None)
        seen = set()
        while w is not None and id(w) not in seen:
            seen.add(id(w))
            for attr in ("deck_chooser", "deckChooser"):
                name = _deck_name_from_chooser(getattr(w, attr, None))
                if name:
                    return name
            w = w.parent() if hasattr(w, "parent") else None
    except Exception:
        pass

    # 3. Note already has cards (browser edit / existing note)
    if editor.note:
        name = _deck_name_for_note(editor.note)
        if name:
            return name

    # 4. Collection "current" deck — what Add cards uses when the chooser
    #    is not reachable, and what the main window has selected.
    if mw.col:
        try:
            if hasattr(mw.col.decks, "get_current_id"):
                name = _deck_name_from_id(mw.col.decks.get_current_id())
                if name:
                    return name
            cur = mw.col.decks.current()
            if isinstance(cur, dict) and cur.get("name"):
                return cur["name"]
            if isinstance(cur, dict) and cur.get("id") is not None:
                name = _deck_name_from_id(cur["id"])
                if name:
                    return name
        except Exception:
            pass

    return None


def on_setup_buttons(buttons: list, editor: Editor) -> list:
    """Add two native buttons: Run Fill + Choose Source"""

    # ——— Button 1: Run QuickFill using selected source ———
    def run_fill(editor: Editor):
        if not editor.note:
            tooltip("No note open")
            return

        model_name = editor.note.note_type()["name"]
        deck_name = _deck_name_for_editor(editor)
        source_config = get_current_source(model_name, deck_name)

        if not source_config:
            tooltip("No sources configured for this note type / deck")
            return

        field_idx = source_config.get("source_field", 0)
        if field_idx >= len(editor.note.fields):
            tooltip("Source field index out of range")
            return

        word = editor.note.fields[field_idx].strip()
        if not word:
            tooltip("Source field is empty")
            return

        # fill_note runs QueryOp in the background; success / clearance
        # prompt are handled in FetcherRegistry.fill_note on_success.
        quickfill.fill_note(editor.note, word, source_config, editor)

    run_btn_html = editor.addButton(
        icon=ICON_PATH if os.path.exists(ICON_PATH) else None,
        cmd="qf_run",
        func=lambda e=editor: e.saveNow(lambda: run_fill(e)),
        tip="QuickFill: Fill fields from selected source",
        keys="Ctrl+Shift+Q",
        disables=False,
        rightside=True,
    )
    buttons.append(run_btn_html)  # ← MUST append the returned string

    # ——— 2. Source selector button (dropdown arrow) ———
    def show_source_menu(editor: Editor):
        if not editor.note:
            tooltip("No note open")
            return

        model_name = editor.note.note_type()["name"]
        deck_name = _deck_name_for_editor(editor)
        sources = CONFIG.get("models", {}).get(model_name, [])

        if not sources:
            tooltip("No sources configured for this note type")
            return

        # One entry per display name: most-specific matching deck variant.
        # (e.g. MW any-deck + MW Teaching::English → only MW Teaching::English;
        #  Cambridge any-deck still appears.)
        candidates = sources_for_deck(model_name, deck_name, sources=sources)
        if not candidates:
            tooltip("No sources configured for this note type / deck")
            return

        current = get_current_source(model_name, deck_name)

        menu = QMenu(editor.widget)
        # QAction tooltips are suppressed in menus unless this is on.
        menu.setToolTipsVisible(True)

        for source in candidates:
            name = source.get("name", "Unnamed " + source["fetcher"])
            scope = _normalize_deck(source.get("deck"))
            # Same pattern as dev/core: checkable QAction + setChecked.
            # Also match by display key so the tick survives config reload
            # (object identity alone breaks after CONFIG is replaced).
            is_current = source is current or (
                current is not None
                and _display_key(source) == _display_key(current)
            )

            action = QAction(name, menu)
            action.setCheckable(True)
            action.setChecked(is_current)
            if scope != _ANY_DECK:
                action.setToolTip(f"Deck: {scope}")
            else:
                action.setToolTip("Deck: (any deck)")

            def on_select(*, src=source):
                _selected_source[model_name] = src
                _selected_source_deck[model_name] = deck_name
                tooltip(f'QuickFill source → {src.get("name", src["fetcher"])}')

            action.triggered.connect(on_select)
            menu.addAction(action)

        menu.exec(QCursor.pos())

    # Handle Linux Flatpak bug that swaps light and dark arrows
    if theme_manager.night_mode and 'FLATPAK_ID' in os.environ:
        theme_manager.set_night_mode(False)
        pulldown_icon = theme_manager.themed_icon('mdi:chevron-down')
        theme_manager.set_night_mode(True)
    else:
        pulldown_icon = theme_manager.themed_icon('mdi:chevron-down')

    src_btn_html = editor.addButton(
        icon=pulldown_icon,
        cmd='.',
        func=lambda e=editor: show_source_menu(e),
        tip='QuickFill: Choose source',
        disables=False,
        rightside=True,
    )
    buttons.append(src_btn_html)  # ← MUST append

    return buttons


def _selected_note_ids(browser):
    """Prefer modern API; fall back to legacy selectedNotes()."""
    if hasattr(browser, "selected_notes"):
        return list(browser.selected_notes())
    if hasattr(browser, "selectedNotes"):
        return list(browser.selectedNotes())
    return []


def bulk_quickfill(browser):
    """Browser: fill all currently highlighted notes (Edit → QuickFill in bulk…)."""
    nids = _selected_note_ids(browser)
    if not nids:
        tooltip("QuickFill: No notes selected")
        return

    def source_for_note_context(model_name, deck_name=None):
        return get_current_source(model_name, deck_name)

    quickfill.fill_notes_bulk(
        nids,
        source_for_model=source_for_note_context,
        browser=browser,
    )


def on_browser_menus(browser):
    """Add bulk action under the browser Edit menu (same place as AutoDefine)."""
    menu = browser.form.menuEdit
    menu.addSeparator()
    action = menu.addAction("QuickFill in bulk…")
    action.setShortcut(QKeySequence("Ctrl+Shift+Q"))
    action.triggered.connect(lambda _checked=False, b=browser: bulk_quickfill(b))


gui_hooks.editor_did_init_buttons.append(on_setup_buttons)
gui_hooks.browser_menus_did_init.append(on_browser_menus)


def on_main_menu() -> None:
    """Tools → QuickFill configuration… (GUI). Add-ons list Config stays JSON."""
    def _open():
        from .config_gui import open_config

        open_config()

    action = QAction("QuickFill configuration…", mw)
    action.triggered.connect(_open)
    mw.form.menuTools.addSeparator()
    mw.form.menuTools.addAction(action)


# Menu is built once at startup after the main window exists
gui_hooks.main_window_did_init.append(on_main_menu)
