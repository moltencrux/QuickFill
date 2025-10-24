from aqt.utils import showInfo
from .csv_seeker import get_csv_header, get_matching_rows

def load_from_csv(file_path, word, csv_field_mappings, source_field_name, csv_sorted=False):
    """Load data from CSV using csv_seeker."""
    data = get_matching_rows(file_path, word, source_field_name, csv_sorted, return_position=False)
    if not data:
        showInfo(f"No entry found for '{word}' in CSV.")
        return []
    
    # Validate CSV columns
    header = get_csv_header(file_path)
    missing_cols = [col for col in csv_field_mappings.keys() if col not in header]
    if missing_cols:
        showInfo(f"CSV missing columns: {', '.join(missing_cols)}")
        return []
    
    # Concatenate multiple senses
    combined = {}
    for col, field_idx in csv_field_mappings.items():
        separator = ', ' if col in ['part_of_speech', 'pos'] else '; '
        values = [d[col] for d in data if col in d and d[col]]
        if col in ['part_of_speech', 'pos']:
            values = list(set(values))
        combined[field_idx] = separator.join(values) if values else ''
    
    print(f"Debug: Processed CSV data: {combined}")
    return [combined]

if __name__ == "__main__":
    import os
    file_path = os.path.expanduser('~/.var/app/net.ankiweb.Anki/data/Anki2/addons21/quickfill/data/dictionary.csv')
    word = 'memorize'
    source_field_name = 'term'
    csv_field_mappings = {
        'term': 0,
        'notes': 2,
        'definitions': 6,
        'examples': 7,
        'other': -1
    }
    csv_sorted = True
    result = load_from_csv(file_path, word, csv_field_mappings, source_field_name, csv_sorted)
    print("Result:", result)
