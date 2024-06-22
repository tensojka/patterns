# Adapted from https://nedbatchelder.com/code/modules/hyphenate.py

import re
import regex
import sys

class Hyphenator:
    def __init__(self, tex_file):
        self.tree = {}
        self.exceptions = {}
        self.load_patterns_from_tex(tex_file)

    def load_patterns_from_tex(self, tex_file):
        with open(tex_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        patterns = []
        for line in lines:
            line = line.strip()
            if line.startswith('%') or line.startswith('}'):
                continue
            if line.startswith('\\patterns{'):
                line = line[10:]
            patterns.extend(line.split())
        for pattern in patterns:
            self._insert_pattern(pattern)

    def _insert_pattern(self, pattern):
        # Convert the a pattern like 'a1bc3d4' into a string of chars 'abcd'
        # and a list of points [ 0, 1, 0, 3, 4 ].
        chars = re.sub(r'[0-9]', '', pattern)
        points = [int(d or 0) for d in regex.split(r'\D', pattern)]

        # Insert the pattern into the tree.  Each character finds a dict
        # another level down in the tree, and leaf nodes have the list of
        # points.
        t = self.tree
        for c in chars:
            if c not in t:
                t[c] = {}
            t = t[c]
        t[None] = points

    def hyphenate_word(self, word):
        if len(word) <= 4:
            return [word]
        if word.lower() in self.exceptions:
            points = self.exceptions[word.lower()]
        else:
            work = '.' + word.lower() + '.'
            points = [0] * (len(work)+1)
            for i in range(len(work)):
                t = self.tree
                for c in work[i:]:
                    if c in t:
                        t = t[c]
                        if None in t:
                            p = t[None]
                            for j in range(len(p)):
                                points[i+j] = max(points[i+j], p[j])
                    else:
                        break
            points[1] = points[2] = points[-2] = points[-3] = 0
        pieces = ['']
        for c, p in zip(word, points[2:]):
            pieces[-1] += c
            if p % 2:
                pieces.append('')
        return pieces

def main():
    if len(sys.argv) != 3:
        print("Usage: python hyphenator.py <patterns_file.tex> <text_file.txt>")
        sys.exit(1)

    patterns_file = sys.argv[1]
    text_file = sys.argv[2]

    hyphenator = Hyphenator(patterns_file)

    with open(text_file, 'r', encoding='utf-8') as f:
        for line in f:
            words = line.strip().split()
            hyphenated_words = ['-'.join(hyphenator.hyphenate_word(word)) for word in words]
            print(' '.join(hyphenated_words))

if __name__ == '__main__':
    main()
