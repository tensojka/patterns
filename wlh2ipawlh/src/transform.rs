use phf::phf_map;
use itertools::Itertools;
use std::collections::HashSet;
use rayon::prelude::*;
use crate::utils::get_best_levenshtein;

// Also contains mappings from various characters to ASCII, to ease similarity computations
static IPA_ASCII_TABLE: phf::Map<char, char> = phf_map! {
    'ɡ' => 'g',
    'ʃ' => 's',
    'ʊ' => 'u',
    'ɔ' => 'o',
    'ɲ' => 'n',
    'ŋ' => 'n',
    'ɨ' => 'i',
    'ʒ' => 'z',
    'ɛ' => 'e',
    'š' => 's',
    'á' => 'a',
    'é' => 'e',
    'í' => 'i',
    'ó' => 'o',
    'ý' => 'i',
};

fn ipa_to_ascii(s: &str) -> String {
    s.chars().map(|c| *IPA_ASCII_TABLE.get(&c).unwrap_or(&c)).collect()
}

fn get_hyphen_points(hyphenated: &str) -> Vec<usize> {
    hyphenated.char_indices()
        .filter_map(|(i, c)| if c == '-' { Some(i) } else { None })
        .collect()
}

pub(crate) fn insert_hyphens(word: &str, positions: &[usize]) -> String {
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

pub fn transform<F>(hyphenated: &str, target: &str, tiebreaker: F) -> String
where
    F: Fn(&[String], &str) -> String
{
    let num_hyphens = get_hyphen_points(hyphenated).len();
    let ascii_hyphenated = ipa_to_ascii(hyphenated);

    // Generate combinations on-the-fly instead of storing them all
    let combinations = (1..target.len()).combinations(num_hyphens)
        .filter(|hyphen_positions| {
            hyphen_positions.first() != Some(&0) && hyphen_positions.last() != Some(&(target.len() - 1))
        });

    // Use an iterator to avoid storing all candidates in memory
    let mut best_jaro_score = 0;
    let mut best_candidates = Vec::new();

    for hyphen_positions in combinations {
        let candidate = insert_hyphens(target, &hyphen_positions);
        let ascii_candidate = ipa_to_ascii(&candidate);
        let jaro_score = calculate_jaro_like_score(&ascii_hyphenated, &ascii_candidate);

        if jaro_score > best_jaro_score {
            best_jaro_score = jaro_score;
            best_candidates.clear();
            best_candidates.push(candidate);
        } else if jaro_score == best_jaro_score {
            best_candidates.push(candidate);
        }
    }

    let ascii_candidates: Vec<String> = best_candidates.iter()
        .map(|candidate| ipa_to_ascii(candidate))
        .collect();

    let best_levenshtein_candidates = get_best_levenshtein(&ascii_candidates, &ascii_hyphenated);

    if best_levenshtein_candidates.len() > 1 {
        tiebreaker(&best_levenshtein_candidates, hyphenated)
    } else if let Some(best_candidate) = best_levenshtein_candidates.first() {
        best_candidate.clone()
    } else {
        println!("No valid candidates found. Hyphenated: {}, Target: {}", hyphenated, target);
        String::new()
    }
}


pub fn calculate_jaro_like_score(hyphenated: &str, candidate: &str) -> u32 {
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
            ("gra-phics", "ɡrˈafiks"),
            ("pret-hod-ny", "predhodny"),
            ("roz-šou-stat", "rˈosʃoʊstat"),
            ("ju-ni-pe-rus", "jˌuɲipˈɛrus"),
            ("sek-cja", "sˈɛktsja"), // TODO: pokud je remiza, rozdelit puvodni slabiky 
            ("ne-roz-hod-nost", "nˈeroshˌodnost"),
            ("za-chod-nio-eu-ro-pej-skich", "zˌaxɔdɲˌɔɛwrɔpˈɛjskix"),
            ("przy-rod-ni-czo-hu-ma-ni-stycz-ne-go", "pʃˌɨrɔdɲˌitʃɔxˌumaɲˌistɨtʃnˈɛɡɔ"),
        ]
    }

    #[test]
    fn test_transform() {
        for (hyphenated, target) in get_test_cases() {
            let result = transform(hyphenated, target, |candidates, _| candidates[0].clone());
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