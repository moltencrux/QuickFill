from aqt.utils import showInfo
from aqt import mw
from . import fetchers # import CSVFetcher # , YahooFetcher  # Import directly from fetchers

class FetcherRegistry:
    def __init__(self):
        self.fetchers = {}
        self.load_fetchers()

    def load_fetchers(self):
        # Instantiate all fetchers from fetchers/__init__.py
        print(f"Debug: Registered fetchers: {list(self.fetchers.keys())}")
        for cls in fetchers.all_fetchers:
            self.fetchers[cls.source_name()] = cls(message_callback=showInfo)
        print(f"Debug: Registered fetchers: {list(self.fetchers.keys())}")

    def fetch(self, word, model_config, deck_name):
        source = model_config.get('source')
        fetcher = self.fetchers.get(source)
        if not fetcher:
            showInfo(f"No fetcher found for source '{source}'")
            return []
        data_list = fetcher.fetch(word, model_config)
        print(f"Debug: data_list after fetch: {data_list}")
        return data_list

    def fill_note(self, note, word, model_config, deck_name, deck_id, editor):
        print(f"Debug: Note fields count: {len(note.fields)}")
        print(f"Debug: Note fields: {note.fields}")
        print(f"Debug: Note ID: {note.id}")
        data = self.fetch(word, model_config, deck_name)
        if not data:
            return False
        else:
            for field_idx, value in data.items():
                if field_idx >= 0 and field_idx < len(note.fields):
                    note.fields[field_idx] = value
                    print(f"Debug: Assigning field {field_idx}='{value}'")
                else:
                    print(f"Debug: Field index {field_idx} out of range for note with {len(note.fields)} fields")
        editor.loadNoteKeepingFocus()
        print("Debug: Editor refreshed with loadNoteKeepingFocus")
        return True
