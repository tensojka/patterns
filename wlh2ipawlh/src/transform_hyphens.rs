//use rapidfuzz::distance::indel::{distance_with_args, Args};
use triple_accel::levenshtein::levenshtein_simd_k_str;
use phf::phf_map;
use itertools::Itertools;
use std::collections::{HashSet};
use rayon::prelude::*;

// Also contains mappings from various characters to ASCII, to ease similarity computations
static IPA_ASCII_TABLE: phf::Map<char, char> = phf_map! {
    'ɡ' => 'g',
    'ʃ' => 's',
    'ʊ' => 'u',
    'ɔ' => 'o',
    'ɲ' => 'n',
    'ɨ' => 'i',
    'ʒ' => 'z',
    'ɛ' => 'e',
    'š' => 's',
};

fn ipa_to_ascii(s: &str) -> String {
    s.chars().map(|c| *IPA_ASCII_TABLE.get(&c).unwrap_or(&c)).collect()
}

fn get_hyphen_points(hyphenated: &str) -> Vec<usize> {
    hyphenated.char_indices()
        .filter_map(|(i, c)| if c == '-' { Some(i) } else { None })
        .collect()
}

fn insert_hyphens(word: &str, positions: &[usize]) -> String {
    let mut result: Vec<char> = word.chars().collect();
    let mut offset = 0;
    for &pos in positions.iter() {
        if pos + offset <= result.len() {
            result.insert(pos + offset, '-');
            offset += 1;
        }
    }
    result.into_iter().collect()
}

pub fn transform(hyphenated: &str, target: &str) -> String {
    let num_hyphens = get_hyphen_points(hyphenated).len();
    let possible_positions: Vec<usize> = (1..target.len()).collect();
    let ascii_hyphenated = ipa_to_ascii(hyphenated);

    // Generate all combinations first
    let combinations: Vec<Vec<usize>> = possible_positions.into_iter()
        .combinations(num_hyphens)
        .filter(|hyphen_positions| {
            hyphen_positions.first() != Some(&0) && hyphen_positions.last() != Some(&(target.len() - 1))
        })
        .collect();

    // First pass: Calculate Jaro-like scores in parallel
    let candidates: Vec<(String, u32)> = combinations.par_iter()
        .map(|hyphen_positions| {
            let candidate = insert_hyphens(target, hyphen_positions);
            let ascii_candidate = ipa_to_ascii(&candidate);
            let jaro_score = calculate_jaro_like_score(&ascii_hyphenated, &ascii_candidate);
            (candidate, jaro_score)
        })
        .collect();

    let best_jaro_score = candidates.par_iter().map(|(_, score)| *score).max().unwrap_or(0);
    let best_candidates: Vec<String> = candidates.into_iter()
        .filter(|(_, score)| *score == best_jaro_score)
        .map(|(candidate, _)| candidate)
        .collect();

    println!("Second pass: Calculate Levenshtein distance only for best Jaro candidates");
    let mut best_levenshtein_distance = usize::MAX;
    let mut best_levenshtein_candidates: Vec<String> = Vec::new();

    for candidate in best_candidates {
        let ascii_candidate = ipa_to_ascii(&candidate);
        if let Some(distance) = levenshtein_simd_k_str(&ascii_hyphenated, &ascii_candidate, best_levenshtein_distance as u32) {
            if distance < best_levenshtein_distance as u32 {
                best_levenshtein_distance = distance as usize;
                best_levenshtein_candidates = vec![candidate];
            } else if distance == best_levenshtein_distance as u32 {
                best_levenshtein_candidates.push(candidate);
            }
        }
    }

    if best_levenshtein_candidates.len() > 1 {
        println!("Resolving tie between {} candidates:", best_levenshtein_candidates.len());
        for candidate in &best_levenshtein_candidates {
            println!("  {}", candidate);
        }
        let best_candidate = resolve_tie(&ascii_hyphenated, &best_levenshtein_candidates);
        println!("Selected: {}", best_candidate);
        best_candidate
    } else if let Some(best_candidate) = best_levenshtein_candidates.first() {
        best_candidate.clone()
    } else {
        target.to_string()
    }
}

fn resolve_tie(hyphenated: &str, candidates: &[String]) -> String {
    candidates
        .iter()
        .max_by_key(|candidate| calculate_jaro_like_score(hyphenated, candidate))
        .unwrap_or(&candidates[0])
        .clone()
}

fn calculate_jaro_like_score(hyphenated: &str, candidate: &str) -> u32 {
    let hyphenated_points = get_hyphen_points(hyphenated);
    let candidate_points = get_hyphen_points(candidate);
    
    hyphenated_points.iter().zip(candidate_points.iter())
        .map(|(&h_pos, &c_pos)| {
            let left_score = score_substring(&hyphenated[..h_pos], &candidate[..c_pos]);
            let right_score = score_substring(&hyphenated[h_pos+1..], &candidate[c_pos+1..]);
            left_score + right_score
        })
        .sum()
}

fn score_substring(hyphenated_part: &str, candidate_part: &str) -> u32 {
    let candidate_chars: HashSet<char> = candidate_part.chars().collect();
    hyphenated_part.chars().filter(|&c| candidate_chars.contains(&c)).count() as u32
}

#[cfg(test)]
mod tests {
    use super::*;

    fn get_test_cases() -> Vec<(&'static str, &'static str)> {
        vec![
            //("abc-d-ef", "axbxcdxef"),
            ("ne-boj-sa", "nebojsa"),
            ("pret-hod-ny", "predhodny"),
            ("roz-šou-stat", "rˈosʃoʊstat"),
            ("ju-ni-pe-rus", "jˌuɲipˈɛrus"),
            ("ne-roz-hod-nost", "nˈeroshˌodnost"),
            ("za-chod-nio-eu-ro-pej-skich", "zˌaxɔdɲˌɔɛwrɔpˈɛjskix"),
            ("przy-rod-ni-czo-hu-ma-ni-stycz-ne-go", "pʃˌɨrɔdɲˌitʃɔxˌumaɲˌistɨtʃnˈɛɡɔ"),
        ]
    }

    #[test]
    fn test_transform() {
        for (hyphenated, target) in get_test_cases() {
            let result = transform(hyphenated, target);
            println!("Input: {} -> {}", hyphenated, target);
            println!("Output: {}\n", result);
        }
    }

    //#[test]
    fn test_jaro_like_score() {
        for (hyphenated, target) in get_test_cases() {
            let num_hyphens = get_hyphen_points(hyphenated).len();
            let possible_positions: Vec<usize> = (1..target.len()).collect();
            let mut max_score = 0;
            let mut best_candidates = Vec::new();
            
            for hyphen_positions in possible_positions.into_iter().combinations(num_hyphens) {
                let ascii_hyphenated = ipa_to_ascii(hyphenated);
                let candidate = insert_hyphens(target, &hyphen_positions);
                let ascii_candidate = ipa_to_ascii(&candidate);
                let score = calculate_jaro_like_score(&ascii_hyphenated, &ascii_candidate);
                
                if score > max_score {
                    max_score = score;
                    best_candidates.clear();
                    best_candidates.push(candidate);
                } else if score == max_score {
                    best_candidates.push(candidate);
                }
            }
            
            println!("Input: {} -> {}", hyphenated, target);
            println!("Best score: {}", max_score);
            println!("Best candidates:");
            best_candidates.iter().for_each(|candidate| println!("  {}", candidate));
            println!();
        }
    }
}
