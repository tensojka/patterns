import subprocess
import os
from shutil import copy
from itertools import product
from typing import Tuple, Union, List, Optional
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

    #print(f"Patterns generated for {language} in {non_ipa_patterns_file}. Evaluation:")
    good, bad, missed = validate_using_patgen(groundtruth_filename, non_ipa_patterns_file, language)
    #print(f"{good} good, {bad} bad, {missed} missed")
    return good, bad, missed


def get_groundtruth_for(language: str):
    if language == "uk":
        return "groundtruth/uk-full-wiktionary.wlh"
    elif language == "cs":
        return "groundtruth/cs-ujc.wlh"
    else:
        return f'groundtruth/{language}-wiktionary.wlh'

from count_unique_unicode import generate_translate_file


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

    pattern_final = os.path.join(TEMP_WORKDIR, "pattern.final")
    if os.path.exists(pattern_final):
        copy(pattern_final, output_file)
    else:
        print(f"Error: pattern.final was not generated for {language}")

    #pattmp_4 = os.path.join(TEMP_WORKDIR, "pattmp.4")


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
        (0,), # pl
        (0, 1, 3), # sk
        (0, 1), # uk
        (0, 1, 3) # ru
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

def create_temp_param_file(params_tuple: Tuple[int, ...], base_param_file: str, threshold: int = 5) -> str:
    """Creates a temporary parameter file based on the input tuple and returns its path"""
    temp_param_path = os.path.join(TEMP_WORKDIR, f"temp_params_{hash(params_tuple)}.par")

    # Copy the base parameter file content
    with open(os.path.join('parameters', base_param_file)) as f:
        param_content = f.readlines()

    # Replace good_bad_thres lines with new values
    param_content = [line for line in param_content if not line.startswith('good_bad_thres')]
    for i, bad_value in enumerate(params_tuple, 1):
        param_content.append(f"good_bad_thres[{i}]='1 {bad_value} 5'\n")

    with open(temp_param_path, 'w') as f:
        f.writelines(param_content)

    return temp_param_path


from generate_joint_patterns import generate_joint_patterns

def sample(ipa_files: List[str], weights: Tuple[int, ...], params_ipa: Union[str, Tuple[int, ...]], params_single: Union[str, Tuple[int, ...]], threshold: int, language: str, workdir_i: Optional[int] = None) -> Tuple[int, int, int]:
    global TEMP_WORKDIR
    original_workdir = TEMP_WORKDIR
    TEMP_WORKDIR = TEMP_WORKDIR + language + str(workdir_i) + "/"
    os.makedirs(TEMP_WORKDIR, exist_ok=True)
    output_file = "work/all.pat"

        # Handle tuple parameters by creating temporary parameter files
    actual_params_ipa = (create_temp_param_file(params_ipa, 'csskhyphen.par', threshold)
                        if isinstance(params_ipa, tuple) else params_ipa)
    actual_params_single = (create_temp_param_file(params_single, 'csskhyphen.par', threshold)
                          if isinstance(params_single, tuple) else params_single)

    #print(f"Evaluating weights: {weights}")
    generate_joint_patterns(ipa_files, list(weights), output_file, actual_params_ipa, TEMP_WORKDIR)

    #print(f"Joint IPA patterns saved to: {output_file}")

    res = evaluate_patterns(output_file, get_groundtruth_for(language), f'work/{language}.ipa.wls', language, actual_params_single)
    TEMP_WORKDIR = original_workdir
    return res

def run_with_params(params_ipa, params_single):
    ipa_files = ["work/pl.ipa.wlh", "work/sk.ipa.wlh", "work/uk.ipa.wlh", "work/ru.ipa.wlh"]
    results: List[Tuple[Tuple[int, ...], Tuple[int, ...]]] = []
    weights_to_evaluate = generate_weights_to_evaluate()
    for weights in weights_to_evaluate:
        results.append((weights, sample(ipa_files, weights, params_ipa, params_single, "uk")))


    import json
    import time

    # Generate a unique timestamp
    timestamp = int(time.time())

    json_report = {
        "run_params": {
            "ipa_files": ipa_files,
            "params_ipa" : params_ipa,
            "params_single": params_single,
            "pipeline_version": 2
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
    print(sample(["work/pl.ipa.wlh", "work/sk.ipa.wlh", "work/uk.ipa.wlh", "work/ru.ipa.wlh"], (3,5,0,5), (3,4,6,2), (6,2,5,4), 5, 'uk'))
    print(sample(["work/cs.ipa.wlh", "work/pl.ipa.wlh", "work/sk.ipa.wlh", "work/ru.ipa.wlh"], (3,5,0,5), (3,4,6,2), (6,2,5,4), 5, 'pl'))
    exit()
    run_with_params("csskhyphen.par", "csskhyphen.par")
    run_with_params("ipa-verysmall.par", "csskhyphen.par")
    run_with_params("ipa-verybig.par", "csskhyphen.par")
    run_with_params("ipa-sojka-correctoptimized.par", "csskhyphen.par")
    run_with_params("csskhyphen.par", "ipa-sojka-correctoptimized.par")
    run_with_params("ipa-verybig.par", "ipa-sojka-correctoptimized.par")
    run_with_params("haralambous-default.par", "csskhyphen.par")
    run_with_params("csskhyphen.par", "haralambous-default.par")
