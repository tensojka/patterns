import sys
import unicodedata

def count_and_check_unicode_chars(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            text = file.read()
        unique_chars = set(text)
        print(f"Total unique characters: {len(unique_chars)}")
        
        non_iso8859_5_chars = []
        for char in unique_chars:
            try:
                char.encode('iso8859-5')
            except UnicodeEncodeError:
                non_iso8859_5_chars.append(char)
        
        if non_iso8859_5_chars:
            print("\nCharacters without ISO-8859-5 equivalent:")
            for char in sorted(non_iso8859_5_chars):
                name = unicodedata.name(char, "Unknown")
                code_point = f"U+{ord(char):04X}"
                print(f"{char} ({code_point}) - {name}")
        else:
            print("\nAll characters have ISO-8859-5 equivalents.")
        
    except FileNotFoundError:
        print(f"File not found: {filename}")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python count_and_check_unicode.py <filename>")
    else:
        count_and_check_unicode_chars(sys.argv[1])