import os
import re
import sys
from collections import Counter

def process_files(directory, lowercase=True):
    word_counter = Counter()
    total_words = 0
    
    for root, dirs, files in os.walk(directory):
        for file in files:
            file_path = os.path.join(root, file)
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                content = re.sub(r'<[^>]+>', '', content)  # Remove XML tags and attributes
                if lowercase:
                    content = content.lower()
                words = re.findall(r'\b[a-záčďéěíňóřšťúůýž]+(?:-[a-záčďéěíňóřšťúůýž]+)*\b', content)
                word_counter.update(words)
                total_words += len(words)
    
    return word_counter, total_words

def generate_frqwl(word_counter, output_file, filter_numeric=True):
    with open(output_file, 'w', encoding='utf-8') as f:
        for word, count in word_counter.most_common():
            if filter_numeric and word.isdigit():
                continue
            f.write(f"{word}\t{count}\n")

def main():
    if len(sys.argv) != 3:
        print("Usage: python script.py <input_directory> <output_file>")
        sys.exit(1)
    
    input_directory = sys.argv[1]
    output_file = sys.argv[2]
    
    if not os.path.isdir(input_directory):
        print(f"Error: {input_directory} is not a valid directory.")
        sys.exit(1)
    
    lowercase = True
    filter_numeric = True
    
    word_counter, total_words = process_files(input_directory, lowercase)
    generate_frqwl(word_counter, output_file, filter_numeric)
    
    print(f"Processed {total_words} input words, {len(word_counter)} unique.")

if __name__ == '__main__':
    main()