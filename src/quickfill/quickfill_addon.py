from aqt import gui_hooks, mw
from aqt.qt import QMenu, QAction, QIcon, QCursor
from aqt.utils import tooltip, showWarning
from aqt.editor import Editor
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
            tooltip("No source selected — click the Source button")
            return

        word = editor.note.fields[source_config.get('source_field', 0)]
        try:
            # Use your existing fill_note() — no deck needed anymore
            quickfill.fill_note(editor.note, word, source_config, editor)
            editor.loadNoteKeepingFocus()
            tooltip(f"Filled using {source_config.get('name', source_config['fetcher'])}")
        except Exception as e:
            showWarning(f"QuickFill failed:\n{e}")

    button = editor.addButton(
        icon=ICON_PATH if os.path.exists(ICON_PATH) else None,
        cmd="qf_run",
        func=lambda e=editor: run_fill(e),
        tip="QuickFill: Fill fields from selected source",
        keys="Ctrl+Shift+Q",
        rightside=True,
    )

    buttons.append(button)

    # ——— Button 2: Source Selector (opens menu at mouse) ———
    def show_source_menu(editor: Editor):
        if not editor.note:
            tooltip("No note open")
            return

        model_name = editor.note.model()["name"]
        # sources = CONFIG.get("models", {}).get(model_name, [])
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
                tooltip(f"QuickFill source → {src.get('name', src['fetcher'])}")

            action.triggered.connect(on_select)
            menu.addAction(action)

        # Show at mouse cursor
        menu.exec(QCursor.pos())

    src_button = editor.addButton(
        icon=None,
        cmd="⌄",
        func=lambda e=editor: show_source_menu(e),
        tip="QuickFill: Choose source",
        rightside=True,
    )
    buttons.append(src_button)

    return buttons


# Hook into editor
gui_hooks.editor_did_init_buttons.append(on_setup_buttons)
