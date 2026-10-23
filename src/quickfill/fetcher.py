from aqt.utils import tooltip, askUser, showWarning
from aqt import mw
from aqt.operations import QueryOp
from . import fetchers
from .stem_mask import apply_mask_to_fields
from .clearance_install import (
    CLEARANCE_PIP_PACKAGES,
    clearance_available,
    install_clearance,
    is_clearance_needed_error,
    set_declined,
)


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

        parent = getattr(editor, "parentWindow", None) or mw

        def background_op(col):
            messages = []
            try:
                data = self.fetch(word, config, message_sink=messages.append)
                return {
                    "data": data,
                    "messages": messages,
                    "clearance_needed": False,
                }
            except Exception as e:
                # Use marker/name check — Anki can load the package twice so
                # ``except ClearanceNeededError`` may miss the real exception.
                if is_clearance_needed_error(e):
                    return {
                        "data": {},
                        "messages": messages,
                        "clearance_needed": True,
                        "clearance_msg": str(e),
                    }
                raise

        def on_success(result):
            # Main thread — safe to touch Qt / editor here.
            messages = (result or {}).get("messages") or []
            data = (result or {}).get("data") or {}

            for msg in messages:
                # tooltip is lighter than a modal dialog for fetch notes
                tooltip(f"QuickFill: {msg}")

            if (result or {}).get("clearance_needed"):
                pkgs = ", ".join(CLEARANCE_PIP_PACKAGES)
                ok = askUser(
                    "This dictionary site is showing a bot check (Cloudflare).\n\n"
                    "Install optional browser-clearance support?\n"
                    f"({pkgs} + Chromium — roughly 100+ MB download)\n\n"
                    "If you choose No, use a VPN or a different network.",
                    parent=parent
                )
                if not ok:
                    set_declined(True)
                    tooltip("Clearance install declined. Use a VPN or try again later.")
                    return
                set_declined(False)

                def install_op(col):
                    logs = []
                    try:
                        install_clearance(message=logs.append)
                        return {"ok": True, "logs": logs, "error": None}
                    except Exception as e:
                        return {"ok": False, "logs": logs, "error": str(e)}

                def install_done(res):
                    for line in (res or {}).get("logs") or []:
                        print(f"QuickFill: {line}")
                    if not (res or {}).get("ok"):
                        showWarning(
                            f"Clearance install failed:\n{(res or {}).get('error')}"
                        )
                        return
                    if clearance_available():
                        tooltip("Clearance ready — run QuickFill again on this note.")
                    else:
                        showWarning(
                            "Install finished but Playwright/Chromium was not detected. "
                            "Restart Anki and try again."
                        )

                QueryOp(
                    parent=mw,
                    op=install_op,
                    success=install_done,
                ).with_progress(
                    label="QuickFill: Installing browser clearance…"
                ).run_in_background()
                return

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
            parent=parent,
            op=background_op,
            success=on_success,
        ).with_progress(
            label="QuickFill: Fetching…"
        ).run_in_background()
