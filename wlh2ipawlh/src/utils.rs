use std::process::{Command, Stdio};
use std::io::{Read, Write};
use triple_accel::levenshtein::levenshtein_simd_k_str;

pub fn get_language(filename: &str) -> &'static str {
    let lowercase_filename = filename.to_lowercase();
    if lowercase_filename.contains("pl") {
        "zlw/pl"
    } else if lowercase_filename.contains("cs") {
        "zlw/cs"
    } else if lowercase_filename.contains("sk") {
        "zlw/sk"
    } else if lowercase_filename.contains("uk") {
        "zle/uk"
    } else if lowercase_filename.contains("ru") {
        "zle/ru"
    } else if lowercase_filename.contains("sl") {
        "zls/sl"
    } else if lowercase_filename.contains("sh"){
        "zls/hr"
    } else {
        println!("defaulting to cs lang, no match!");
        "zlw/cs"
    }
}

pub fn get_espeak_ipa_batch(words: &[String], language: &str) -> Vec<String> {
    let input = words.join("\n");
    let mut child = Command::new("espeak-ng")
        .args(&["-v", language, "--ipa", "-q"])
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .spawn()
        .expect("Failed to spawn espeak-ng");

    {
        let mut stdin = child.stdin.take().expect("Failed to open stdin");
        stdin.write_all(input.as_bytes()).expect("Failed to write to stdin");
    }

    let mut output = String::new();
    child.stdout.take().expect("Failed to open stdout")
        .read_to_string(&mut output)
        .expect("Failed to read from stdout");

    child.wait().expect("Failed to wait on child");

    output.trim()
        .split('\n')
        .map(|s| {
            let trimmed = s.trim();
            if trimmed.is_empty() {
                println!("Warning: Empty IPA generated for a word");
                String::from("?") // Placeholder for empty IPA
            } else {
                trimmed.replace("ˈ", "").to_string()
            }
        })
        .collect()
}


pub fn get_best_levenshtein(candidates: &[String], target: &str) -> Vec<String> {
    let mut best_levenshtein_distance = usize::MAX;
    let mut best_levenshtein_candidates: Vec<String> = Vec::new();

    for candidate in candidates {
        if let Some(distance) = levenshtein_simd_k_str(target, candidate, best_levenshtein_distance as u32) {
            if distance < best_levenshtein_distance as u32 {
                best_levenshtein_distance = distance as usize;
                best_levenshtein_candidates = vec![candidate.clone()];
            } else if distance == best_levenshtein_distance as u32 {
                best_levenshtein_candidates.push(candidate.clone());
            }
        }
    }

    best_levenshtein_candidates
}
