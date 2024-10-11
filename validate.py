import subprocess
import os
import shutil
# Directly uses patgen to get data on the validation perf of a given validation wl and a given pattern set.

WORKDIR = '/var/tmp/validate-patterns'
os.makedirs(WORKDIR, exist_ok=True)

# expects both wlh and pat to be in UTF-8
def validate(wlh, pat, lang):
    if lang != 'uk':
        print('must be ukr')
        exit(1)
    # Convert relative filenames to absolute paths
    current_dir = os.getcwd()
    wlh = os.path.abspath(os.path.join(current_dir, wlh))
    pat = os.path.abspath(os.path.join(current_dir, pat))
    # Prepare the input for patgen
    patgen_input = "1 1\n1 9\n1 1 10000\ny\n"

    # Run patgen command
    process = subprocess.Popen(
        ['patgen', wlh, pat, '/dev/null', '/Users/onda/patterns/patterns/translatefiles/uk'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=WORKDIR,
        #check=True
    )

    stdout, stderr = process.communicate(input=patgen_input)

    print(stdout)
    print(stderr)


#validate('groundtruth/uk-full-wiktionary.wlh', '/var/tmp/ipa-patterns/uk.new.pat', 'uk')
validate('groundtruth/uk-full-wiktionary.wlh', 'work/uk-orig.pat', 'uk')