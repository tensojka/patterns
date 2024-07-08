//use rapidfuzz::distance::indel::{distance_with_args, Args};
use triple_accel::levenshtein::levenshtein_simd_k_str;
use phf::phf_map;
use itertools::Itertools;
use std::collections::HashMap;

static IPA_ASCII_TABLE: phf::Map<char, char> = phf_map! {
    'ɡ' => 'g',
    'ʃ' => 's',
    'ʊ' => 'u',
    'ɔ' => 'o',
    'ɲ' => 'n',
    'ɨ' => 'i',
    'ʒ' => 'z',
    'ɛ' => 'e',
    // Add more IPA to ASCII mappings as needed
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
    //println!("Possible positions: {:?}", possible_positions.len());
    let mut best_distance = hyphenated.len() as u32;
    let mut best_candidate = String::new();

    let ascii_hyphenated = ipa_to_ascii(hyphenated);

    for hyphen_positions in possible_positions.into_iter().combinations(num_hyphens) {
        if hyphen_positions.first() == Some(&0) || hyphen_positions.last() == Some(&(target.len() - 1)) {
            continue;
        }

        let candidate = insert_hyphens(target, &hyphen_positions);
        let ascii_candidate = ipa_to_ascii(&candidate);
        if let Some(distance) = levenshtein_simd_k_str(&ascii_hyphenated, &ascii_candidate, best_distance) {
            if distance < best_distance {
                best_distance = distance;
                best_candidate = candidate;
            } else if distance == best_distance && distance == 9 {
                //println!("Current distance: {}", distance);
                //println!("Found tied best candidates:");
                //println!("Previous: {}", best_candidate);
                //println!("New: {}", candidate);
            }
        }
    }
    //println!("Best distance: {}", best_distance);
    if best_candidate.is_empty() { target.to_string() } else { best_candidate }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_transform() {
        let test_cases = vec![
            //("abc-d-ef", "axbxcdxef"),
            //("ne-boj-sa", "nebojsa"),
            //("pret-hod-ny", "predhodny"),
            //("roz-šou-stat", "rˈosʃoʊstat"),
            //("ne-roz-hod-nost", "nˈeroshˌodnost"),
            ("za-chod-nio-eu-ro-pej-skich", "zˌaxɔdɲʲˌɔɛwrɔpˈɛjskix"),
            //("przy-rod-ni-czo--hu-ma-ni-stycz-ne-go", "pʃˌɨrɔdɲˌitʃɔxˌumaɲˌistɨtʃnˈɛɡɔ"),
        ];

        for (hyphenated, target) in test_cases {
            let result = transform(hyphenated, target);
            println!("Input: {} -> {}", hyphenated, target);
            println!("Output: {}\n", result);
        }
    }
}
