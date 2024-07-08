use std::env;
use std::fs::{self, File};
use std::io::{self, BufRead, BufReader, Write};
use std::path::Path;
use std::process::{Command, Stdio};
use rayon::prelude::*;
use serde_json;
use crate::transform_hyphens::transform;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::Mutex;
use std::collections::HashMap;
use std::io::ErrorKind;
use translit::{Transliterator, gost779b_ua};
use std::sync::Arc;
use std::time::{Duration, Instant};
use std::thread;

mod transform_hyphens;

static WORD_COUNT: AtomicUsize = AtomicUsize::new(0);

const BATCH_SIZE: usize = 100;
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

    words.iter().zip(stripped_words.iter().zip(ipa_words.iter()))
        .map(|(hyphenated_word, (stripped_word, ipa_word))| {
            let transliterated_hyphenated = if language == "zle/uk" {
                transliterate_ukrainian(hyphenated_word)
            } else {
                hyphenated_word.to_string()
            };
            let res = (transform(&transliterated_hyphenated, ipa_word), (stripped_word.clone(), ipa_word.clone()));
            WORD_COUNT.fetch_add(1, Ordering::Relaxed);
            res
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
    let ipa_map = Mutex::new(HashMap::new());

    // Load existing IPA cache
    let cache_dir = Path::new("work").join("ipacache");
    fs::create_dir_all(&cache_dir)?;
    let ipa_file = cache_dir.join(format!("{}.json", language.replace('/', "-")));
    let mut ipa_map = if ipa_file.exists() {
        let json = fs::read_to_string(&ipa_file)?;
        serde_json::from_str(&json).unwrap_or_else(|_| HashMap::new())
    } else {
        HashMap::new()
    };
    let ipa_map = Mutex::new(ipa_map);

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

    let last_cache_save = Mutex::new(Instant::now());

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
                let mut map_guard = ipa_map.lock().map_err(|e| {
                    std::io::Error::new(ErrorKind::Other, format!("Failed to lock IPA map: {}", e))
                })?;
                map_guard.insert(stripped_word.clone(), ipa_word.clone());
            }
            
            // Check if it's time to save the cache
            let mut last_save = last_cache_save.lock().map_err(|e| {
                std::io::Error::new(ErrorKind::Other, format!("Failed to lock last_cache_save: {}", e))
            })?;
            if last_save.elapsed() >= CACHE_INTERVAL {
                save_ipa_cache(&ipa_map, &ipa_file)?;
                *last_save = Instant::now();
            }
            
            Ok(())
        })?;

    println!("\nFinished processing {} words", WORD_COUNT.load(Ordering::Relaxed));

    // Final cache save
    save_ipa_cache(&ipa_map, &ipa_file)?;

    Ok(())
}

fn save_ipa_cache(ipa_map: &Mutex<HashMap<String, String>>, ipa_file: &Path) -> std::io::Result<()> {
    let map_guard = ipa_map.lock().map_err(|e| {
        std::io::Error::new(ErrorKind::Other, format!("Failed to lock IPA map: {}", e))
    })?;
    let json = serde_json::to_string(&*map_guard)?;
    fs::write(ipa_file, json)?;
    println!("\nSaved IPA cache to {:?}", ipa_file);
    Ok(())
}