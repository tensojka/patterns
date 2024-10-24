import subprocess
import os
from collections import OrderedDict
from itertools import product
from typing import Tuple
from validate import validate_using_patgen

TEMP_WORKDIR = '/var/tmp/ipa-patterns/'

def evaluate_patterns(patterns_filename: str, groundtruth_filename: str, final_training_wordlist: str, language: str, params_single_lang: str) -> Tuple[int, int, int]:
    os.makedirs(TEMP_WORKDIR, exist_ok=True)

    # Use these IPA patterns to hyphenate a specific-language wordlist
    hyphenated_ipa_file = os.path.join(TEMP_WORKDIR, f"{language}.ipa.new.wlh")
    subprocess.run(["python3", "hyph.py", patterns_filename, final_training_wordlist], stdout=open(hyphenated_ipa_file, "w"))

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
    print(f"Patterns generated for {language} in {non_ipa_patterns_file}. Evaluation:")
    return validate_using_patgen(groundtruth_filename, non_ipa_patterns_file, language)


def get_groundtruth_for(language: str):
    if language == "uk":
        return "groundtruth/uk-full-wiktionary.wlh"
    elif language == "cs":
        return "groundtruth/cs-ujc.wlh"
    else:
        return f'groundtruth/{language}-wiktionary.wlh'

from count_unique_unicode import generate_translate_file
from shutil import copy

# expects input file to be absolute path
def generate_non_ipa_patterns(input_file: str, output_file: str, language: str, params_single_lang: str):
    # Create a custom translate file
    translate_file = os.path.join(TEMP_WORKDIR, f"{language}.tra")
    generate_translate_file(translate_file, input_file)

    # Generate patterns using patgen
    params_file = os.path.abspath(os.path.join(os.path.dirname(__file__), 'parameters', params_single_lang))

    make_full_pattern_script = os.path.abspath(os.path.join(os.path.dirname(__file__), 'make-full-pattern.sh'))

    subprocess.run([
        "bash",
        make_full_pattern_script,
        input_file,
        translate_file,
        params_file,
    ], cwd=TEMP_WORKDIR, stdout=subprocess.DEVNULL)

    # Convert the resulting patterns back to Unicode
    pattern_final = os.path.join(TEMP_WORKDIR, "pattern.final")
    if os.path.exists(pattern_final):
        copy(pattern_final, output_file)
    else:
        print(f"Error: pattern.final was not generated for {language}")

    #pattmp_4 = os.path.join(TEMP_WORKDIR, "pattmp.4")


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
        (0, 1, 3), # pl
        (0, 1, 3, 5, 7), # sk
        (0, 1, 3, 5, 7), # uk
        (0, 1, 3, 5, 7) # ru
    ]

    # Generate all combinations of weights
    weights_to_evaluate = list(product(*weight_ranges))

    # Filter out cases where all weights are zero or all weights are the same (except 1)
    weights_to_evaluate = list(filter(lambda w:
        any(w) and  # at least one weight is non-zero
        not (len(set(w)) == 1 and w[0] != 1),  # not all weights are the same, unless they're all 1
        weights_to_evaluate
    ))

    if len(weights_to_evaluate) > 500:
        print(f"It's probably not viable to evaluate {len(weights_to_evaluate)} weight combinations.")
        exit(-1)

    return weights_to_evaluate


#evaluate_patterns("work/all.pat", "groundtruth/cs-ujc.wlh", "work/cs.ipa.wls", "cs")

from typing import Dict, List, Tuple
from generate_joint_patterns import generate_joint_patterns

def evaluate_data_mix(ipa_files: List[str], weights: Tuple[int, ...], params_ipa: str, params_single: str, language: str) -> Tuple[int, int, int]:
    output_file = "work/all.pat"

    print(f"Evaluating weights: {weights}")
    generate_joint_patterns(ipa_files, list(weights), output_file, params_ipa)

    print(f"Joint IPA patterns saved to: {output_file}")

    return evaluate_patterns(output_file, get_groundtruth_for(language), f'work/{language}.ipa.wls', language, params_single)

#print(evaluate_data_mix(["work/sk.ipa.wlh", "work/uk.ipa.wlh"], (8,1), params_ipa, params_single, 'uk'))

def run_with_params(params_ipa, params_single):
    ipa_files = ["work/pl.ipa.wlh", "work/sk.ipa.wlh", "work/uk.ipa.wlh", "work/ru.ipa.wlh"]
    results: List[Tuple[Tuple[int, ...], Tuple[int, ...]]] = []
    weights_to_evaluate = generate_weights_to_evaluate()
    for weights in weights_to_evaluate:
        results.append((weights, evaluate_data_mix(ipa_files, weights, params_ipa, params_single, "uk")))


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
        (g, b, m) = validate_using_patgen("groundtruth/uk-full-wiktionary.wlh", "work/hyph-uk.tex", "uk")
        json_report["validation_results"] = [ (g, b, m)]

    # Save results to a JSON file
    output_filename = f"work/gridsearch-{timestamp}-results.json"
    with open(output_filename, 'w') as f:
        json.dump(json_report, f, indent=2)

    print(f"Results saved to: {output_filename}")

if __name__ == "__main__":
    run_with_params("csskhyphen.par", "csskhyphen.par")
    run_with_params("ipa-verysmall.par", "csskhyphen.par")
    run_with_params("ipa-verybig.par", "csskhyphen.par")
    run_with_params("ipa-sojkacorrectoptimized.par", "csskhyphen.par")
    run_with_params("csskhyphen.par", "ipa-sojkacorrectoptimized.par")
    run_with_params("ipa-verybig.par", "ipa-sojkacorrectoptimized.par")
