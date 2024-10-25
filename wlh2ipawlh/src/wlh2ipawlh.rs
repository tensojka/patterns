use std::{env, fs};
use std::fs::File;
use std::io::{self, BufRead, BufReader, Write, BufWriter};
use std::path::Path;
use serde_json;
use transform_hyphens::transform::transform;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::collections::HashMap;
use translit::{Transliterator, ToLatin, gost779b_ua, gost779b_ru};
use std::time::Duration;
use std::thread;
use dashmap::DashMap;
use std::sync::Arc;
use std::sync::Mutex;
use serde::Serialize;
use rayon::prelude::*;
use transform_hyphens::utils::{get_language, get_espeak_ipa_batch};

static WORD_COUNT: AtomicUsize = AtomicUsize::new(0);

const BATCH_SIZE: usize = 500;

fn transliterate_ukrainian(input: &str) -> String {
    let tr = Transliterator::new(gost779b_ua());
    input.split('-')
         .map(|part| tr.to_latin(part))
         .collect::<Vec<String>>()
         .join("-")
}

fn transliterate_russian(input: &str) -> String {
    let tr = Transliterator::new(gost779b_ru());
    input.split('-')
         .map(|part| tr.to_latin(part))
         .collect::<Vec<String>>()
         .join("-")
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

    // Process results
    results.into_iter().map(|(hyphenated_word, stripped_word, ipa_word)| {
        let transliterated_hyphenated = if language == "zle/uk" {
            transliterate_ukrainian(&hyphenated_word)
        } else if language == "zle/ru" {
            transliterate_russian(&hyphenated_word)
        } else {
            hyphenated_word.clone()
        };
        if ipa_word.is_empty() {
            println!("Warning: Empty IPA for word: {}", hyphenated_word);
            (hyphenated_word, stripped_word, ipa_word)
        } else {
            let result = if hyphenated_word.contains('-') {
                transform(&transliterated_hyphenated, &ipa_word)
            } else {
                ipa_word.clone()
            };
            WORD_COUNT.fetch_add(1, Ordering::Relaxed);
            (result, stripped_word, ipa_word)
        }
    }).collect()
}

pub fn load_ipa_map(ipa_file: &Path) -> Arc<DashMap<String, String>> {
    let ipa_map = Arc::new(DashMap::new());
    if ipa_file.exists() {
        let json = fs::read_to_string(ipa_file).expect("Failed to read IPA cache file");
        let loaded_map: HashMap<String, String> = serde_json::from_str(&json).unwrap_or_else(|_| HashMap::new());
        for (key, value) in loaded_map {
            ipa_map.insert(key, value);
        }
    }
    ipa_map
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

    let out_file = Arc::new(Mutex::new(File::create(output_file)?));
    let ipa_file = Path::new("work").join("ipacache").join(format!("{}.json", language.replace('/', "-")));
    let ipa_map = load_ipa_map(&ipa_file);

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
            if !transformed_word.contains("(") { // FIXME – ignoring all that start with (en)
               writeln!(file_guard, "{}", transformed_word).unwrap();
            }
            
            // Update IPA map
            ipa_map.insert(stripped_word, ipa_word);
        }
    });

    let total_words = WORD_COUNT.load(Ordering::Relaxed);

    println!("\nProcessing complete:");
    println!("Total words processed: {}", total_words);

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
    
    println!("\nSaved IPA cache to {:?}", ipa_file);
    Ok(())
}