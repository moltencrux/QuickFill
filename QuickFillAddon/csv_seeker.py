import csv
import os
from pathlib import Path

from io import StringIO

from typing import List, Dict, Any

def dict_from_record(record_str, fieldnames, delimiter='\t'):
    """Convert a record string to a dictionary using fieldnames."""
    try:
        stream = StringIO(record_str)
        return next(csv.DictReader(stream, fieldnames, delimiter=delimiter))
    except (csv.Error, IndexError) as e:
        print(f"Debug: Error parsing record '{record_str}': {str(e)}")
        return {}


class CSVSeeker:
    """
    Robust CSV lookup using your proven logic.
    Works with any delimiter, sorted/unsorted, and custom search column.
    """

    def __init__(self, csv_path, search_field, sorted=True, delimiter="\t"):
        self.csv_path = Path(csv_path).expanduser()
        self.sorted = sorted
        self.delimiter = delimiter
        self.search_field = search_field

        if not self.csv_path.is_file():
            raise FileNotFoundError(f"CSV file not found: {self.csv_path}")

        # Read header once
        self.header = self._get_csv_header()

    def _get_csv_header(self, encoding: str = "utf-8") -> List[str]:
        """Read the first line and split by delimiter."""
        try:
            with open(self.csv_path, "r", encoding=encoding) as f:
                line = f.readline().strip()
                header = line.split(self.delimiter)
            print(f"Debug: Header (delimiter='{self.delimiter}'): {header}")
            return header
        except UnicodeDecodeError:
            print("Debug: Trying utf-8-sig for BOM...")
            with open(self.csv_path, "r", encoding="utf-8-sig") as f:
                line = f.readline().strip()
                header = line.split(self.delimiter)
            print(f"Debug: Header (utf-8-sig): {header}")
            return header

    def search(self, word: str) -> List[Dict[str, str]]:
        #def get_matching_rows_mine(file_path, word, source_field_name, csv_sorted=False, encoding='utf-8'):
        size = os.path.getsize(self.csv_path)

        word_lower = word.lower()
        data = []
        
        # Get header
        if not self.header:
            print(f"Error: Search field '{search_field}' not in header.")
            return []

        source_idx = self.header.index(self.search_field)

        with open(self.csv_path, 'rt', encoding='utf-8') as f:
            # Skip header
            f.readline()

            low = f.tell()
            high = size - 1

            if self.sorted:
                while low < high: # while we are still searching

                    approx_mid = (low + high) // 2
                    mid = approx_mid

                    if mid > low:
                        while True:
                            try:
                                f.seek(mid)
                                f.readline() # skip forward to the next line
                            except UnicodeDecodeError:
                                mid += 1
                                continue
                            break

                        # Get the first /NEW/ word that occurs strictly after approx_mid
                        prev_word = None
                        cur_word = None
                        while not prev_word or cur_word == prev_word:
                            mid = f.tell()
                            line = f.readline()
                            prev_word = cur_word
                            cur_word = dict_from_record(line, self.header, self.delimiter).get(self.search_field, '').lower()
                    else: # mid == low, so this is the start of a new word
                        f.seek(mid)
                        line = f.readline()
                        cur_word = dict_from_record(line, self.header, self.delimiter).get(self.search_field, '').lower()

                    # Now we know that next_word starts AT mid
                    if cur_word and cur_word < word and low < mid:
                        low = mid
                    else:
                        high = approx_mid # in case we skipped over it

                # approximate location found
                # If the target records exist, they will be close after /low/
                f.seek(low)
                while cur_word <= word: # also handle hit end of file
                    line = f.readline()
                    cur_word = dict_from_record(line, self.header, self.delimiter).get(self.search_field, '').lower()
                    if cur_word == word:
                        data.append(next(csv.reader([line], delimiter=self.delimiter)))

        return data


if __name__ == "__main__":
    # file_path = os.path.expanduser('~/.var/app/net.ankiweb.Anki/data/Anki2/addons21/quickfill/data/dictionary.csv')
    file_path = os.path.expanduser('~/.var/app/net.ankiweb.Anki/data/Anki2/addons21/quickfill/data/ecdict_trad.csv')
    seeker = CSVSeeker(file_path, sorted=True, delimiter=',', search_field='word')
    word = 'instability'
    results = seeker.search(word)
    print(f"Result: {results}")
