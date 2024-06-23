use itertools::Itertools;
use strsim::levenshtein;

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
    let origin = hyphenated.replace("-", "");
    let num_hyphens = get_hyphen_points(hyphenated).len();
    
    let possible_positions: Vec<usize> = (1..target.len()).collect();
    let mut best_result = String::new();
    let mut min_distance = usize::MAX;

    for hyphen_positions in possible_positions.into_iter().combinations(num_hyphens) {
        // Skip if any hyphen position is at the start or end of the word
        if hyphen_positions.first() == Some(&0) || hyphen_positions.last() == Some(&(target.len() - 1)) {
            continue;
        }

        let candidate = insert_hyphens(target, &hyphen_positions);
        let current_distance = levenshtein(hyphenated, &candidate);
        
        if current_distance < min_distance {
            min_distance = current_distance;
            best_result = candidate;
        }
    }

    best_result
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
