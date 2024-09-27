import xml.etree.ElementTree as ET
import re
import sys
import unicodedata

# Creates ground truth data from Wiktionary for Ukrainian language.

def load_xml(file_path):
    tree = ET.parse(file_path)
    return tree.getroot()

def remove_accents(text):
    return ''.join(char for char in unicodedata.normalize('NFD', text)
                   if unicodedata.category(char) != 'Mn')

def extract_syllables(line):
    # Pattern to match only {{склади|...}}
    pattern = r'склади={{склади\|(.*?)}}'
    match = re.search(pattern, line)
    if match:
        syllables = match.group(1)
        res = syllables.replace('|', '-').replace('-.-', '-')
        if not ('---' in res or res.endswith('-')):
            return res
    return None

def process_page(page: ET.Element, namespace: dict):
    title_elem = page.find('mw:title', namespace)
    if title_elem is None:
        return None
    title = title_elem.text
    if ' ' in title:  # Skip multi-word titles
        return None
    #print(f"Processing title: {title}")

    text_elem = page.find('.//mw:text', namespace)
    if text_elem is None or text_elem.text is None:
        return None
    text = text_elem.text

    if '{{=uk=}}' not in text:  # Confirm it's a Ukrainian entry
        return None

    # Find the syllable form
    for line in text.split('\n'):
        syllables = extract_syllables(line)
        if syllables:
            return title, syllables
    
    return None

def main(file_path):
    root = load_xml(file_path)
    namespace = {'mw': 'http://www.mediawiki.org/xml/export-0.11/'}
    pages = root.findall('.//mw:page', namespace)
    #print(f"Total pages found: {len(pages)}")
    for page in pages:
        result = process_page(page, namespace)
        if result:
            word, syllables = result
            #print(f"Word: {word}, Syllables: {syllables}")
            if len(syllables) > 3 and syllables.count('-') > 1:
                print(remove_accents(syllables))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python parse_ground_truth.py <file_path>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    main(file_path)
