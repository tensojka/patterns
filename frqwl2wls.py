# Generate a .wls (wordlist separated by newlines) from one or more frqwl

import argparse
from typing import List, Tuple

FORBIDDEN_CHARACTERS = 'ñôçë'

def parse_frqwl(filename: str) -> List[Tuple[str, int]]:
    with open(filename) as inpf:
        return [
            (split[0], int(split[1]))
            for line in inpf
            for split in [line.strip().split("\t")]
            if len(split) == 2 and split[1].isdigit() 
            and not any(c in split[0] for c in FORBIDDEN_CHARACTERS)
        ]

def get_top_n_words(word_freq_list: List[Tuple[str, int]], n: int) -> List[str]:
    return [word for word, _ in sorted(word_freq_list, key=lambda x: x[1], reverse=True)[:n]]

parser = argparse.ArgumentParser()
parser.add_argument('outf', type=str, help='wls output file')
parser.add_argument('inpf', type=str, help='frqwl input file')
parser.add_argument("--len", type=int, default=50000, help='number of top words to include')
parser.add_argument("-v", action='store_true', help='verbose')

args = parser.parse_args()

word_freq_list = parse_frqwl(args.inpf)
top_words = get_top_n_words(word_freq_list, args.len)

if args.v:
    print(f"Words in input file: {len(word_freq_list)}")
    print(f"Words in output: {len(top_words)}")

with open(args.outf, 'w') as of:
    of.write('\n'.join(top_words))