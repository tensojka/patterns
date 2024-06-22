import sys

def count_unique_unicode_chars_in_file(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            text = file.read()
        unique_chars = set(text)
        print(len(unique_chars))
    except FileNotFoundError:
        print(f"file not found: {filename}")
    except Exception as e:
        print(f"an error occurred: {e}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python script.py <filename>")
    else:
        count_unique_unicode_chars_in_file(sys.argv[1])