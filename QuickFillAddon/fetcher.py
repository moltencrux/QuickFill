from aqt import mw
from aqt.utils import showInfo
from anki.notes import Note
from .yahoo_scraper import scrape_word
from .csv_loader import load_from_csv
import os

def fetch_and_fill(editor):
    """Fetch data from Yahoo Dictionary or CSV and fill note fields."""
    config = mw.addonManager.getConfig(__name__)
    if not config:
        showInfo("Configuration not found. Please check Tools > Add-ons > Yahoo Dictionary Autofill > Config.")
        return
    
    # Get current note type and its specific config
    note_type_name = editor.note.note_type()['name']
    model_config = config.get("models", {}).get(note_type_name)
    if not model_config:
        showInfo(f"No configuration found for note type '{note_type_name}' in config.json. Please add it to 'models'.")
        return
    
    # Debug: Print model_config and note fields
    print(f"Debug: model_config for {note_type_name}: {model_config}")
    print(f"Debug: Note fields count: {len(editor.note.fields)}")
    
    # Get word from source field (model-specific)
    source_field_idx = model_config.get("source_field", 0)
    if source_field_idx >= len(editor.note.fields):
        showInfo(f"Source field index {source_field_idx} is out of range for note type '{note_type_name}'. Please ensure the note type has enough fields.")
        return
    
    word = editor.note.fields[source_field_idx].strip()
    if not word:
        showInfo("Please enter a word in the source field.")
        return
    
    # Fetch data based on source (model-specific)
    source = model_config.get("source", "yahoo")
    data_list = []
    if source == "yahoo":
        data_list = scrape_word(word, config)
    elif source == "local_csv":
        csv_path = model_config.get("csv_path")
        if not csv_path:
            showInfo(f"No csv_path configured for note type '{note_type_name}' in config.json.")
            return
        print(f"Debug: csv_path={csv_path}, exists={os.path.exists(csv_path)}")
        if not os.path.exists(csv_path):
            showInfo(f"CSV file not found at '{csv_path}' for note type '{note_type_name}'. Check file path and Flatpak permissions.")
            return
        csv_field_mappings = model_config.get("csv_field_mappings", {})
        if not csv_field_mappings:
            showInfo(f"No csv_field_mappings defined for note type '{note_type_name}'.")
            return
        csv_sorted = model_config.get("csv_sorted", False)
        source_field_name = next((col for col, idx in csv_field_mappings.items() if idx == source_field_idx), 'word')
        data_list = load_from_csv(csv_path, word, csv_field_mappings, source_field_name, csv_sorted)
    else:
        showInfo(f"Unknown source '{source}' for note type '{note_type_name}'.")
        return
    
    print(f"Debug: data_list after fetch: {data_list}")
    if not data_list:
        return  # Error already shown in scrape_word or load_from_csv
    
    # Field mappings (model-specific)
    field_map = model_config.get("field_mappings", {}) if source == "yahoo" else csv_field_mappings
    print(f"Debug: field_map: {field_map}")
    
    # Validate field indices
    for key, field_idx in field_map.items():
        if field_idx >= 0 and field_idx >= len(editor.note.fields):
            showInfo(f"Field index {field_idx} for '{key}' is out of range for note type '{note_type_name}'. Please ensure the note type has enough fields.")
            return
    
    # Process fetched data
    for data in data_list:
        note = editor.note
        if data != data_list[0] and config.get("include_related_words", False) and source == "yahoo":
            deck_id = mw.col.decks.id(config.get("deck_name", "Default"))
            model = mw.col.models.by_name(note.note_type()['name'])
            if not model:
                showInfo(f"Note type '{note.note_type()['name']}' not found for related words.")
                continue
            note = Note(mw.col, model)
            note.addTag("YahooDictionary")
            mw.col.addNote(note)
        
        for key, field_idx in field_map.items():
            if field_idx >= 0 and field_idx < len(note.fields):
                if field_idx in data:
                    print(f"Debug: Assigning field {field_idx}='{data[field_idx]}' for key '{key}'")
                    note.fields[field_idx] = data[field_idx]
        
        if data == data_list[0]:
            editor.loadNoteKeepingFocus()
            editor.web.eval(f"focusField({source_field_idx});")

if __name__ == "__main__":
    # Mock editor and config for standalone testing
    class MockEditor:
        def __init__(self):
            self.note = MockNote()
            self.web = MockWeb()
        
        def loadNoteKeepingFocus(self):
            print("Debug: loadNoteKeepingFocus called")
    
    class MockNote:
        def __init__(self):
            self.fields = ['memorize', '', '', '', '', '', '', '']
            self.note_type = lambda: {'name': 'ESL Vocabulary'}
        
        def addTag(self, tag):
            print(f"Debug: Added tag {tag}")
    
    class MockWeb:
        def eval(self, cmd):
            print(f"Debug: Web eval: {cmd}")
    
    class MockMW:
        def __init__(self):
            self.addonManager = MockAddonManager()
            self.col = MockCol()
    
    class MockAddonManager:
        def getConfig(self, module):
            return {
                "models": {
                    "ESL Vocabulary": {
                        "source": "local_csv",
                        "csv_path": os.path.expanduser('~/.var/app/net.ankiweb.Anki/data/Anki2/addons21/quickfill/data/dictionary.csv'),
                        "csv_sorted": True,
                        "source_field": 0,
                        "csv_field_mappings": {
                            "term": 0,
                            "notes": 2,
                            "definitions": 6,
                            "examples": 7,
                            "other": -1
                        }
                    }
                }
            }
    
    class MockCol:
        def __init__(self):
            self.decks = MockDecks()
            self.models = MockModels()
        
        def addNote(self, note):
            print("Debug: Added note")
    
    class MockDecks:
        def id(self, name):
            return 1
    
    class MockModels:
        def by_name(self, name):
            return {'name': name} if name == 'ESL Vocabulary' else None
    
    mw = MockMW()
    editor = MockEditor()
    fetch_and_fill(editor)
