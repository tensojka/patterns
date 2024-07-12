use std::env;
use std::fs::{self, File};
use std::io::{self, BufRead, BufReader, Write};
use std::path::Path;
use std::process::{Command, Stdio};
use rayon::prelude::*;
use serde_json;
use crate::transform_hyphens::{calculate_jaro_like_score, transform};
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::{RwLock, Mutex, Arc};
use std::collections::HashMap;
use std::io::ErrorKind;
use translit::{Transliterator, gost779b_ua};
use std::time::{Duration, Instant};
use std::thread;

mod transform_hyphens;

static WORD_COUNT: AtomicUsize = AtomicUsize::new(0);
static TIE_COUNT: AtomicUsize = AtomicUsize::new(0);

const BATCH_SIZE: usize = 50;
const CACHE_INTERVAL: Duration = Duration::from_secs(300); // Save cache every 5 minutes

fn get_language(filename: &str) -> &'static str {
    let lowercase_filename = filename.to_lowercase();
    if lowercase_filename.contains("pl") {
        "zlw/pl"
    } else if lowercase_filename.contains("cs") {
        "zlw/cs"
    } else if lowercase_filename.contains("sk") {
        "zlw/sk"
    } else if lowercase_filename.contains("uk") {
        "zle/uk"
    } else if lowercase_filename.contains("sl") {
        "zls/sl"
    } else {
        println!("defaulting to cs lang, no match!");
        "zlw/cs"
    }
}

fn transliterate_ukrainian(input: &str) -> String {
    let tr = Transliterator::new(gost779b_ua());
    input.chars().flat_map(|c| {
        if c == '-' {
            vec![c]
        } else {
            tr.convert(&c.to_string(), false).chars().collect::<Vec<char>>()
        }
    }).collect()
}

fn create_espeak_tiebreaker(language: String) -> impl Fn(&[String], &str) -> String {
    move |candidates: &[String], original_hyphenated: &str| {
        let original_ipa_parts: Vec<String> = original_hyphenated.split('-')
            .map(|part| get_espeak_ipa(part, &language))
            .collect();

        candidates.iter()
            .map(|candidate| {
                let candidate_parts: Vec<&str> = candidate.split('-').collect();
                let score = original_ipa_parts.iter().zip(candidate_parts.iter())
                    .map(|(orig_ipa, cand)| calculate_jaro_like_score(orig_ipa, cand))
                    .sum::<u32>();
                (candidate, score)
            })
            .max_by_key(|&(_, score)| score)
            .map(|(candidate, _)| candidate.to_string())
            .unwrap_or_else(|| candidates[0].clone())
    }
}

fn get_espeak_ipa(word: &str, language: &str) -> String {
    let output = Command::new("espeak-ng")
        .args(&["-v", language, "--ipa", word])
        .output()
        .expect("Failed to execute espeak-ng");

    String::from_utf8_lossy(&output.stdout).trim().to_string()
}

fn process_word_batch(words: &[String], language: &str) -> Vec<(String, (String, String))> {
    let stripped_words: Vec<String> = words.iter().map(|w| w.replace("-", "")).collect();
    
    let mut child = Command::new("espeak-ng")
        .args(&["-v", language, "--ipa"])
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::null())  // Suppress stderr
        .spawn()
        .expect("Failed to spawn espeak-ng");

    {
        let stdin = child.stdin.as_mut().expect("Failed to open stdin");
        stripped_words.iter().for_each(|word| {
            writeln!(stdin, "{}", word).expect("Failed to write to stdin");
        });
    }

    let output = child.wait_with_output().expect("Failed to read stdout");
    let ipa_words: Vec<String> = String::from_utf8_lossy(&output.stdout)
        .lines()
        .map(|s| s.to_string())
        .collect();

    let tiebreaker = create_espeak_tiebreaker(language.to_string());

    words.iter().zip(stripped_words.iter().zip(ipa_words.iter()))
        .map(|(hyphenated_word, (stripped_word, ipa_word))| {
            let transliterated_hyphenated = if language == "zle/uk" {
                transliterate_ukrainian(hyphenated_word)
            } else {
                hyphenated_word.to_string()
            };
            let result = transform(&transliterated_hyphenated, ipa_word, &tiebreaker);
            WORD_COUNT.fetch_add(1, Ordering::Relaxed);
            (result, (stripped_word.clone(), ipa_word.clone()))
        })
        .collect()
}

fn main() -> std::io::Result<()> {
    let args: Vec<String> = env::args().collect();
    if args.len() != 3 {
        eprintln!("Usage: {} <input_file> <output_file>", args[0]);
        std::process::exit(1);
    }

    let input_file = &args[1];
    let output_file = &args[2];
    let language = get_language(Path::new(input_file).file_name().unwrap().to_str().unwrap());
    println!("using language: {}", language);

    let words: Vec<String> = BufReader::new(File::open(input_file)?)
        .lines()
        .filter_map(Result::ok)
        .collect();

    println!("Processing words:");
    let out_file = Mutex::new(File::create(output_file)?);
    let ipa_file = Path::new("work").join("ipacache").join(format!("{}.json", language.replace('/', "-")));

    let ipa_map = Arc::new(RwLock::new(load_ipa_cache(&ipa_file)?));

    // Spawn a new thread for periodic cache saving
    let ipa_map_clone = Arc::clone(&ipa_map);
    let ipa_file_clone = ipa_file.clone();
    thread::spawn(move || {
        let mut last_save = Instant::now();
        loop {
            thread::sleep(CACHE_INTERVAL);
            if last_save.elapsed() >= CACHE_INTERVAL {
                if let Err(e) = save_ipa_cache(&ipa_map_clone, &ipa_file_clone) {
                    eprintln!("Error saving IPA cache: {}", e);
                }
                last_save = Instant::now();
            }
        }
    });

    // Create an Arc to share the static WORD_COUNT across threads
    let shared_word_count = Arc::new(&WORD_COUNT);
    let word_count_clone = Arc::clone(&shared_word_count);

    // Spawn a new thread to print the word count every few seconds
    thread::spawn(move || {
        loop {
            thread::sleep(Duration::from_secs(3));
            let count = word_count_clone.load(Ordering::Relaxed);
            print!("\rProcessed {} words", count);
            io::stdout().flush().unwrap();
        }
    });

    words.par_chunks(BATCH_SIZE)
        .try_for_each(|chunk| -> std::io::Result<()> {
            let batch_results = process_word_batch(chunk, language);
            
            // Write transformed words to file
            let mut file_guard = out_file.lock().map_err(|e| {
                std::io::Error::new(ErrorKind::Other, format!("Failed to lock file: {}", e))
            })?;
            for (transformed_word, (stripped_word, ipa_word)) in &batch_results {
                writeln!(file_guard, "{}", transformed_word)?;
                
                // Update IPA map
                if let Ok(mut map_guard) = ipa_map.write() {
                    map_guard.insert(stripped_word.clone(), ipa_word.clone());
                }
            }
            
            Ok(())
        })?;

    let total_words = WORD_COUNT.load(Ordering::Relaxed);
    let tied_words = TIE_COUNT.load(Ordering::Relaxed);
    let processed_words = total_words - tied_words;

    println!("\nProcessing complete:");
    println!("Total words: {}", total_words);
    println!("Processed words: {}", processed_words);
    println!("Tied words (skipped): {}", tied_words);
    println!("Tie percentage: {:.2}%", (tied_words as f64 / total_words as f64) * 100.0);

    // Final cache save
    save_ipa_cache(&ipa_map, &ipa_file)?;

    Ok(())
}

fn load_ipa_cache(ipa_file: &Path) -> std::io::Result<HashMap<String, String>> {
    if ipa_file.exists() {
        let json = fs::read_to_string(ipa_file)?;
        Ok(serde_json::from_str(&json).unwrap_or_else(|_| HashMap::new()))
    } else {
        Ok(HashMap::new())
    }
}

fn save_ipa_cache(ipa_map: &RwLock<HashMap<String, String>>, ipa_file: &Path) -> std::io::Result<()> {
    if let Ok(map_guard) = ipa_map.read() {
        let json = serde_json::to_string(&*map_guard)?;
        fs::write(ipa_file, json)?;
        println!("\nSaved IPA cache to {:?}", ipa_file);
    }
    Ok(())
}