use std::env;
use std::fs::{self, File};
use std::io::{self, BufRead, BufReader, Read, Write, BufWriter};
use std::path::Path;
use std::process::{Command, Stdio};
use serde_json;
use transform_hyphens::transform::{calculate_jaro_like_score, transform};
use transform_hyphens::get_language;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::collections::HashMap;
use translit::{Transliterator, gost779b_ua};
use std::time::{Duration, Instant};
use std::thread;
use dashmap::DashMap;
use std::sync::Arc;
use std::sync::Mutex;
use serde::Serialize;
use rayon::prelude::*;
use std::mem;


static WORD_COUNT: AtomicUsize = AtomicUsize::new(0);
static TIE_COUNT: AtomicUsize = AtomicUsize::new(0);

const BATCH_SIZE: usize = 500;
const CACHE_INTERVAL: Duration = Duration::from_secs(300); // Save cache every 5 minutes

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

fn get_espeak_ipa_batch(words: &[String], language: &str) -> Vec<String> {
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
                trimmed.to_string()
            }
        })
        .collect()
}

fn process_word_batch(words: &[String], language: &str, ipa_map: Arc<DashMap<String, String>>) -> Vec<(String, String, String)> {
    let mut results = Vec::with_capacity(words.len());
    let mut words_to_process = Vec::new();

    // First pass: Check cache and collect words that need processing
    for word in words {
        let stripped_word = word.replace("-", "");
        if let Some(ipa) = ipa_map.get(&stripped_word) {
            results.push((word.clone(), stripped_word, ipa.value().clone()));
        } else {
            words_to_process.push((word.clone(), stripped_word));
        }
    }

    // Process words not found in cache
    if !words_to_process.is_empty() {
        let words_to_lookup: Vec<_> = words_to_process.iter().map(|(_, w)| w.clone()).collect();
        let new_ipas = get_espeak_ipa_batch(&words_to_lookup, language);
        for ((original_word, stripped_word), ipa) in words_to_process.into_iter().zip(new_ipas) {
            ipa_map.insert(stripped_word.clone(), ipa.clone());
            results.push((original_word, stripped_word, ipa));
        }
    }

    let tiebreaker = create_espeak_tiebreaker(language.to_string(), Arc::clone(&ipa_map));

    // Process results
    results.into_iter().map(|(hyphenated_word, stripped_word, ipa_word)| {
        let transliterated_hyphenated = if language == "zle/uk" {
            transliterate_ukrainian(&hyphenated_word)
        } else {
            hyphenated_word.clone()
        };
        if ipa_word.is_empty() {
            println!("Warning: Empty IPA for word: {}", hyphenated_word);
            (hyphenated_word, stripped_word, ipa_word)
        } else {
            let result = transform(&transliterated_hyphenated, &ipa_word, &tiebreaker);
            WORD_COUNT.fetch_add(1, Ordering::Relaxed);
            (result, stripped_word, ipa_word)
        }
    }).collect()
}

fn create_espeak_tiebreaker(language: String, ipa_map: Arc<DashMap<String, String>>) -> impl Fn(&[String], &str) -> String {
    move |candidates: &[String], original_hyphenated: &str| {
        let original_parts: Vec<&str> = original_hyphenated.split('-').collect();
        let mut words_to_process = Vec::new();
        let mut original_ipa_parts = Vec::with_capacity(original_parts.len());

        for &part in &original_parts {
            if let Some(ipa) = ipa_map.get(part) {
                original_ipa_parts.push(ipa.clone());
            } else {
                words_to_process.push(part.to_string());
                original_ipa_parts.push(String::new()); // Placeholder for IPA to be filled later
            }
        }

        if !words_to_process.is_empty() {
            let new_ipas = get_espeak_ipa_batch(&words_to_process, &language);
            for (part, ipa) in words_to_process.into_iter().zip(new_ipas) {
                ipa_map.insert(part.clone(), ipa.clone());
                original_ipa_parts[original_parts.iter().position(|&p| p == part).unwrap()] = ipa;
            }
        }

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
    let out_file = Arc::new(Mutex::new(File::create(output_file)?));
    let ipa_file = Path::new("work").join("ipacache").join(format!("{}.json", language.replace('/', "-")));

    let ipa_map = Arc::new(DashMap::new());
    if ipa_file.exists() {
        let json = fs::read_to_string(&ipa_file)?;
        let loaded_map: HashMap<String, String> = serde_json::from_str(&json).unwrap_or_else(|_| HashMap::new());
        for (key, value) in loaded_map {
            ipa_map.insert(key, value);
        }
    }

    // Spawn a new thread for periodic cache saving
    let ipa_map_clone = Arc::clone(&ipa_map);
    let ipa_file_clone = ipa_file.clone();
    thread::spawn(move || {
        let mut last_save = Instant::now();
        loop {
            thread::sleep(Duration::from_secs(60)); // Check every minute
            if last_save.elapsed() >= CACHE_INTERVAL {
                if let Err(e) = save_ipa_cache(&ipa_map_clone, &ipa_file_clone) {
                    eprintln!("Error saving IPA cache: {}", e);
                }
                last_save = Instant::now();
                
                // Shrink the DashMap to release unused memory
                ipa_map_clone.shrink_to_fit();
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

    // Process all words in batches using parallel iteration
    words.par_chunks(BATCH_SIZE).for_each(|chunk| {
        let batch_results = process_word_batch(chunk, language, Arc::clone(&ipa_map));
        
        // Write transformed words to file
        let mut file_guard = out_file.lock().unwrap();
        for (transformed_word, stripped_word, ipa_word) in batch_results {
            writeln!(file_guard, "{}", transformed_word).unwrap();
            
            // Update IPA map
            ipa_map.insert(stripped_word, ipa_word);
        }
    });

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

fn save_ipa_cache(ipa_map: &DashMap<String, String>, ipa_file: &Path) -> std::io::Result<()> {
    let file = File::create(ipa_file)?;
    let writer = BufWriter::new(file);
    let mut serializer = serde_json::Serializer::new(writer);
    
    // Convert DashMap to a regular HashMap before serialization
    let regular_map: HashMap<String, String> = ipa_map.iter().map(|entry| (entry.key().clone(), entry.value().clone())).collect();
    
    regular_map.serialize(&mut serializer)?;
    
    // Explicitly drop the regular_map to free memory
    mem::drop(regular_map);
    
    println!("\nSaved IPA cache to {:?}", ipa_file);
    Ok(())
}