use std::collections::HashMap;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::time::Duration;
use std::{env, fs, io, thread};
use std::fs::File;
use std::io::{BufRead, BufReader, Write};
use std::path::Path;
use std::sync::{Arc, Mutex};
use transform_hyphens::transform::transform;
use rayon::prelude::*;

static WORD_COUNT: AtomicUsize = AtomicUsize::new(0);
const BATCH_SIZE: usize = 500;

fn process_word_batch(words: &[String], ipa_map: &HashMap<String, String>) -> Vec<String> {
    words.iter().map(|word| {
        let stripped_word = word.replace("-", "");
        let ipa = ipa_map.get(&stripped_word)
            .unwrap_or_else(|| panic!("IPA not found for word: {}", stripped_word))
            .clone();
        
        if !word.contains('-') {
            return ipa;
        }
        let result = transform(word, &ipa);
        WORD_COUNT.fetch_add(1, Ordering::Relaxed);
        result
    }).collect()
}

pub fn load_ipa_maps() -> HashMap<String, String> {
    let mut ipa_map = HashMap::new();
    let ipa_cache_dir = Path::new("work").join("ipacache");

    if let Ok(entries) = fs::read_dir(ipa_cache_dir) {
        for entry in entries.filter_map(Result::ok) {
            if let Some(file_name) = entry.file_name().to_str() {
                if file_name.ends_with(".json") {
                    let json = fs::read_to_string(entry.path()).expect("Failed to read IPA cache file");
                    let loaded_map: HashMap<String, String> = serde_json::from_str(&json).unwrap_or_else(|_| HashMap::new());
                    ipa_map.extend(loaded_map.into_iter().map(|(k, v)| (v, k)));
                }
            }
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

    let words: Vec<String> = BufReader::new(File::open(input_file)?)
        .lines()
        .filter_map(Result::ok)
        .collect();

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

    println!("Processing words:");
    let out_file = Arc::new(Mutex::new(File::create(output_file)?));
    let ipa_map = load_ipa_maps();

    words.par_chunks(BATCH_SIZE).for_each(|chunk| {
        let batch_results = process_word_batch(chunk, &ipa_map);
        
        let mut file_guard = out_file.lock().unwrap();
        for transformed_word in batch_results {
            writeln!(file_guard, "{}", transformed_word).unwrap();
        }
    });

    let total_words = WORD_COUNT.load(Ordering::Relaxed);

    println!("\nProcessing complete:");
    println!("Total words processed: {}", total_words);

    Ok(())
}