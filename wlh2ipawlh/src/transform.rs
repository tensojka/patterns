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

// Function to transfer hyphens between two strings
fn transfer_hyphens(hyphenated: &str, non_hyphenated: &str) -> String {
    let hyphenated_no_hyphens = hyphenated.replace('-', "");
    let simplified_hyphenated: Vec<char> = simplify(&hyphenated_no_hyphens);
    let simplified_non_hyphenated: Vec<char> = simplify(non_hyphenated);

    let (align_hyph_indices, align_non_hyph_indices) =
        align_sequences(&simplified_hyphenated, &simplified_non_hyphenated);

    let mut hyphen_positions = Vec::new();
    let mut hyph_index = -1_isize; // Start from -1
    for c in hyphenated.chars() {
        if c != '-' {
            hyph_index += 1;
        } else {
            hyphen_positions.push(hyph_index as usize);
        }
    }

    let mut result_chars: Vec<char> = non_hyphenated.chars().collect();
    let mut insert_positions = Vec::new();

    for hyphen_pos in hyphen_positions {
        for (hyph_opt, non_hyph_opt) in align_hyph_indices.iter().zip(align_non_hyph_indices.iter()) {
            if let Some(hyph_i) = hyph_opt {
                if *hyph_i == hyphen_pos {
                    if let Some(non_hyph_i) = non_hyph_opt {
                        insert_positions.push(non_hyph_i + 1);
                        break;
                    }
                }
            }
        }
    }

    // Insert hyphens into the result
    insert_positions.sort_unstable();
    let mut offset = 0;
    for pos in insert_positions {
        if pos + offset < result_chars.len() {
            result_chars.insert(pos + offset, '-');
            offset += 1;
        } else {
            result_chars.push('-');
        }
    }

    result_chars.iter().collect()
}

pub fn transform(original: &str, ipa: &str) -> String {
    if original.contains('-') {
        transfer_hyphens(original, ipa)
    } else {
        transfer_hyphens(ipa, original)
    }
}
