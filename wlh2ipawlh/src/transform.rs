use crate::utils::count_hyphens;

// Mapping from IPA characters to ASCII characters to simplify similarity computations
fn ipa_to_ascii(c: char) -> char {
    match c {
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
        'ɑ' => 'a',  // Map 'ɑ' to 'a'
        _ => c,
    }
}

// Function to simplify a string using the ipa_to_ascii mapping
fn simplify(s: &str) -> Vec<char> {
    s.chars().map(ipa_to_ascii).collect()
}

fn align_sequences(seq1: &[char], seq2: &[char]) -> (Vec<Option<usize>>, Vec<Option<usize>>) {
    let m = seq1.len();
    let n = seq2.len();
    let match_score = 1;
    let mismatch_penalty = -1;
    let gap_penalty = -1;

    // Initialize scoring matrix and traceback matrix
    let mut score_matrix = vec![vec![0; n + 1]; m + 1];
    let mut traceback = vec![vec![(0, 0); n + 1]; m + 1];

    // Initialize first column of traceback
    for i in 1..=m {
        score_matrix[i][0] = gap_penalty * i as i32;
        traceback[i][0] = (i - 1, 0);
    }

    // Initialize first row of traceback
    for j in 1..=n {
        score_matrix[0][j] = gap_penalty * j as i32;
        traceback[0][j] = (0, j - 1);
    }

    // Fill in the rest of the matrix
    for i in 1..=m {
        for j in 1..=n {
            let is_hyphen = seq1[i - 1] == '-';

            let match_mismatch = if is_hyphen {
                std::i32::MIN / 2 // Large negative number to prevent matching hyphen with any character
            } else if seq1[i - 1] == seq2[j - 1] {
                score_matrix[i - 1][j - 1] + match_score
            } else {
                score_matrix[i - 1][j - 1] + mismatch_penalty
            };

            let delete_penalty = if is_hyphen { 0 } else { gap_penalty };
            let delete = score_matrix[i - 1][j] + delete_penalty;

            let insert = score_matrix[i][j - 1] + gap_penalty;

            let max_score = match_mismatch.max(delete).max(insert);
            score_matrix[i][j] = max_score;

            // Traceback pointers
            traceback[i][j] = if max_score == match_mismatch {
                (i - 1, j - 1)
            } else if max_score == delete {
                (i - 1, j)
            } else {
                (i, j - 1)
            };
        }
    }

    // Traceback to get the alignment
    let mut align1 = Vec::new();
    let mut align2 = Vec::new();
    let mut i = m;
    let mut j = n;

    while i > 0 || j > 0 {
        if i == 0 && j == 0 {
            break;
        }

        let (prev_i, prev_j) = traceback[i][j];

        if i > prev_i && j > prev_j {
            // Diagonal move
            align1.push(Some(i - 1));
            align2.push(Some(j - 1));
        } else if i > prev_i {
            // Up move (gap in seq2)
            align1.push(Some(i - 1));
            align2.push(None);
        } else if j > prev_j {
            // Left move (gap in seq1)
            align1.push(None);
            align2.push(Some(j - 1));
        } else {
            // Should not happen
            break;
        }

        i = prev_i;
        j = prev_j;
    }

    align1.reverse();
    align2.reverse();

    (align1, align2)
}


// Function to transfer hyphens between two strings
fn transfer_hyphens(hyphenated: &str, non_hyphenated: &str) -> String {
    let simplified_hyphenated: Vec<char> = simplify(hyphenated);
    let simplified_non_hyphenated: Vec<char> = simplify(non_hyphenated);

    let (align_hyph_indices, align_non_hyph_indices) =
        align_sequences(&simplified_hyphenated, &simplified_non_hyphenated);

    let seq1 = hyphenated.chars().collect::<Vec<char>>();
    let seq2 = non_hyphenated.chars().collect::<Vec<char>>();

    let mut result_chars = Vec::new();
    for k in 0..align_hyph_indices.len() {
        if let Some(i) = align_hyph_indices[k] {
            if seq1[i] == '-' {
                // Hyphen in seq1, insert hyphen into result
                result_chars.push('-');
            } else if let Some(j) = align_non_hyph_indices[k] {
                // Both seq1 and seq2 have characters, append seq2[j]
                result_chars.push(seq2[j]);
            } else {
                // seq1 has character, seq2 has gap
                // Should not happen with adjusted scoring
            }
        } else if let Some(j) = align_non_hyph_indices[k] {
            // Gap in seq1, character in seq2
            result_chars.push(seq2[j]);
        } else {
            // Both seq1 and seq2 have gaps
            // Should not happen
        }
    }

    result_chars.iter().collect()
}

pub fn transform(original: &str, ipa: &str) -> String {
    if original.contains('-') {
        let res = transfer_hyphens(original, ipa);
        assert_eq!(count_hyphens(original), count_hyphens(res.as_str()));
        res
    } else {
        transfer_hyphens(ipa, original)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_transfer_hyphens() {
        assert_eq!(transfer_hyphens("укра-ї-на", "ukrɑina"), "ukrɑ-i-na");
        assert_eq!(transfer_hyphens("укра-ї-ни", "ukrɑini"), "ukrɑ-i-ni");
        assert_eq!(transfer_hyphens("ukra-yin-s`ke", "ukrɑinski"), "ukrɑ-in-ski");
        assert_eq!(transfer_hyphens("ukra-yi-ni", "ukrɑini"), "ukrɑ-i-ni");
        assert_eq!(transfer_hyphens("ukra-yi-nu", "ukrɑinu"), "ukrɑ-i-nu");
    }
}