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

def generate_translate_file(translate_filename, inp_filename, inp2_filename=None):
    with open(inp_filename, 'r', encoding='utf-8') as file:
        text = file.read()
    unique_chars = set(text)
    with open(inp2_filename, 'r', encoding='utf-8') as f:
        t2 = f.read()
    unique_chars = unique_chars | set(t2)
    chars_for_translatefile = unique_chars - set(['\n', '-', '<', '/', '.'])

    with open(translate_filename, 'wb') as f:
        f.write(b" 2 2\n")
        for char in chars_for_translatefile:
            if not char.isnumeric():
                f.write(f" {char} \n".encode('utf-8'))


def count_unique_chars(file1, file2):
    def read_chars(file):
        with open(file, 'rb') as f:
            all_bytes = set(f.read())
            filtered_bytes = set(byte for byte in all_bytes if byte > 162)
            return all_bytes, filtered_bytes

    all_chars1, chars1 = read_chars(file1)
    all_chars2, chars2 = read_chars(file2)

    unique_to_file1 = chars1 - chars2
    unique_to_file2 = chars2 - chars1

    print(f"Total unique bytes in {file1}: {len(all_chars1)}")
    print(f"Total unique bytes in {file2}: {len(all_chars2)}")
    print(f"Bytes > 162 unique to {file1}: {len(unique_to_file1)}")
    print(f"Bytes > 162 unique to {file2}: {len(unique_to_file2)}")
    print(f"Unique to {file1}: {', '.join(map(str, sorted(unique_to_file1)))}")
    print(f"Unique to {file2}: {', '.join(map(str, sorted(unique_to_file2)))}")