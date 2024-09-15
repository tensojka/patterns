use std::collections::HashMap;

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
        _ => c,
    }
}

// Function to remove hyphens from a word
fn remove_hyphens(s: &str) -> String {
    s.replace('-', "")
}

// Function to simplify a string using the IPA_ASCII_TABLE mapping
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

    // Fill in the first row and column
    for i in 0..=m {
        score_matrix[i][0] = gap_penalty * i as i32;
    }
    for j in 0..=n {
        score_matrix[0][j] = gap_penalty * j as i32;
    }

    // Fill in the rest of the matrix
    for i in 1..=m {
        for j in 1..=n {
            let match_mismatch = if seq1[i - 1] == seq2[j - 1] {
                score_matrix[i - 1][j - 1] + match_score
            } else {
                score_matrix[i - 1][j - 1] + mismatch_penalty
            };
            let delete = score_matrix[i - 1][j] + gap_penalty;
            let insert = score_matrix[i][j - 1] + gap_penalty;

            let max_score = match_mismatch.max(delete).max(insert);
            score_matrix[i][j] = max_score;

            // Traceback pointers
            if max_score == match_mismatch {
                traceback[i][j] = (i - 1, j - 1);
            } else if max_score == delete {
                traceback[i][j] = (i - 1, j);
            } else {
                traceback[i][j] = (i, j - 1);
            }
        }
    }

    // Traceback to get the alignment
    let mut align1 = Vec::new();
    let mut align2 = Vec::new();
    let mut i = m;
    let mut j = n;

    while i > 0 || j > 0 {
        let (prev_i, prev_j) = traceback[i][j];
        if i > 0 && j > 0 && traceback[i][j] == (i - 1, j - 1) {
            align1.push(Some(i - 1));
            align2.push(Some(j - 1));
        } else if i > 0 && traceback[i][j] == (i - 1, j) {
            align1.push(Some(i - 1));
            align2.push(None);
        } else {
            align1.push(None);
            align2.push(Some(j - 1));
        }
        i = prev_i;
        j = prev_j;
    }

    align1.reverse();
    align2.reverse();

    (align1, align2)
}

// Function to transfer hyphens from the original word to the IPA transcription
fn transfer_hyphens(original: &str, ipa: &str) -> String {
    let original_no_hyphens = original.replace('-', "");
    let simplified_original: Vec<char> = original_no_hyphens.chars().map(ipa_to_ascii).collect();
    let simplified_ipa: Vec<char> = ipa.chars().map(ipa_to_ascii).collect();

    let (align_orig_indices, align_ipa_indices) =
        align_sequences(&simplified_original, &simplified_ipa);

    let mut hyphen_positions = Vec::new();
    let mut orig_index = -1_isize; // Start from -1
    for c in original.chars() {
        if c != '-' {
            orig_index += 1;
        } else {
            hyphen_positions.push(orig_index as usize);
        }
    }

    let mut ipa_chars: Vec<char> = ipa.chars().collect();
    let mut insert_positions = Vec::new();

    for hyphen_pos in hyphen_positions {
        for (orig_opt, ipa_opt) in align_orig_indices.iter().zip(align_ipa_indices.iter()) {
            if let Some(orig_i) = orig_opt {
                if *orig_i == hyphen_pos {
                    if let Some(ipa_i) = ipa_opt {
                        insert_positions.push(ipa_i + 1);
                        break;
                    }
                }
            }
        }
    }

    // Insert hyphens into the IPA transcription
    insert_positions.sort_unstable();
    let mut offset = 0;
    for pos in insert_positions {
        if pos + offset < ipa_chars.len() {
            ipa_chars.insert(pos + offset, '-');
            offset += 1;
        } else {
            ipa_chars.push('-');
        }
    }

    ipa_chars.iter().collect()
}



fn main() {
    let test_cases = vec![
        ("ne-boj-sa", "nebojsa", "ne-boj-sa"),
        ("gra-phics", "ɡrˈafiks", "ɡrˈa-fiks"),
        ("pret-hod-ny", "predhodny", "pred-hod-ny"),
        ("roz-šou-stat", "rˈosʃoʊstat", "rˈos-ʃoʊ-stat"),
        ("ju-ni-pe-rus", "jˌuɲipˈɛrus", "jˌu-ɲi-pˈɛ-rus"),
        ("sek-cja", "sˈɛktsja", "sˈɛk-tsja"),
        ("ne-roz-hod-nost", "nˈeroshˌodnost", "nˈe-ros-hˌod-nost"),
        (
            "za-chod-nio-eu-ro-pej-skich",
            "zˌaxɔdɲˌɔɛwrɔpˈɛjskix",
            "zˌa-xɔd-ɲˌɔ-ɛw-rɔ-pˈɛj-skix",
        ),
        (
            "przy-rod-ni-czo-hu-ma-ni-stycz-ne-go",
            "pʃˌɨrɔdɲˌitʃɔxˌumaɲˌistɨtʃnˈɛɡɔ",
            "pʃˌɨ-rɔd-ɲˌi-tʃɔ-xˌu-ma-ɲˌi-stɨtʃ-nˈɛ-ɡɔ",
        ),
    ];

    for (original, ipa, expected) in test_cases {
        let result = transfer_hyphens(original, ipa);
        if result == expected {
            println!("PASSED: \"{}\" -> \"{}\"", original, result);
        } else {
            println!(
                "FAILED: \"{}\" -> \"{}\" (expected \"{}\")",
                original, result, expected
            );
        }
    }
}