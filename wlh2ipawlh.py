import subprocess
import sys
from transform_hyphens import transform
import os
import multiprocessing
from functools import partial

def get_language(filename):
    lowercase_filename = filename.lower()
    if 'pl' in lowercase_filename:
        return 'pl'
    elif 'cs' in lowercase_filename:
        return 'cs'
    print("defaulting to cs lang, no match!")
    return 'cs'  # Default to Czech if no match

def get_ipa(word, language):
    command = f"espeak-ng -vzlw/{language} --ipa '{word}' 2>/dev/null"
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    return result.stdout.strip()

def process_word(hyphenated_word, language):
    stripped_word = hyphenated_word.replace("-", "")
    ipa_word = get_ipa(stripped_word, language)
    return transform(hyphenated_word, ipa_word)

def main(input_file, output_file):
    language = get_language(os.path.basename(input_file))
    print("using language: "+language)
    with open(input_file, 'r') as file:
        words = file.read().splitlines()
    
    # Use all available cores minus one
    num_cores = max(1, multiprocessing.cpu_count() - 1)
    
    # Create a partial function with the language parameter
    process_word_with_lang = partial(process_word, language=language)
    
    # Use Pool to distribute work across cores
    with multiprocessing.Pool(num_cores) as pool:
        results = pool.map(process_word_with_lang, words)
    
    with open(output_file, 'w') as out_file:
        for result in results:
            out_file.write(f"{result}\n")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python wlh2ipawlh.py <input_file> <output_file>")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
