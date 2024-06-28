use std::env;
use std::fs::{self, File};
use std::io::{BufRead, BufReader, Write};
use std::path::Path;
use std::process::{Command, Stdio};
use rayon::prelude::*;
use serde_json;
use crate::transform_hyphens::transform;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::Mutex;
use std::collections::HashMap;
use std::io::ErrorKind;

mod transform_hyphens;

static WORD_COUNT: AtomicUsize = AtomicUsize::new(0);

const BATCH_SIZE: usize = 100;

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
            let count = WORD_COUNT.fetch_add(1, Ordering::Relaxed);
            if count % 1024 == 0 {
                print!(".");
                std::io::stdout().flush().unwrap();
            }
            (transform(hyphenated_word, ipa_word), (stripped_word.clone(), ipa_word.clone()))
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

    // Limit the number of threads to 128 or the number of available cores, whichever is smaller
    let num_threads = std::cmp::min(128, rayon::current_num_threads());
    rayon::ThreadPoolBuilder::new().num_threads(num_threads).build_global().unwrap();

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
            
            // Print progress
            let count = WORD_COUNT.load(Ordering::Relaxed);
            print!("\rProcessed {} words", count);
            std::io::stdout().flush()?;

            Ok(())
        })?;

    println!("\nProcessed {} words", WORD_COUNT.load(Ordering::Relaxed));

    // Write IPA cache
    let cache_dir = Path::new("work").join("ipacache");
    fs::create_dir_all(&cache_dir)?;
    let ipa_file = cache_dir.join(format!("{}.json", language.replace('/', "-")));

    let ipa_map = ipa_map.into_inner().map_err(|e| {
        std::io::Error::new(ErrorKind::Other, format!("Failed to unwrap IPA map: {}", e))
    })?;
    let json = serde_json::to_string(&ipa_map)?;
    fs::write(ipa_file, json)?;

    Ok(())
}