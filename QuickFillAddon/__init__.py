import sys
import os
from aqt import mw, gui_hooks
from aqt.addcards import AddCards
from aqt.editor import Editor
from .fetcher import fetch_and_fill

# Add addon directory to sys.path
addon_dir = os.path.dirname(__file__)
if addon_dir not in sys.path:
    sys.path.append(addon_dir)

# Add button to editor
def setup_editor_buttons(buttons, editor):
    config = mw.addonManager.getConfig(__name__)
    addon_folder = mw.addonManager.addonFromModule(__name__)
    addon_path = os.path.join(mw.addonManager.addonsFolder(), addon_folder)
    icon_path = os.path.join(addon_path, "images", "quickfill.svg")
    
    button = editor.addButton(
        icon=icon_path if os.path.exists(icon_path) else None,
        cmd="yahoo_fetch",
        func=lambda ed: fetch_and_fill(ed),
        tip="Fetch from Yahoo Dictionary or CSV (Ctrl+Alt+E)",
        keys="Ctrl+Alt+E"
    )
    buttons.append(button)
    return buttons

# Hooks
gui_hooks.editor_did_init_buttons.append(setup_editor_buttons)