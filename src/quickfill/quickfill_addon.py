from aqt import gui_hooks, mw
from aqt.qt import QMenu, QAction, QIcon, QCursor
from aqt.utils import tooltip, showWarning
from aqt.editor import Editor
from aqt.theme import theme_manager
import os
from .fetcher import FetcherRegistry


# Load config and icon
CONFIG = mw.addonManager.getConfig(__name__)
ICON_PATH = os.path.join(os.path.dirname(__file__), "images", "quickfill.svg")

# Track selected source per note type
_selected_source: dict[str, dict] = {}

quickfill = FetcherRegistry()

def on_setup_buttons(buttons: list, editor: Editor) -> list:
    """Add two native buttons: Run Fill + Choose Source"""

    # ——— Button 1: Run QuickFill using selected source ———
    def run_fill(editor: Editor):
        if not editor.note:
            tooltip("No note open")
            return

        model_name = editor.note.model()["name"]
        source_config = _selected_source.get(model_name)

        if not source_config:
            tooltip("No source selected — click the dropdown button")
            return

        field_idx = source_config.get("source_field", 0)
        if field_idx >= len(editor.note.fields):
            tooltip("Source field index out of range")
            return

        word = editor.note.fields[field_idx].strip()
        if not word:
            tooltip("Source field is empty")
            return

        try:
            # Use your existing fill_note() — no deck needed anymore
            quickfill.fill_note(editor.note, word, source_config, editor)
            editor.loadNoteKeepingFocus()
            tooltip(f"Filled using {source_config.get('name', source_config['fetcher'])}")
        except Exception as e:
            showWarning(f"QuickFill failed:\n{e}")

    run_btn_html = editor.addButton(
        icon=ICON_PATH if os.path.exists(ICON_PATH) else None,
        cmd="qf_run",
        func=lambda e=editor: run_fill(e),
        tip="QuickFill: Fill fields from selected source",
        keys="Ctrl+Shift+Q",
        disables=False,
        rightside=True,
    )
    buttons.append(run_btn_html)   # ← MUST append the returned string


    # ——— 2. Source selector button (dropdown arrow) ———
    def show_source_menu(editor: Editor):
        if not editor.note:
            tooltip("No note open")
            return

        model_name = editor.note.model()["name"]
        sources = CONFIG.get("models", {}).get(model_name, [])

        if not sources:
            tooltip("No sources configured for this note type")
            return

        # Default to first
        if model_name not in _selected_source:
            _selected_source[model_name] = sources[0]

        current = _selected_source[model_name]
        menu = QMenu(editor.widget)

        for source in sources:
            name = source.get("name", "Unnamed " + source["fetcher"])
            action = QAction(name, menu)
            action.setCheckable(True)
            action.setChecked(source is current)


            # changed src to be keyword only, so it doesn't get overwritten
            def on_select(*, src=source):
                _selected_source[model_name] = src
                tooltip(f'QuickFill source → {src.get("name", src["fetcher"])}')

            action.triggered.connect(on_select)
            menu.addAction(action)

        # Show at mouse cursor
        menu.exec(QCursor.pos())

    # Handle Linux Flatpak bug that swaps light and dark arrows
    if theme_manager.night_mode and 'FLATPAK_ID' in os.environ:
        theme_manager.set_night_mode(False)
        pulldown_icon=theme_manager.themed_icon('mdi:chevron-down')
        theme_manager.set_night_mode(True)
    else:
        pulldown_icon=theme_manager.themed_icon('mdi:chevron-down')

    src_btn_html = editor.addButton(
        icon=pulldown_icon,
        cmd='.',
        func=lambda e=editor: show_source_menu(e),
        tip='QuickFill: Choose source',
        disables=False,
        rightside=True,
    )
    buttons.append(src_btn_html)   # ← MUST append

    return buttons


gui_hooks.editor_did_init_buttons.append(on_setup_buttons)
