"""Cambridge English → Japanese fetcher."""

from .cambridge_base import CambridgeFetcher


class CambridgeEJFetcher(CambridgeFetcher):
    """Fetcher for Cambridge English-Japanese Dictionary."""

    base_url = "https://dictionary.cambridge.org/dictionary/english-japanese/"
    translation_key = "def_ja"

    @staticmethod
    def source_name():
        return "cambridge_en_ja"

    def _translation_selector(self):
        # EJ pages typically omit the break-cj class
        return (
            "span.trans.dtrans.dtrans-se, "
            "span.trans.dtrans"
        )
