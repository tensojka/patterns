# This script takes a list of .ipa.wlh files and weights and merges them into a single .ipa.wlh file and trains joint patterns on it. Also creates a translate file for the IPA.

import sys
from os import makedirs
from collections import OrderedDict
from typing import List
import subprocess
import os

TEMP_WORKDIR_PREFIX = '/var/tmp/ipa-patterns/'

# Create the temporary work directory if it doesn't exist
makedirs(TEMP_WORKDIR_PREFIX, exist_ok=True)


def generate_joint_patterns(ipa_filenames, weights, output_filename):
    # Merge the .ipa.wlh files into a single .ipa.wlh file
    joint_ipa_file = TEMP_WORKDIR_PREFIX + 'joint.ipa.wlh'
    translate_filename = TEMP_WORKDIR_PREFIX + 'joint.tra'
    assert(len(ipa_filenames) == len(weights))
    merge_ipa_files(ipa_filenames, weights, joint_ipa_file)
    generate_translate_file(joint_ipa_file, translate_filename)

    # Train joint patterns on the merged .ipa.wlh file
    params_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'parameters', 'csskhyphen.par')
    train_joint_patterns(joint_ipa_file, translate_filename, params_file)


def train_joint_patterns(joint_ipa_file, translate_file, params_file):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    make_full_pattern_script = os.path.join(script_dir, 'make-full-pattern.sh')
    
    output_dir = os.path.join(TEMP_WORKDIR_PREFIX, 'out')
    os.makedirs(output_dir, exist_ok=True)
    
    command = [
        'bash',
        make_full_pattern_script,
        joint_ipa_file,  # Use full path to the input file
        translate_file,
        params_file
    ]
    
    try:
        process = subprocess.Popen(
            command,
            cwd=output_dir,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        for line in process.stderr:
            sys.stderr.write(line)
            sys.stderr.flush()
        
        return_code = process.wait()
        
        pattern_final = os.path.join(output_dir, 'pattern.final')
        if os.path.exists(pattern_final):
            print(f"Pattern file generated: {pattern_final}")
        else:
            print("Error: pattern.final was not generated", file=sys.stderr)
        
        if return_code != 0:
            raise subprocess.CalledProcessError(return_code, command)
    
    except subprocess.CalledProcessError as e:
        print(f"Error running make-full-pattern.sh: {e}", file=sys.stderr)


def merge_ipa_files(ipa_filenames, weights: List[int], output_filename: str):
    with open(output_filename, 'w', encoding='utf-8') as output_file:
        for ipa_filename, weight in zip(ipa_filenames, weights):
            try:
                with open(ipa_filename, 'r', encoding='utf-8') as input_file:
                    for line in input_file:
                        if line.strip():  # Check if line is not empty
                            output_file.write(f"{line}")  # TODO add back {weight} 
                output_file.write('\n')  # Add a newline between files
            except FileNotFoundError:
                print(f"File not found: {ipa_filename}")
            except Exception as e:
                print(f"An error occurred while processing {ipa_filename}: {e}")

def generate_translate_file(joint_ipa_file, output_file):
    # Read the joint IPA file
    with open(joint_ipa_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Extract unique non-ASCII IPA characters
    ipa_chars = set(char for char in content if ord(char) > 127)

    # Check if there are more than 96 unique IPA characters
    if len(ipa_chars) > 96:
        print(f"Error: More than 96 unique IPA characters found ({len(ipa_chars)}). Cannot proceed.")
        sys.exit(1)

    # Create an OrderedDict to maintain insertion order
    translate_dict = OrderedDict()

    # Assign 8-bit characters (starting from A0 hex / 160 decimal)
    for i, ipa_char in enumerate(sorted(ipa_chars)):
        eight_bit_char = chr(160 + i)
        translate_dict[eight_bit_char] = ipa_char

    # Write the translate file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(" 2 2\n")
        f.write("%% This is an automatically generated translate file for IPA characters\n")
        f.write("%% encoding: Custom (IPA to 8-bit)\n")
        f.write("%%\n")
        for eight_bit, ipa in translate_dict.items():
            f.write(f" {eight_bit} {ipa} \n")

    print(f"Translate file generated: {output_file}")
    return translate_dict


if __name__ == "__main__":
    ipa_files = ["work/cs.ipa.wlh", "work/pl.ipa.wlh", "work/sk.ipa.wlh", "work/uk.ipa.wlh"]
    weights = [3, 1, 1, 1]
    output_file = "ipa/all.ipa.wlh"
    generate_joint_patterns(ipa_files, weights, output_file)