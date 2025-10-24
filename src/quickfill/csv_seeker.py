import csv
import os
from pathlib import Path
import mmap
from io import StringIO


class CSVSeeker:
    """Seeker for efficient word lookup in a sorted CSV file."""
    
    def __init__(self, csv_path, sorted=True, delimiter='\t', search_field='term'):
        self.csv_path = Path(csv_path)
        self.sorted = sorted
        self.delimiter = delimiter
        self.search_field = search_field
        self.header = None
        if not os.path.exists(self.csv_path):
            raise FileNotFoundError(f"CSV file not found at '{self.csv_path}'")
        self.header = self.get_csv_header()

    def get_csv_header(self, encoding='utf-8'):
        """Read the CSV header."""
        with open(self.csv_path, 'rt', encoding=encoding) as f:
            reader = csv.reader(f, delimiter=self.delimiter)
            header = next(reader, None)
            print(f"Debug: Header: {header}")
            return header if header else []
    
    # def dict_from_record(self, line, header):
        """Parse a CSV line into a dictionary using the header."""
        if not line:
            return {}
        try:
            row = next(csv.reader([line], delimiter=self.delimiter))
            return {header[i]: row[i] for i in range(min(len(header), len(row)))}
        except Exception as e:
            print(f"Debug: Failed to parse CSV line '{line}': {str(e)}")
            return {}

    # def dict_from_record(record_str, fieldnames, delimiter='\t'):
    def dict_from_record(self, line):
        """Convert a record string to a dictionary using fieldnames."""
        try:
            stream = StringIO(line)
            return next(csv.DictReader(stream, self.header, delimiter=self.delimiter))
        except (csv.Error, IndexError) as e:
            print(f"Debug: Error parsing record '{line}': {str(e)}")
            return {}

    def search(self, word):
        """Search for a word in the CSV file.
        
        Args:
            word (str): The word to search for.
        
        Returns:
            list: List of rows matching the word in the source field.
        """
        results = []
        print(f"Debug: Searching for '{word}' in CSV: {self.csv_path}, sorted={self.sorted}")
        
        if self.search_field not in self.header:
            print(f"Error: Source field '{self.search_field}' not in header {self.header}")
            return []
        
        source_idx = self.header.index(self.search_field)
        word_lower = word.lower()
        
        with open(self.csv_path, 'rt', encoding='utf-8') as f:
            # Memory-map the file for efficient seeking
            with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                size = os.path.getsize(self.csv_path)
                print(f"Debug: File size={size}")
                
                # Skip header
                mm.seek(0)
                header_line = mm.readline()
                low = mm.tell()
                high = size - 1
                print(f"Debug: Seek offset={low}, first_word='{self._read_word(mm, low)}'")
                
                if not self.sorted:
                    # Linear search for unsorted CSV
                    f.seek(0)
                    reader = csv.reader(f, delimiter=self.delimiter)
                    next(reader, None)  # Skip header
                    for row in reader:
                        if row and len(row) > source_idx and row[source_idx].strip().lower() == word_lower:
                            results.append(row)
                    print(f"Debug: Found {len(results)} matching rows for '{word}' in unsorted CSV")
                    return results
                
                # Binary search for sorted CSV
                max_iterations = 1000  # Prevent infinite loops
                iteration = 0
                prev_mid = -1
                
                while low <= high and iteration < max_iterations:
                    iteration += 1
                    approx_mid = (low + high) // 2
                    mid = approx_mid
                    
                    if mid == prev_mid:
                        print("Debug: Loop detected, breaking binary search")
                        break
                    prev_mid = mid
                    
                    while mid > low:
                        try:
                            mm.seek(mid)
                            mm.readline()  # Skip to next full line
                            break
                        except UnicodeDecodeError:
                            mid += 1
                            continue
                    
                    cur_pos = mm.tell()
                    if cur_pos >= size:
                        print(f"Debug: Reached end of file at position={cur_pos}")
                        break
                    
                    line = mm.readline().decode('utf-8', errors='replace')
                    first_word = self.dict_from_record(line).get(self.search_field, '').lower()
                    mid = mm.tell()
                    
                    line = mm.readline().decode('utf-8', errors='replace')
                    cur_word = self.dict_from_record(line).get(self.search_field, '').lower()
                    print(f"Debug: Binary search iteration={iteration}, mid={mid}, low={low}, high={high}, first_word='{first_word}', cur_word='{cur_word}'")
                    
                    while cur_word and cur_word == first_word:
                        mid = mm.tell()
                        line = mm.readline().decode('utf-8', errors='replace')
                        cur_word = self.dict_from_record(line).get(self.search_field, '').lower()
                    
                    if cur_word and cur_word < word_lower:
                        low = mid
                    elif not cur_word or cur_word > word_lower:
                        high = approx_mid
                    else:
                        # Found a match, collect all matching rows
                        temp_pos = cur_pos
                        while temp_pos > low:
                            mm.seek(temp_pos)
                            mm.readline()  # Ensure start of line
                            temp_line = mm.readline().decode('utf-8', errors='replace')
                            if not temp_line:
                                break
                            temp_row = next(csv.reader([temp_line], delimiter=self.delimiter))
                            if temp_row and len(temp_row) > source_idx and temp_row[source_idx].strip().lower() == word_lower:
                                results.append(temp_row)
                            else:
                                break
                            temp_pos -= len(temp_line.encode('utf-8')) + 1
                        
                        mm.seek(cur_pos)
                        while mm.tell() < size:
                            next_line = mm.readline().decode('utf-8', errors='replace')
                            if not next_line:
                                break
                            next_row = next(csv.reader([next_line], delimiter=self.delimiter))
                            if next_row and len(next_row) > source_idx and next_row[source_idx].strip().lower() == word_lower:
                                results.append(next_row)
                            else:
                                break
                        break
                
                if iteration >= max_iterations:
                    print("Debug: Max iterations reached, possible unsorted CSV or search error")
                
                print(f"Debug: Found {len(results)} matching rows for '{word}' in CSV")
                return results
    
    def _read_word(self, mm, pos):
        """Read the source field at a given position in a memory-mapped file."""
        mm.seek(pos)
        line = mm.readline().decode('utf-8', errors='replace')
        if line:
            return self.dict_from_record(line).get(self.search_field, '')
        return ''

if __name__ == "__main__":
    file_path = os.path.expanduser('~/.var/app/net.ankiweb.Anki/data/Anki2/addons21/quickfill/data/dictionary.csv')
    seeker = CSVSeeker(file_path, sorted=True, delimiter=',', search_field='word')
    word = 'memorize'
    results = seeker.search(word)
    print(f"Result: {results}")
