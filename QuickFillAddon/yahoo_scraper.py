import requests
from bs4 import BeautifulSoup
import urllib.parse
from aqt.utils import showInfo

def scrape_word(word, config=None):
    """Scrape word data from Yahoo Dictionary."""
    parser = config.get("parser", "html.parser") if config else "html.parser"
    
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
            pos_val = pos_span.text.strip() if pos_span else ''
            pos_list.append(pos_val)
            
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
                    def_list.append(f"{pos_val} {'; '.join(def_senses)}")
                if examples:
                    ex_list.append(f"{pos_val} {' | '.join(examples)}")
        
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
    if config and config.get("include_related_words", False):
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

if __name__ == "__main__":
    word = 'memorize'
    result = scrape_word(word)
    print("Result:", result)
