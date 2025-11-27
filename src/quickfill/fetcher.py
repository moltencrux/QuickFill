from aqt.utils import showInfo, tooltip
from aqt import mw
from aqt.operations import QueryOp
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

    def fetch(self, word, config):
        source = config.get('fetcher')
        fetcher = self.fetchers.get(source)
        if not fetcher:
            showInfo(f"No fetcher found for source '{source}'")
            return []
        data_list = fetcher.fetch(word, config)
        print(f"Debug: data_list after fetch: {data_list}")
        return data_list

    def fill_note(self, note, word, config, editor):

        def background_op(col):
            return self.fetch(word, config)        # runs in background thread

        def on_success(data):
            if not data:
                tooltip("QuickFill: Nothing found")
                return
            for idx, val in data.items():
                if 0 <= idx < len(note.fields):
                    note.fields[idx] = val.strip()
            editor.loadNoteKeepingFocus()
            tooltip("QuickFill → fields filled")

        tooltip(f"QuickFill: Fetching from {config.get('name', 'Unnamed source')}…")
        QueryOp(
            parent=mw,
            op=background_op,
            success=on_success,
        ).with_progress(
            label=f"QuickFill: Fetching…"
        ).run_in_background()
