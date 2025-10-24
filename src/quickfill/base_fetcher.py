from abc import ABC, abstractmethod

class Fetcher(ABC):
    """Abstract base class for QuickFill fetchers."""
    def __init__(self, message_callback=None):
        self.message_callback = message_callback or (lambda msg: None)
    
    @staticmethod
    @abstractmethod
    def source_name(self):
        """
        Return the source name for this fetcher.
        
        Returns:
            str: The source identifier (e.g., 'yahoo', 'local_csv').
        """
        raise NotImplementedError(f"{self.__class__.__name__}.source_name() must be overridden")
    
    @abstractmethod
    def fetch(self, word, config):
        """
        Fetch data for a word.
        
        Args:
            word (str): The word to fetch data for.
            config (dict): Model-deck-specific configuration.
        
        Returns:
            list: List of dictionaries with field indices as keys (e.g., {0: 'value', 8: 'value'}).
        """
        raise NotImplementedError(f"{self.__class__.__name__}.fetch() must be overridden")