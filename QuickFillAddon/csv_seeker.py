import os
import csv
from io import StringIO
from pathlib import Path

def dict_from_record(record_str, fieldnames, delimiter='\t'):
    """Convert a record string to a dictionary using fieldnames."""
    try:
        stream = StringIO(record_str)
        return next(csv.DictReader(stream, fieldnames, delimiter=delimiter))
    except (csv.Error, IndexError) as e:
        print(f"Debug: Error parsing record '{record_str}': {str(e)}")
        return {}

def get_csv_header(file_path, encoding='utf-8'):
    """Read the header from the CSV file."""
    try:
        with open(file_path, 'r', encoding=encoding) as f:
            header = f.readline().strip().split('\t')
        print("Debug: Header:", header)
        return header
    except UnicodeDecodeError as e:
        print(f"Debug: Encoding error with '{encoding}': {str(e)}. Trying 'utf-8-sig'.")
        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                header = f.readline().strip().split('\t')
            print("Debug: Header:", header)
            return header
        except UnicodeDecodeError as e:
            print(f"Debug: Encoding error with 'utf-8-sig': {str(e)}.")
            return []

def get_matching_rows_mine(file_path, word, source_field_name, csv_sorted=False, encoding='utf-8'):
    file_path = Path(file_path)
    size = os.path.getsize(file_path)

    word_lower = word.lower()
    data = []
    
    # Get header
    header = get_csv_header(file_path, encoding)
    if source_field_name not in header:
        print(f"Error: Source field '{source_field_name}' not in header.")
        return []
    
    source_idx = header.index(source_field_name)

    with open(file_path, 'rt', encoding='utf-8') as f:
        ...
        # Skip header
        f.readline()

        low = f.tell()
        # start_word = dict_from_record(line, header).get(source_field_name, '').lower()
        high = size - 1

        if csv_sorted:
            while low <= high:
                approx_mid = (low + high) // 2
                mid = approx_mid

                while mid > low:
                    try:
                        f.seek(mid)
                        f.readline() # skip forward to the next line
                    except UnicodeDecodeError:
                        mid += 1
                        continue
                    break

                line = f.readline()
                first_word = dict_from_record(line, header).get(source_field_name)
                # Now we know that first_word starts AT OR BEFORE mid
                mid = f.tell()
                line = f.readline()
                cur_word = dict_from_record(line, header).get(source_field_name, '').lower()
                #### check if start of record > high? or '' ?
                while cur_word == first_word:
                    mid = f.tell()
                    line = f.readline()
                    cur_word = dict_from_record(line, header).get(source_field_name, '').lower()
                # Now we know that next_word starts AT mid
                if cur_word and cur_word < word:
                    low = mid
                elif not cur_word or cur_word > word:
                    high = approx_mid # in case we skipped over it
                else:
                    ... # found!
                    return mid
                # mid >= high: can't be word we're searching for



def get_matching_rows(file_path, word, source_field_name, csv_sorted=False, encoding='utf-8', return_position=False):
    """Get matching rows or file position from the CSV using binary search (if sorted) or linear scan."""
    file_path = Path(file_path)
    word_lower = word.lower()
    data = []
    
    # Get header
    header = get_csv_header(file_path, encoding)
    if not header:
        print("Error: Failed to read header.")
        return 0 if return_position else []
    if source_field_name not in header:
        print(f"Error: Source field '{source_field_name}' not in header.")
        return 0 if return_position else []
    
    source_idx = header.index(source_field_name)
    
    try:
        with open(file_path, 'rt', encoding=encoding) as f:
            # Skip header
            f.readline()
            low = f.tell()
            size = os.path.getsize(file_path)
            high = size - 1
            
            if csv_sorted:
                # Estimate average line size
                f.seek(0)
                total_size = 0
                sample_lines = 100
                for _ in range(sample_lines):
                    line = f.readline()
                    if not line:
                        break
                    total_size += len(line.encode(encoding))
                avg_line_size = total_size / sample_lines if total_size > 0 else 1
                line_count = size // avg_line_size
                print(f"Debug: File size={size}, avg_line_size={avg_line_size}, estimated lines={line_count}")
                
                # Binary search with iteration limit
                max_iterations = int(line_count * 2)
                iteration = 0
                while low <= high:
                    if iteration >= max_iterations:
                        print(f"Debug: Binary search exceeded {max_iterations} iterations. Aborting.")
                        return 0 if return_position else []
                    iteration += 1
                    approx_mid = (low + high) // 2
                    mid = approx_mid
                    
                    # Align to valid UTF-8 boundary
                    while mid > low:
                        try:
                            f.seek(mid)
                            f.readline()  # Skip partial line
                            break
                        except UnicodeDecodeError:
                            mid += 1
                            continue
                    pos = f.tell()
                    line = f.readline().strip()
                    if not line:
                        print(f"Debug: Empty line at offset={pos}")
                        high = approx_mid - 1
                        continue
                    first_word = dict_from_record(line, header).get(source_field_name, '').lower()
                    print(f"Debug: Seek offset={pos}, first_word='{first_word}'")
                    
                    # Check next lines to find term boundary
                    mid = pos
                    cur_word = first_word
                    max_boundary_checks = 10
                    boundary_count = 0
                    while cur_word == first_word and boundary_count < max_boundary_checks:
                        mid = f.tell()
                        line = f.readline().strip()
                        if not line:
                            cur_word = ''
                            break
                        cur_word = dict_from_record(line, header).get(source_field_name, '').lower()
                        boundary_count += 1
                    if boundary_count >= max_boundary_checks:
                        print(f"Debug: Boundary check reached limit of {max_boundary_checks} at offset={mid}")
                    
                    print(f"Debug: Binary search iteration={iteration}, approx_mid={approx_mid}, low={low}, high={high}, cur_word='{cur_word}'")
                    if cur_word == word_lower or first_word == word_lower:
                        # Found match, backtrack to first occurrence
                        backtrack_pos = pos
                        backtrack_count = 0
                        backtrack_limit = 10
                        while backtrack_pos > low and backtrack_count < backtrack_limit:
                            backtrack_pos = max(low, backtrack_pos - int(avg_line_size))
                            f.seek(backtrack_pos)
                            if backtrack_pos > 0:
                                f.readline()
                            backtrack_pos = f.tell()
                            line = f.readline().strip()
                            try:
                                if not line or dict_from_record(line, header).get(source_field_name, '').lower() != word_lower:
                                    break
                            except (csv.Error, IndexError):
                                break
                            backtrack_count += 1
                        if backtrack_count >= backtrack_limit:
                            print(f"Debug: Backtrack reached limit of {backtrack_limit} at offset={backtrack_pos}")
                        
                        if return_position:
                            return backtrack_pos
                        # Collect matching rows
                        f.seek(backtrack_pos)
                        if backtrack_pos > 0:
                            f.readline()
                        while True:
                            pos = f.tell()
                            line = f.readline().strip()
                            if not line:
                                break
                            row = dict_from_record(line, header)
                            if row.get(source_field_name, '').lower() != word_lower:
                                break
                            data.append(row)
                        break
                    elif cur_word == '' or cur_word > word_lower:
                        high = approx_mid - 1
                    else:
                        low = mid
                if not data and not return_position:
                    print(f"Debug: No matching rows for '{word}' in sorted CSV")
                    return []
            else:
                # Linear scan for unsorted CSV
                f.seek(0)
                reader = csv.DictReader(f, delimiter='\t')
                for row in reader:
                    if row[source_field_name].lower() == word_lower:
                        data.append(row)
                if return_position and data:
                    print("Debug: Linear scan does not support returning position.")
                    return 0
                if not data:
                    print(f"Debug: No matching rows for '{word}' in unsorted CSV")
        
        print(f"Debug: Found {len(data)} matching rows for '{word}' in CSV")
        return data
    except UnicodeDecodeError as e:
        print(f"Debug: Encoding error with '{encoding}': {str(e)}. Falling back to binary mode.")
        try:
            with open(file_path, 'rb') as f:
                # Read header
                header_line = f.readline().decode('utf-8', errors='ignore').strip()
                header = header_line.split('\t')
                if source_field_name not in header:
                    print(f"Error: Source field '{source_field_name}' not in header.")
                    return 0 if return_position else []
                source_idx = header.index(source_field_name)
                data = []
                if csv_sorted:
                    size = os.path.getsize(file_path)
                    f.seek(0)
                    total_size = 0
                    for _ in range(100):
                        line = f.readline()
                        if not line:
                            break
                        total_size += len(line)
                    avg_line_size = total_size / 100 if total_size > 0 else 1
                    line_count = size // avg_line_size
                    low = f.tell()
                    high = size - 1
                    max_iterations = int(line_count * 2)
                    iteration = 0
                    found = False
                    while low <= high:
                        if iteration >= max_iterations:
                            print(f"Debug: Binary search exceeded {max_iterations} iterations. Aborting.")
                            return 0 if return_position else []
                        iteration += 1
                        approx_mid = (low + high) // 2
                        mid = approx_mid
                        f.seek(mid)
                        if mid > 0:
                            f.readline()
                        pos = f.tell()
                        line = f.readline().decode('utf-8', errors='ignore').strip()
                        if not line:
                            high = approx_mid - 1
                            continue
                        first_word = dict_from_record(line, header).get(source_field_name, '').lower()
                        print(f"Debug: Seek offset={pos}, first_word='{first_word}'")
                        mid = pos
                        cur_word = first_word
                        boundary_count = 0
                        max_boundary_checks = 10
                        while cur_word == first_word and boundary_count < max_boundary_checks:
                            mid = f.tell()
                            line = f.readline().decode('utf-8', errors='ignore').strip()
                            if not line:
                                cur_word = ''
                                break
                            cur_word = dict_from_record(line, header).get(source_field_name, '').lower()
                            boundary_count += 1
                        print(f"Debug: Binary search iteration={iteration}, approx_mid={approx_mid}, low={low}, high={high}, cur_word='{cur_word}'")
                        if cur_word == word_lower or first_word == word_lower:
                            found = True
                            backtrack_pos = pos
                            backtrack_count = 0
                            backtrack_limit = 10
                            while backtrack_pos > low and backtrack_count < backtrack_limit:
                                backtrack_pos = max(low, backtrack_pos - int(avg_line_size))
                                f.seek(backtrack_pos)
                                if backtrack_pos > 0:
                                    f.readline()
                                backtrack_pos = f.tell()
                                line = f.readline().decode('utf-8', errors='ignore').strip()
                                try:
                                    if not line or dict_from_record(line, header).get(source_field_name, '').lower() != word_lower:
                                        break
                                except (csv.Error, IndexError):
                                    break
                                backtrack_count += 1
                            if return_position:
                                return backtrack_pos
                            f.seek(backtrack_pos)
                            if backtrack_pos > 0:
                                f.readline()
                            while True:
                                pos = f.tell()
                                line = f.readline().decode('utf-8', errors='ignore').strip()
                                if not line:
                                    break
                                row = dict_from_record(line, header)
                                if row.get(source_field_name, '').lower() != word_lower:
                                    break
                                data.append(row)
                            break
                        elif cur_word == '' or cur_word > word_lower:
                            high = approx_mid - 1
                        else:
                            low = mid
                    if not data and not return_position:
                        print(f"Debug: No matching rows for '{word}' in sorted CSV")
                        return []
                else:
                    f.seek(0)
                    reader = csv.DictReader(f, delimiter='\t')
                    for row in reader:
                        if row[source_field_name].lower() == word_lower:
                            data.append(row)
                    if return_position and data:
                        print("Debug: Linear scan does not support returning position.")
                        return 0
            print(f"Debug: Found {len(data)} matching rows for '{word}' in CSV")
            return data
        except Exception as e:
            print(f"Debug: Binary mode fallback failed: {str(e)}")
            return 0 if return_position else []


# Test with sample CSV
if __name__ == "__main__":
    file_path = os.path.expanduser('~/.var/app/net.ankiweb.Anki/data/Anki2/addons21/quickfill/data/dictionary.csv')
    word = 'memorize'
    source_field_name = 'term'
    csv_sorted = True
    return_position = False
    
    header = get_csv_header(file_path)
    result = get_matching_rows(file_path, word, source_field_name, csv_sorted, return_position=return_position)
    print("Result:", result)
