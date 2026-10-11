from aqt.utils import tooltip
from aqt import mw
from aqt.operations import QueryOp
from . import fetchers
from .stem_mask import apply_mask_to_fields


class FetcherRegistry:
    def __init__(self):
        self.fetchers = {}
        self.load_fetchers()

    def load_fetchers(self):
        # Instantiate all fetchers. Do NOT pass showInfo here — fetch() runs
        # inside QueryOp's background thread, and Qt UI must stay on the main
        # thread (showInfo from a worker → "Cannot set parent, different thread").
        print(f"Debug: Registered fetchers: {list(self.fetchers.keys())}")
        for cls in fetchers.all_fetchers:
            self.fetchers[cls.source_name()] = cls(message_callback=None)
        print(f"Debug: Registered fetchers: {list(self.fetchers.keys())}")

    def fetch(self, word, config, message_sink=None):
        """
        Run the configured fetcher.

        message_sink: optional callable(str) invoked for status/error messages.
        When called from a background thread, pass a list.append (or similar)
        and surface those messages on the main thread in on_success.
        """
        source = config.get("fetcher")
        fetcher = self.fetchers.get(source)
        if not fetcher:
            msg = f"No fetcher found for source '{source}'"
            if message_sink:
                message_sink(msg)
            return {}

        # Temporarily route message_callback through the sink so any
        # self.message_callback(...) inside the fetcher is thread-safe.
        previous = fetcher.message_callback
        if message_sink is not None:
            fetcher.message_callback = message_sink
        try:
            data = fetcher.fetch(word, config) or {}
        finally:
            fetcher.message_callback = previous

        print(f"Debug: data after fetch: {data}")
        return data

    def fill_note(self, note, word, config, editor):
        def background_op(col):
            messages = []
            data = self.fetch(word, config, message_sink=messages.append)
            return {"data": data, "messages": messages}

        def on_success(result):
            # Main thread — safe to touch Qt / editor here.
            messages = (result or {}).get("messages") or []
            data = (result or {}).get("data") or {}

            for msg in messages:
                # tooltip is lighter than a modal dialog for fetch notes
                tooltip(f"QuickFill: {msg}")

            if not data:
                if not messages:
                    tooltip("QuickFill: Nothing found")
                return

            # Optional stem-mask post-processing (mask_fields, mask_mode, …)
            data = apply_mask_to_fields(data, word, config)

            for idx, val in data.items():
                if 0 <= idx < len(note.fields):
                    note.fields[idx] = val.strip() if isinstance(val, str) else val
            editor.loadNoteKeepingFocus()
            tooltip("QuickFill → fields filled")

        tooltip(f"QuickFill: Fetching from {config.get('name', 'Unnamed source')}…")
        QueryOp(
            parent=mw,
            op=background_op,
            success=on_success,
        ).with_progress(
            label="QuickFill: Fetching…"
        ).run_in_background()
