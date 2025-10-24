import os
from aqt import mw, gui_hooks
from aqt.utils import showInfo
from .fetcher import FetcherRegistry

# Global FetcherRegistry instance
quickfill = FetcherRegistry()

def load_config():
    try:
        # Use Anki's addonManager to get effective config (merges config.json and meta.json)
        config = mw.addonManager.getConfig(__name__)
        if config is None:
            showInfo("Error: No configuration found for QuickFill add-on")
            print("Debug: Config load error: No configuration found")
            return {}
        return config
    except Exception as e:
        showInfo(f"Error loading config: {str(e)}")
        print(f"Debug: Config load error: {str(e)}")
        return {}

def fetch_and_fill(editor):
    """Fill note from editor context (used by button and Ctrl+Alt+E)."""
    note = editor.note
    if note is None:
        showInfo("Error: editor.note not found")
        print("Debug: editor.note not found")
        return
    print(f"Debug: fetch_and_fill called, editor type: {type(editor).__name__}, addMode: {getattr(editor, 'addMode', 'Unknown')}")
    config = load_config()
    model_name = note.note_type()['name']
    deck_id = None
    deck_name = None

    # Log editor attributes
    print(f"Debug: editor attributes: {dir(editor)}")
    if hasattr(editor, 'parentWindow'):
        print(f"Debug: editor.parentWindow type: {type(editor.parentWindow).__name__}, attributes: {dir(editor.parentWindow)}")
    else:
        print("Debug: editor has no parentWindow")

    # Try getting deck ID based on addMode
    if hasattr(editor, 'addMode') and editor.addMode:
        if hasattr(editor, 'parentWindow') and hasattr(editor.parentWindow, 'deckChooser') and hasattr(editor.parentWindow.deckChooser, 'selectedId'):
            try:
                deck_id = editor.parentWindow.deckChooser.selectedId()
                deck_name = editor.mw.col.decks.get(deck_id)["name"]
                print(f"Debug: editor.parentWindow.deckChooser.selectedId(): {deck_id}, Deck name: {deck_name}")
            except Exception as e:
                print(f"Debug: Failed to get deck from editor.parentWindow.deckChooser: {str(e)}")
        else:
            print("Debug: editor.parentWindow.deckChooser unavailable")
    else:
        print("Debug: Not in addMode or addMode not available")

    # Fallback to mw.col.decks.current()
    if not deck_id and hasattr(mw, 'col') and mw.col:
        try:
            deck_id = mw.col.decks.current()['id']
            deck_name = mw.col.decks.get(deck_id)["name"]
            print(f"Debug: Fallback to mw.col.decks.current(): {deck_id}, Deck name: {deck_name}")
        except Exception as e:
            print(f"Debug: Failed to get current deck: {str(e)}")

    # Final fallback to Default EC
    if not deck_id or not deck_name:
        deck_name = 'Default EC'
        deck_id = mw.col.decks.id('Default EC', create=True) if hasattr(mw, 'col') and mw.col else 1761544421211
        print(f"Debug: Fallback to Default EC deck, ID: {deck_id}")

    # Log all available decks
    print(f"Debug: All decks: {mw.col.decks.all_names_and_ids() if hasattr(mw, 'col') and mw.col else 'No collection'}")

    # Case-sensitive deck name matching
    model_config = None
    available_decks = config.get('models', {}).get(model_name, {}).get('decks', {})
    print(f"Debug: Available decks for model '{model_name}': {list(available_decks.keys())}")
    for config_deck_name in available_decks:
        if config_deck_name == deck_name:  # Case-sensitive
            model_config = available_decks[config_deck_name]
            print(f"Debug: Matched deck '{deck_name}' (case-sensitive)")
            break
    if not model_config:
        showInfo(f"No configuration found for model '{model_name}' and deck '{deck_name}'")
        print(f"Debug: No config for model='{model_name}', deck='{deck_name}'")
        return
    word = note.fields[model_config.get('source_field', 0)]
    print(f"Debug: Filling note for word='{word}', model='{model_name}', deck='{deck_name}'")
    quickfill.fill_note(note, word, model_config, deck_name, deck_id, editor)

def setup_editor_buttons(buttons, editor):
    # Add QuickFill button with Ctrl+Alt+E hotkey
    addon_folder = mw.addonManager.addonFromModule(__name__)
    addon_path = os.path.join(mw.addonManager.addonsFolder(), addon_folder)
    icon_path = os.path.join(addon_path, "images", "quickfill.svg")
    
    button = editor.addButton(
        icon=icon_path if os.path.exists(icon_path) else None,
        cmd="QuickFill",
        func=fetch_and_fill,
        tip="Fetch fields from configurable sources (Ctrl+Alt+E)",
        keys="Ctrl+Alt+E"
    )
    buttons.append(button)
    print("Debug: QuickFill button added to editor")
    return buttons

# Register hooks
gui_hooks.editor_did_init_buttons.append(setup_editor_buttons)
print("Debug: QuickFill hooks initialized")
