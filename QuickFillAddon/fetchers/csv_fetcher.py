import csv
import sys
import os
from io import StringIO
from .. import Fetcher
from .. import CSVSeeker


# Add parent directory to sys.path for standalone and Anki
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
print(f"Debug: sys.path: {sys.path}")


class CSVFetcher(Fetcher):
    """Fetcher for local CSV files."""

    def __init__(self, message_callback=None):
        super().__init__(message_callback)

    
    @staticmethod
    def source_name():
        return "local_csv"

    def fetch_old(self, word, config):
        try:
            csv_path = config.get('csv_path')
            csv_sorted = config.get('csv_sorted', True)
            delimiter = config.get('delimiter', '\t')
            seeker = CSVSeeker(csv_path, sorted=csv_sorted, delimiter=delimiter)
            rows = seeker.search(word, source_field_name='term')
            if not rows:
                self.message_callback(f"No results found for '{word}' in CSV")
                return []
            field_mappings = config.get('csv_field_mappings', {})
            results = []
            for row in rows:
                print(f"Debug: Raw CSV row: {row}")
                print(f"Debug: Row length: {len(row)}")
                data = {}
                for key, idx in field_mappings.items():
                    if idx >= 0:
                        try:
                            data[idx] = row[idx] if idx < len(row) else ''
                            print(f"Debug: Mapping {key} to index {idx}: {data[idx]}")
                        except IndexError:
                            print(f"Debug: Field index {idx} out of range for row: {row}")
                            data[idx] = ''
                # Map 'other' field (-1) to remaining unmapped columns
                if -1 in field_mappings.values():
                    mapped_indices = [idx for idx in field_mappings.values() if idx >= 0]
                    remaining = [row[i] for i in range(len(row)) if i not in mapped_indices and i < len(row)]
                    data[-1] = '; '.join(remaining) if remaining else ''
                    print(f"Debug: Mapping 'other' to index -1: {data[-1]}")
                results.append(data)
            print(f"Debug: CSVFetcher fetched data for '{word}': {results}")
            return results
        except Exception as e:
            self.message_callback(f"Error fetching CSV data: {str(e)}")
            return []

    def fetch(self, word, config):
        csv_path = config.get("csv_path")
        csv_sorted = config.get("csv_sorted", False)
        delimiter = config.get("delimiter", "\t")
        csv_search_field = config.get("csv_search_field", "term")  # Default to 'term' if not specified
        field_mappings = config.get("csv_field_mappings", {})
        if not csv_path or not os.path.exists(csv_path):
            if self.message_callback:
                self.message_callback(f"CSV file not found: {csv_path}")
            print(f"Debug: CSV file not found: {csv_path}")
            return []

        seeker = CSVSeeker(csv_path, sorted=csv_sorted, delimiter=delimiter, search_field=csv_search_field)
        rows = seeker.search(word)
        print(f"Debug: Found {len(rows)} matching rows for '{word}' in CSV")
        if not rows:
            if self.message_callback:
                self.message_callback(f"No data found for '{word}' in CSV")
            return []

        data_list = []
        for row in rows:
            print(f"Debug: Raw CSV row: {row}")
            data = {}
            for field_name, note_field_idx in field_mappings.items():
                csv_col_idx = next((i for i, col in enumerate(seeker.header) if col == field_name), None)
                if csv_col_idx is not None and csv_col_idx < len(row):
                    value = row[csv_col_idx]
                    if note_field_idx >= 0:
                        data[note_field_idx] = value
                        print(f"Debug: Mapping {field_name} (CSV col {csv_col_idx}) to note field {note_field_idx}: {value}")
                else:
                    print(f"Debug: Field '{field_name}' not found in CSV header or invalid index")
            data_list.append(data)
        print(f"Debug: CSVFetcher fetched data for '{word}': {data_list}")
        return data_list


if __name__ == "__main__":
    # Mock test
    config = {
        'csv_path': os.path.expanduser('~/.var/app/net.ankiweb.Anki/data/Anki2/addons21/quickfill/data/dictionary.csv'),
        'csv_sorted': True,
        'source_field': 0,
        'csv_field_mappings': {
            'term': 0,
            'definitions': 6,
            'examples': 7,
            'notes': 8,
            'other': -1
        }
    }
    fetcher = CSVFetcher()
    result = fetcher.fetch('master', config)
    print(f"Result: {result}")
