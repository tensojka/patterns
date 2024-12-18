import re
import subprocess
import os
import sys
from typing import Optional, Tuple
# Directly uses patgen to get data on the validation perf of a given validation wl and a given pattern set.

WORKDIR = '/var/tmp/validate-patterns'
os.makedirs(WORKDIR, exist_ok=True)

# Cleans pattern.tex file to be edible by patgen. Sends result to WORKDIR/pat.pat
def clean_pattern_dot_tex(tex_file: str) -> str:
    result_filename = os.path.abspath(os.path.join(WORKDIR, 'pat.pat'))
    with open(result_filename, 'w', encoding='utf-8') as outf:
        with open(tex_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        patterns = []
        for line in lines:
            line = line.strip()
            if line.startswith('%') or line.startswith('}') or line.startswith("\\hyphenation{"):
                continue
            if '-' in line:
                continue
            if line.startswith('\\patterns{'):
                line = line[10:]
            patterns.extend(line.split())
        for pattern in patterns:
            outf.write(pattern+'\n')
    return result_filename

# expects both wlh and pat to be in UTF-8
def validate_using_patgen(wlh, pat, lang) -> Tuple[int, int, int]:
    if lang != 'uk' and lang != 'pl':
        print('lang must be uk or pl')
        exit(1)
    # Convert relative filenames to absolute paths
    current_dir = os.getcwd()
    wlh = os.path.abspath(os.path.join(current_dir, wlh))
    pat = os.path.abspath(os.path.join(current_dir, pat))
    if pat.endswith('.tex'):
        pat = clean_pattern_dot_tex(pat)
    translatefile = os.path.abspath(os.path.join(current_dir, "translatefiles/"+lang))
    # Prepare the input for patgen
    patgen_input = "1 1\n1 9\n1 1 10000\ny\n"

    # Run patgen command
    process = subprocess.Popen(
        ['patgen', wlh, pat, '/dev/null', translatefile],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=WORKDIR,
        #check=True
    )

    stdout, stderr = process.communicate(input=patgen_input)

    print(stderr, sys.stderr)

    # Extract counts using a more precise method
    pattern = r'(\d+) good, (\d+) bad, (\d+) missed'
    match = re.search(pattern, stdout)

    if match:
        return tuple(map(int, match.groups())) # type: ignore
    else:
        print(stdout, sys.stderr)
        raise Exception(f"Failed to extract counts from patgen output. wlh: {wlh}, pat: {pat}, translatefile: {translatefile}")


#validate('groundtruth/uk-full-wiktionary.wlh', '/var/tmp/ipa-patterns/uk.new.pat', 'uk')
#validate('groundtruth/uk-full-wiktionary.wlh', 'work/uk-orig.pat', 'uk')


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 4:
        print("Usage: python validate.py <wlh_file> <pat_file> <lang>")
        sys.exit(1)

    wlh_file = sys.argv[1]
    pat_file = sys.argv[2]
    lang = sys.argv[3]

    good, bad, missed = validate_using_patgen(wlh_file, pat_file, lang)
    print(f"{good} good, {bad} bad, {missed} missed")
