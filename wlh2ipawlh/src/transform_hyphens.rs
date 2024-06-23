use strsim::levenshtein;
use rayon::prelude::*;
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
    
    possible_positions.into_iter()
        .combinations(num_hyphens)
        .par_bridge()
        .filter(|hyphen_positions| {
            hyphen_positions.first() != Some(&0) && hyphen_positions.last() != Some(&(target.len() - 1))
        })
        .map(|hyphen_positions| {
            let candidate = insert_hyphens(target, &hyphen_positions);
            let current_distance = levenshtein(hyphenated, &candidate);
            (candidate, current_distance)
        })
        .reduce(
            || (String::new(), usize::MAX),
            |(best_result, min_distance), (candidate, current_distance)| {
                if current_distance < min_distance {
                    (candidate, current_distance)
                } else {
                    (best_result, min_distance)
                }
            }
        )
        .0
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
