from abc import ABC, abstractmethod

class Fetcher(ABC):
    """Abstract base class for QuickFill fetchers."""
    def __init__(self, message_callback=None):
        self.message_callback = message_callback or (lambda msg: None)

    @staticmethod
    @abstractmethod
    def source_name():
        """
        Return the source name for this fetcher.

        Returns:
            str: The source identifier (e.g., 'yahoo', 'local_csv').
        """
        raise NotImplementedError(f"{self.__class__.__name__}.source_name() must be overridden")

    @classmethod
    @abstractmethod
    def get_fields(cls, config=None):
        """
        Return the mapping keys this fetcher can produce.

        These are the strings used as keys in a source's ``mapping`` dict
        (output key → note field index). The config GUI uses this list to
        populate the field-mapping dropdown.

        Args:
            config: Optional source config dict (same shape passed to
                ``fetch``). Most fetchers ignore it and return a fixed
                schema. ``local_csv`` uses ``config["config"]["csv_path"]``
                (and delimiter) to read the file header when available.

        Returns:
            list[str]: Stable ordered list of supported field names.
        """
        raise NotImplementedError(
            f"{cls.__name__}.get_fields() must be overridden"
        )

    @abstractmethod
    def fetch(self, word, config):
        """
        Fetch data for a word.

        Args:
            word (str): The word to fetch data for.
            config (dict): Model-deck-specific configuration.

        Returns:
            dict: Mapping of note-field indices to values, or a status dict.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__}.fetch() must be overridden"
        )
