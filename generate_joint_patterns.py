# This script takes a list of .ipa.wlh files and weights and merges them into a single .ipa.wlh file and trains joint patterns on it. Also creates a translate file for the IPA.

import sys
from os import makedirs
from collections import OrderedDict
from typing import List
import subprocess
import os
import shutil

TEMP_WORKDIR_PREFIX = '/var/tmp/ipa-patterns/'

# Create the temporary work directory if it doesn't exist
makedirs(TEMP_WORKDIR_PREFIX, exist_ok=True)

def decode_pattern_file(input_file, output_file, inverted_translation_dict):
    with open(input_file, 'rb') as f_in, open(output_file, 'w', encoding='utf-8') as f_out:
        for line in f_in:
            decoded_line = ''
            for byte in line:
                if byte > 161:
                    decoded_line += inverted_translation_dict.get(byte, chr(byte))
                else:
                    decoded_line += chr(byte)
            f_out.write(decoded_line)

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

    return ipa_chars

def generate_translate_file(translation_dict, output_file):
    with open(output_file, 'wb') as f:
        f.write(b" 2 2\n")
        # Write ASCII lowercase letters (a-z)
        for ascii_char in range(ord('a'), ord('z') + 1):
            f.write(b" %c\n" % ascii_char)
        # Write the custom IPA characters
        for eight_bit in translation_dict.values():
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
            # Copy the pattern.final file to the specified output file
            shutil.copy2(pattern_final, output_file)
            print(f"Pattern file generated and copied to: {output_file}")
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
                        if line.strip() and '(' not in line:  # espeak sometimes put (en) tags in and tries to be smart
                                output_file.write(f"{line}")  # TODO add back {weight} 
                output_file.write('\n')  # Add a newline between files
            except FileNotFoundError:
                print(f"File not found: {ipa_filename}")
            except Exception as e:
                print(f"An error occurred while processing {ipa_filename}: {e}")

def generate_joint_patterns(ipa_filenames, weights, output_filename, params_filename):
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
    params_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'parameters', params_filename)
    train_joint_patterns(encoded_ipa_file, translate_filename, params_file, output_filename)

    return translation_dict

if __name__ == "__main__":
    ipa_files = ["work/cs.ipa.wlh"]#, "work/pl.ipa.wlh", "work/sk.ipa.wlh", "work/uk.ipa.wlh", "work/sh.ipa.wlh"]
    weights = [2]#[9, 1, 1, 1, 1]
    output_file = "work/all.pat"
    encoded_output_file = "work/all.pat.enc"
    
    translation_dict = generate_joint_patterns(ipa_files, weights, encoded_output_file, 'ipa-sojka-correctoptimized.par')
    print(translation_dict)
    # Decode the pattern file
    decode_pattern_file(encoded_output_file, output_file, {v: k for k, v in translation_dict.items()})
    # Check if pattmp.4 exists in patgen working directory
    patgen_pattmp4 = os.path.join(TEMP_WORKDIR_PREFIX, 'out/pattmp.4')
    if os.path.exists(patgen_pattmp4):
        # Define the target file in the main working directory
        main_pattmp4 = os.path.join('work', 'pattmp.4')
        
        # Use decode_pattern_file to convert and save the file
        decode_pattern_file(patgen_pattmp4, main_pattmp4, {v: k for k, v in translation_dict.items()})
        
        print(f"Converted pattmp.4 saved to: {main_pattmp4}")
    print(f"Joint IPA patterns saved to: {output_file}")