"""Cambridge English → Traditional Chinese fetcher."""

from .cambridge_base import CambridgeFetcher


class CambridgeECFetcher(CambridgeFetcher):
    """Fetcher for Cambridge English-Chinese (Traditional) Dictionary."""

    base_url = (
        "https://dictionary.cambridge.org/dictionary/english-chinese-traditional/"
    )
    translation_key = "def_zh"

    @staticmethod
    def source_name():
        return "cambridge_en_tc"

    def _translation_selector(self):
        # EC pages prefer the break-cj class on primary translations
        return (
            "span.trans.dtrans.dtrans-se.break-cj, "
            "span.trans.dtrans.dtrans-se, "
            "span.trans.dtrans"
        )
