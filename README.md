# System for Transfer Learning of Slavic Syllabification

This repository contains the implementation of pattern generation pipeline described in my Bachelor's thesis "Transfer Learning of Slavic Syllabification" (Masaryk University, 2024).

## Overview

The pipeline enables transfer of hyphenation knowledge between related languages by:

1. Using existing hyphenation patterns from source languages to hyphenate wordlists
2. Converting hyphenated words to IPA to highlight phonological similarities
3. Generating joint IPA patterns
4. Using these to hyphenate words in the target language
5. Converting back to target language orthography
6. Generating new hyphenation patterns

The main innovation is the use of IPA as an intermediate representation and Gaussian process optimization for parameter tuning.

## Requirements

- Nix package manager
- at most 90 GB of free space

Attempt to install dependencies without Nix only if you're feeling particularly adventurous. If you choose to do so, you are on your own. Use Python 3.8 specifically for wikiextractor and Python 3.11 for the rest. See the provided Nix environment in `shell.nix` and nixpkgs for the exact dependency versions. 

## Usage

The main workflow is orchestrated through the Makefile:

```bash
TARGET_LANGUAGE={pl/uk} nice make -j
```

This will download dumps of all the Wikipedias, create for each source language `LANG.ipa.wlh` and start the optimizer, optimizing for good Ukrainian patterns if `LANGUAGE=uk` and for Polish patterns if `LANGUAGE=pl`.

## Reproducing results

To reproduce the results, run

```bash
make repro
```

This will output:

```
Best results (good, bad, missed) for Polish from thesis:
Total words processed: 45265
 <_io.TextIOWrapper name='<stderr>' mode='w' encoding='utf-8'>
(118, 17, 29)
Results from original Polish patterns
 <_io.TextIOWrapper name='<stderr>' mode='w' encoding='utf-8'>
(129, 19, 18)
Best results (good, bad, missed) for Ukrainian from thesis:
Total words processed: 43283
 <_io.TextIOWrapper name='<stderr>' mode='w' encoding='utf-8'>
(28014, 2339, 11666)
Results from original Ukrainian patterns
 <_io.TextIOWrapper name='<stderr>' mode='w' encoding='utf-8'>
(34421, 5145, 5259)
```

## Citation

```bibtex
@mastersthesis{sojka2024transfer,
    title={Transfer Learning of Slavic Syllabification},
    author={Sojka, Ondřej},
    year={2024},
    school={Masaryk University},
    orcid={0000-0003-2048-9977},
    type={Bachelor's Thesis}
}
```

## License

MIT

## Author

Ondřej Sojka ([@tensojka](https://github.com/tensojka))