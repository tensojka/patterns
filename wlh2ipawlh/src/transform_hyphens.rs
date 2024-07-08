use triple_accel::levenshtein::levenshtein_simd_k_str;
use itertools::Itertools;

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
    let mut best_distance = hyphenated.len() as u32;
    let mut best_candidate = String::new();

    for hyphen_positions in possible_positions.into_iter().combinations(num_hyphens) {
        if hyphen_positions.first() == Some(&0) || hyphen_positions.last() == Some(&(target.len() - 1)) {
            continue;
        }

        let candidate = insert_hyphens(target, &hyphen_positions);
        if let Some(distance) = levenshtein_simd_k_str(hyphenated, &candidate, best_distance) {
            if distance < best_distance {
                best_distance = distance;
                best_candidate = candidate;
            }
        }
    }

    if best_candidate.is_empty() { target.to_string() } else { best_candidate }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_transform() {
        let test_cases = vec![
            ("abc-d-ef", "axbxcdxef"),
            ("ne-boj-sa", "nebojsa"),
            ("pret-hod-ny", "predhodny"),
            ("roz-šou-stat", "rˈosʃoʊstat"),
            ("ne-roz-hod-nost", "nˈeroshˌodnost"),
        ];

        for (hyphenated, target) in test_cases {
            let result = transform(hyphenated, target);
            println!("Input: {} -> {}", hyphenated, target);
            println!("Output: {}\n", result);
        }
    }
}
