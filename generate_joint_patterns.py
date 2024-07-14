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
    encoded_ipa_file = TEMP_WORKDIR_PREFIX + 'joint.ipa.patenc.wlh'
    translate_filename = TEMP_WORKDIR_PREFIX + 'joint.tra'
    assert(len(ipa_filenames) == len(weights))
    merge_ipa_files(ipa_filenames, weights, joint_ipa_file)
    
    # Encode the merged file and generate the translate file
    translation_dict = encode_ipa_file(joint_ipa_file, encoded_ipa_file)
    generate_translate_file(translation_dict, translate_filename)

    # Train joint patterns on the encoded .ipa.wlh file
    params_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'parameters', 'csskhyphen.par')
    train_joint_patterns(encoded_ipa_file, translate_filename, params_file, output_filename)

def encode_ipa_file(input_file, output_file):
    ipa_chars = OrderedDict()
    encoded_lines = []

    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            encoded_chars = bytearray()
            for char in line.strip():  # Process the entire line
                if ord(char) > 127:
                    if char not in ipa_chars:
                        ipa_chars[char] = len(ipa_chars) + 162
                    encoded_chars.append(ipa_chars[char])
                else:
                    encoded_chars.append(ord(char))
            
            encoded_lines.append(encoded_chars)

    with open(output_file, 'wb') as f:
        f.write(b'\n'.join(encoded_lines))

    return {v: chr(v) for v in ipa_chars.values()}

def generate_translate_file(translation_dict, output_file):
    with open(output_file, 'wb') as f:
        f.write(b" 2 2\n")
        # Write ASCII lowercase letters (a-z)
        for ascii_char in range(ord('a'), ord('z') + 1):
            f.write(b" %c\n" % ascii_char)
        # Write the custom IPA characters
        for eight_bit in translation_dict.keys():
            f.write(b" %c\n" % eight_bit)

    print(f"Translate file generated: {output_file}")

def train_joint_patterns(joint_ipa_file, translate_file, params_file, output_file):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    make_full_pattern_script = os.path.join(script_dir, 'make-full-pattern.sh')
    
    output_dir = os.path.join(TEMP_WORKDIR_PREFIX, 'out')
    os.makedirs(output_dir, exist_ok=True)
    
    command = [
        'bash',
        make_full_pattern_script,
        joint_ipa_file,
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
            # Move the pattern.final file to the specified output file
            os.rename(pattern_final, output_file)
            print(f"Pattern file generated and moved to: {output_file}")
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
                            if not line.startswith('('):
                                output_file.write(f"{line}")  # TODO add back {weight} 
                output_file.write('\n')  # Add a newline between files
            except FileNotFoundError:
                print(f"File not found: {ipa_filename}")
            except Exception as e:
                print(f"An error occurred while processing {ipa_filename}: {e}")

if __name__ == "__main__":
    ipa_files = ["work/cs.ipa.wlh", "work/pl.ipa.wlh", "work/sk.ipa.wlh", "work/uk.ipa.wlh"]
    weights = [3, 1, 1, 1]
    output_file = "work/all.pat"
    generate_joint_patterns(ipa_files, weights, output_file)