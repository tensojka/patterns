import subprocess
import os
from collections import OrderedDict
from itertools import product
from typing import Tuple

TEMP_WORKDIR = '/var/tmp/ipa-patterns/' 

def evaluate_patterns(patterns_filename: str, groundtruth_filename: str, final_training_wordlist: str, language: str, params_single_lang: str) -> Tuple[int, int, int]:
    os.makedirs(TEMP_WORKDIR, exist_ok=True)

    # Use these IPA patterns to hyphenate a specific-language wordlist
    hyphenated_ipa_file = os.path.join(TEMP_WORKDIR, f"{language}.ipa.new.wlh")
    subprocess.run(["python", "hyph.py", patterns_filename, final_training_wordlist], stdout=open(hyphenated_ipa_file, "w"))

    # Convert the hyphenated wordlist from IPA
    hyphenated_file = os.path.join(TEMP_WORKDIR, f"{language}.new.wlh")
    run_if_needed(
        ["wlh2ipawlh/target/release/ipawlh2wlh", hyphenated_ipa_file, hyphenated_file],
        hyphenated_ipa_file,
        hyphenated_file,
        f"IPA conversion for {language}"
    )

    # Generate single-language non-IPA patterns
    non_ipa_patterns_file = os.path.join(TEMP_WORKDIR, f"{language}.new.pat")
    generate_non_ipa_patterns(hyphenated_file, non_ipa_patterns_file, language, params_single_lang)

    # Evaluation will be done later
    print(f"Patterns generated for {language}. Evaluation:")
    return validate(groundtruth_filename, non_ipa_patterns_file)


def generate_non_ipa_patterns(input_file: str, output_file: str, language: str, params_single_lang: str):
    # Create a custom translate file
    translate_file = os.path.join(TEMP_WORKDIR, f"{language}.tra")
    encoding_dict = create_translate_file(input_file, translate_file)

    # Generate patterns using patgen
    params_file = os.path.abspath(os.path.join(os.path.dirname(__file__), 'parameters', params_single_lang))
    encoded_input_file = os.path.join(TEMP_WORKDIR, f"{language}.encoded.wlh")
    encode_file(input_file, encoded_input_file, encoding_dict)

    make_full_pattern_script = os.path.abspath(os.path.join(os.path.dirname(__file__), 'make-full-pattern.sh'))

    subprocess.run([
        "bash", 
        make_full_pattern_script, 
        encoded_input_file, 
        translate_file, 
        params_file
    ], cwd=TEMP_WORKDIR)

    # Convert the resulting patterns back to Unicode
    pattern_final = os.path.join(TEMP_WORKDIR, "pattern.final")
    if os.path.exists(pattern_final):
        decode_pattern_file(pattern_final, output_file, {v: k for k, v in encoding_dict.items()})
    else:
        print(f"Error: pattern.final was not generated for {language}")

def create_translate_file(input_file: str, translate_file: str) -> OrderedDict:
    chars = OrderedDict()
    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            for char in line.strip():
                if char == '-':
                    continue
                if ord(char) >= 128 and char not in chars:
                    chars[char] = len(chars) + 162

    with open(translate_file, 'wb') as f:
        f.write(b" 2 2\n")
        # Write ASCII lowercase letters (a-z)
        for ascii_char in range(ord('a'), ord('z') + 1):
            f.write(b" %c\n" % ascii_char)
        # Write the custom characters
        for eight_bit in chars.values():
            f.write(b" %c\n" % eight_bit)

    return chars

def encode_file(input_file: str, output_file: str, encoding_dict: OrderedDict):
    with open(input_file, 'r', encoding='utf-8') as f_in, open(output_file, 'wb') as f_out:
        for line in f_in:
            encoded_line = bytearray()
            for char in line:
                if ord(char) < 128:
                    encoded_line.append(ord(char))
                else:
                    encoded_line.append(encoding_dict.get(char, ord(char)))
            f_out.write(encoded_line)

def decode_pattern_file(input_file, output_file, inverted_encoding_dict):
    with open(input_file, 'rb') as f_in, open(output_file, 'w', encoding='utf-8') as f_out:
        for line in f_in:
            decoded_line = ''
            for byte in line:
                if byte > 161:
                    decoded_line += inverted_encoding_dict.get(byte, chr(byte))
                else:
                    decoded_line += chr(byte)
            f_out.write(decoded_line)

from hyph import Hyphenator

# Given a filename of a hyphenated .wlh wordlist and a filename of
# patterns to use, report how many hyphenation points were correctly found.
# Returns (good, bad, missed)
def validate(wlh, pat):
    #patfile = open(pat, "r")
    #patterns = patfile.read().split('\n')
    hyphenator = Hyphenator(pat)
    wlhfile = open(wlh, "r")
    good = 0  # present in validation wl and patterns
    bad = 0  # not present in validation wl, but in patterns
    missed = 0  # present in validation wl, but not in patterns
    for line in wlhfile.readlines():
        if line[0].isnumeric:
            line = line[1:]
        valid_hyph_word = line[:-1]
        word = valid_hyph_word.replace("-", "")
        pat_hyph_word = "-".join(hyphenator.hyphenate_word(word))
        offset = 0
        for pos, char in enumerate(valid_hyph_word):
            try:
                if char == "-" and pat_hyph_word[pos+offset] == "-":
                    if pos > 1 and pos < (len(pat_hyph_word)+offset-2):
                        good += 1
                elif char == "-" and pat_hyph_word[pos+offset] != "-":
                    if pos > 1 and pos < (len(pat_hyph_word)+offset-2):
                        missed += 1
                    offset -= 1
                elif char != "-" and pat_hyph_word[pos+offset] == "-":
                    if pos > 1 and pos < (len(pat_hyph_word)+offset-2):
                        bad += 1
                    offset += 1
            except IndexError:
                print("Val: "+valid_hyph_word)
                print("Pat: "+pat_hyph_word)


        #if valid_hyph_word != pat_hyph_word:
        #    print(valid_hyph_points)
        #    print(pat_hyph_points)
        #    print("Val: "+valid_hyph_word)
        #    print("Pat: "+pat_hyph_word)
    total = good + missed + bad
    print("good: " + str(good) + ", good %: " + str(round(100*(good/total),2)))
    print("missed: " + str(missed) + ", missed %: " + str(round(100*(missed/total),2)))
    print("bad: " + str(bad) + ", bad %: " + str(round(100*(bad/total),2)))
    return (good, bad, missed)

def run_if_needed(cmd, source_file, target_file, description):
    if not os.path.exists(target_file) or not os.path.exists(source_file):
        should_run = True
    else:
        try:
            source_mtime = os.path.getmtime(source_file)
            target_mtime = os.path.getmtime(target_file)
            should_run = source_mtime > target_mtime
        except OSError:
            should_run = True

    if should_run:
        subprocess.run(cmd)
    else:
        print(f"Skipping {description}, target file is up to date.")

def generate_weights_to_evaluate():
    # Define the range of values for each weight
    weight_ranges = [
        (0, 1), # pl
        (0, 1), # sk
        (0, 1), # uk
        (0, 1) # ru
    ]

    # Generate all combinations of weights
    weights_to_evaluate = list(product(*weight_ranges))
    
    # Optionally, limit the number of combinations if it's too large
    max_combinations = 100  # Adjust this value based on your computational resources
    if len(weights_to_evaluate) > max_combinations:
        print("Cutting combinations")
        weights_to_evaluate = weights_to_evaluate[:max_combinations]
    
    return weights_to_evaluate


#evaluate_patterns("work/all.pat", "groundtruth/cs-ujc.wlh", "work/cs.ipa.wls", "cs")

from typing import Dict, List, Tuple
from generate_joint_patterns import generate_joint_patterns

def evaluate_data_mix(ipa_files: List[str], weights: Tuple[int, ...], params_ipa: str, params_single: str) -> Tuple[int, int, int]:
    output_file = "work/all.pat"
    encoded_output_file = "work/all.pat.enc"

    print(f"Evaluating weights: {weights}")
    translation_dict = generate_joint_patterns(ipa_files, list(weights), encoded_output_file, params_ipa)
    print(translation_dict)
    
    # Decode the pattern file
    decode_pattern_file(encoded_output_file, output_file, {v: k for k, v in translation_dict.items()})
    print(f"Joint IPA patterns saved to: {output_file}")

    return evaluate_patterns(output_file, "groundtruth/uk-full-wiktionary.wlh", "work/uk.ipa.wls", "uk", params_single)


if __name__ == "__main__":
    ipa_files = ["work/pl.ipa.wlh", "work/sk.ipa.wlh", "work/uk.ipa.wlh", "work/ru.ipa.wlh"]
    results: List[Tuple[Tuple[int, ...], Tuple[int, ...]]] = []
    weights_to_evaluate = generate_weights_to_evaluate()
    output_file = "work/all.pat"
    encoded_output_file = "work/all.pat.enc"
    params_ipa = "ipa-sojka-correctoptimized.par"
    params_single = "csskhyphen.par"
    for weights in weights_to_evaluate:
        results.append((weights, evaluate_data_mix(ipa_files, weights, params_ipa, params_single)))


    import json
    import time

    # Generate a unique timestamp
    timestamp = int(time.time())

    json_report = {
        "run_params": {
            "ipa_files": ipa_files,
            "params_ipa" : params_ipa,
            "params_single": params_single,
            "pipeline_version": 1
        },
        "results": results
    }

    if os.path.exists("work/hyph-uk.tex"):
        (g, b, m) = validate("groundtruth/uk-full-wiktionary.wlh", "work/hyph-uk.tex")
        json_report["validation_results"] = [ (g, b, m)]

    # Save results to a JSON file
    output_filename = f"work/gridsearch-{timestamp}-results.json"
    with open(output_filename, 'w') as f:
        json.dump(json_report, f, indent=2)

    print(f"Results saved to: {output_filename}")