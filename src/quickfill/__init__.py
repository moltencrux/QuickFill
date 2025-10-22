from aqt import mw, gui_hooks
from aqt.addcards import AddCards
from aqt.editor import Editor
from aqt.utils import showInfo
from anki.notes import Note
import requests
from bs4 import BeautifulSoup
import urllib.parse
import os

# Full Yahoo Dictionary scraper
def scrape_word(word):
    config = mw.addonManager.getConfig(__name__)
    parser = config.get("PARSER", "html.parser") if config else "html.parser"
    
    base_url = 'https://tw.dictionary.search.yahoo.com/search?p='
    encoded_word = urllib.parse.quote(word)
    url = base_url + encoded_word
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            showInfo(f"Failed to fetch data for '{word}' (HTTP {response.status_code}).")
            return []
    except requests.RequestException as e:
        showInfo(f"Network error for '{word}': {str(e)}")
        return []
    
    try:
        soup = BeautifulSoup(response.text, parser)
    except Exception as e:
        showInfo(f"Parsing error for '{word}': {str(e)}. Try setting PARSER to 'html.parser' or install 'lxml'.")
        return []
    
    data = []
    
    # Main dictionary word card
    main_card = soup.find('div', class_='dictionaryWordCard')
    if not main_card:
        showInfo(f"No entry found for '{word}'.")
        return []
    
    # Extract word
    word_tag = main_card.find('span', class_='fz-24')
    entry_word = word_tag.text.strip() if word_tag else word
    
    # Extract pronunciations (KK only, without labels)
    pron_ul = main_card.find('div', class_='compList d-ib')
    pronunciation = ''
    if pron_ul:
        prons = pron_ul.find_all('li')
        if prons and prons[0].text.strip().startswith('KK'):
            # Extract only the phonetic symbols after 'KK'
            pron_text = prons[0].text.strip()
            pronunciation = pron_text.replace('KK', '', 1).strip()
    
    # Inflections
    infl_ul = main_card.find('ul', class_='compArticleList')
    inflections = ''
    if infl_ul:
        infl_h4 = infl_ul.find('h4')
        inflections = infl_h4.text.strip() if infl_h4 else ''
    
    # Detailed explanations from "釋義" tab
    explanation_div = soup.find('div', class_='grp-tab-content-explanation')
    pos = ''
    def_zh_str = ''
    examples_str = ''
    if explanation_div:
        pos_labels = explanation_div.find_all('label')
        pos_list = []
        def_list = []
        ex_list = []
        for pos_label in pos_labels:
            pos_span = pos_label.find('span', class_='pos_button')
            pos = pos_span.text.strip() if pos_span else ''
            pos_list.append(pos)
            
            ul = pos_label.find_next_sibling('div', class_='compTextList').find('ul')
            if ul:
                lis = ul.find_all('li')
                def_senses = []
                examples = []
                for li in lis:
                    sense_num = li.find('span', class_='fw-xl d-b cl-b p-abs l-0').text.strip()
                    def_span = li.find('span', class_='d-i fz-14 lh-20')
                    if def_span:
                        def_text = def_span.text.strip()
                        def_senses.append(f"{sense_num} {def_text}")
                    
                    ex_span = li.find('span', class_='d-b fz-14 fc-2nd lh-20')
                    if ex_span:
                        ex_text = ex_span.text.strip()
                        parts = ex_text.split('。', 1)
                        en_ex = parts[0].strip() + '。' if parts else ''
                        zh_ex = parts[1].strip() if len(parts) > 1 else ''
                        if en_ex:
                            examples.append(f"{en_ex} ~~ {zh_ex}")
                
                if def_senses:
                    def_list.append(f"{pos} {'; '.join(def_senses)}")
                if examples:
                    ex_list.append(f"{pos} {' | '.join(examples)}")
        
        if def_list:
            def_zh_str = '; '.join(def_list)
        if ex_list:
            examples_str = ' | '.join(ex_list)
        if pos_list:
            pos = ', '.join(pos_list)
    
    data.append({
        'word': entry_word,
        'pronunciation': pronunciation,
        'pos': pos,
        'inflections': inflections,
        'def_zh': def_zh_str,
        'examples': examples_str
    })
    
    # Related words/phrases
    if config and config.get("INCLUDE_RELATED_WORDS", False):
        related_div = soup.find('div', class_='grp-tab-content-algo')
        if related_div:
            titles = related_div.find_all('h3', class_='title')
            for title in titles:
                a = title.find('a')
                if a:
                    rel_word = a.text.strip()
                    next_div = a.find_parent().find_next_sibling('div', class_='compTextList')
                    if next_div:
                        li = next_div.find('ul').find('li')
                        pos_tag = li.find('div', class_='pos_button')
                        rel_pos = pos_tag.text.strip() if pos_tag else ''
                        def_span = li.find('span', class_='fz-14 d-i ml-1 va-mid')
                        rel_def = def_span.text.strip() if def_span else ''
                        # Insert rel_pos into rel_def if rel_pos exists
                        if rel_pos and rel_def:
                            rel_def = f"{rel_pos} {rel_def}"
                        data.append({
                            'word': rel_word,
                            'pronunciation': '',
                            'pos': rel_pos,
                            'inflections': '',
                            'def_zh': rel_def,
                            'examples': ''
                        })
    return data

# Create default note type
def create_default_note_type(note_type_name):
    if mw.col.models.by_name(note_type_name):
        return mw.col.models.by_name(note_type_name)
    
    model = mw.col.models.new(note_type_name)
    fields = ["Word", "Pronunciation", "POS", "Inflections", "Definition_ZH", "Examples"]
    for field in fields:
        mw.col.models.addField(model, mw.col.models.newField(field))
    
    tmpl = mw.col.models.newTemplate("Card 1")
    tmpl['qfmt'] = "{{Word}}"
    tmpl['afmt'] = "{{FrontSide}}<hr id=answer>{{Pronunciation}}<br>{{POS}}<br>{{Definition_ZH}}<br>{{Examples}}"
    mw.col.models.addTemplateInOrder(model, tmpl)
    mw.col.models.add(model)
    mw.col.models.setCurrent(model)
    return model

# Add button to editor
def setup_editor_buttons(buttons, editor):
    config = mw.addonManager.getConfig(__name__)
    addon_folder = mw.addonManager.addonFromModule(__name__)
    addon_path = os.path.join(mw.addonManager.addonsFolder(), addon_folder)
    icon_path = os.path.join(addon_path, "images", "quickfill.svg")
    
    button = editor.addButton(
        icon=icon_path if os.path.exists(icon_path) else None,
        cmd="yahoo_fetch",
        func=lambda ed: fetch_and_fill(ed),
        tip="Fetch from Yahoo Dictionary (Ctrl+Alt+E)",
        keys="Ctrl+Alt+E"
    )
    buttons.append(button)
    return buttons

# Fetch and fill function
def fetch_and_fill(editor):
    config = mw.addonManager.getConfig(__name__)
    if not config:
        showInfo("Configuration not found. Please check Tools > Add-ons > Yahoo Dictionary Autofill > Config.")
        return
    
    # Use default template if enabled
    note_type_name = config.get("NOTE_TYPE", "YahooDictionary")
    if config.get("USE_DEFAULT_TEMPLATE", True):
        if not mw.col.models.by_name(note_type_name):
            create_default_note_type(note_type_name)
        if editor.note.model()['name'] != note_type_name:
            model = mw.col.models.by_name(note_type_name)
            if model:
                mw.col.models.change(editor.note.model(), [editor.note.id], model, {}, {})
                editor.loadNoteKeepingFocus()
            else:
                showInfo(f"Note type '{note_type_name}' not found and could not be created.")
                return
    
    # Get word from source field
    source_field_idx = config.get("SOURCE_FIELD", 0)
    if source_field_idx >= len(editor.note.fields):
        showInfo("Source field index out of range.")
        return
    
    word = editor.note.fields[source_field_idx].strip()
    if not word:
        showInfo("Please enter a word in the source field.")
        return
    
    # Scrape data
    data_list = scrape_word(word)
    if not data_list:
        return  # Error already shown in scrape_word
    
    # Field mappings
    field_map = {
        'word': config.get("WORD_FIELD", -1),
        'pronunciation': config.get("PRONUNCIATION_FIELD", 1),
        'pos': config.get("POS_FIELD", 2),
        'inflections': config.get("INFLECTIONS_FIELD", 3),
        'def_zh': config.get("DEFINITION_ZH_FIELD", 4),
        'examples': config.get("EXAMPLES_FIELD", 5)
    }
    
    # Validate field indices
    for data_key, field_idx in field_map.items():
        if field_idx >= 0 and field_idx >= len(editor.note.fields):
            showInfo(f"Field index {field_idx} for '{data_key}' is out of range for note type '{editor.note.model()['name']}'.")
            return
    
    # Process scraped data
    for data in data_list:
        note = editor.note
        if data != data_list[0] and config.get("INCLUDE_RELATED_WORDS", False):
            deck_id = mw.col.decks.id(config.get("DECK_NAME", "Default"))
            model = mw.col.models.by_name(note.model()['name'])
            if not model:
                showInfo(f"Note type '{note.model()['name']}' not found for related words.")
                continue
            note = Note(mw.col, model)
            note.addTag("YahooDictionary")
            mw.col.addNote(note)
        
        for data_key, field_idx in field_map.items():
            if field_idx >= 0 and field_idx < len(note.fields) and data_key in data:
                note.fields[field_idx] = data[data_key]
        
        if data == data_list[0]:
            editor.loadNoteKeepingFocus()

# Hooks
gui_hooks.editor_did_init_buttons.append(setup_editor_buttons)