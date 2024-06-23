use std::env;
use std::fs::{self, File};
use std::io::{BufRead, BufReader, Write};
use std::path::Path;
use std::process::{Command, Stdio};
use rayon::prelude::*;
use serde_json;
use crate::transform_hyphens::transform;
use std::sync::atomic::{AtomicUsize, Ordering};

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
        .spawn()
        .expect("Failed to spawn espeak-ng");

    {
        let stdin = child.stdin.as_mut().expect("Failed to open stdin");
        for word in &stripped_words {
            writeln!(stdin, "{}", word).expect("Failed to write to stdin");
        }
    }

    let output = child.wait_with_output().expect("Failed to read stdout");
    let ipa_words: Vec<String> = String::from_utf8_lossy(&output.stdout)
        .lines()
        .map(|s| s.to_string())
        .collect();

    words.iter().zip(stripped_words.iter().zip(ipa_words.iter()))
        .map(|(hyphenated_word, (stripped_word, ipa_word))| {
            WORD_COUNT.fetch_add(1, Ordering::Relaxed);
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
    let results: Vec<(String, (String, String))> = words.par_chunks(BATCH_SIZE)
        .flat_map(|chunk| process_word_batch(chunk, language))
        .collect();
    println!("\nProcessed {} words", WORD_COUNT.load(Ordering::Relaxed));

    let (transformed_words, ipa_translations): (Vec<_>, Vec<_>) = results.into_iter().unzip();

    let mut out_file = File::create(output_file)?;
    for result in transformed_words {
        writeln!(out_file, "{}", result)?;
    }

    let cache_dir = Path::new("work").join("ipacache");
    fs::create_dir_all(&cache_dir)?;
    let ipa_file = cache_dir.join(format!("{}.json", language.replace('/', "-")));

    let ipa_map: std::collections::HashMap<_, _> = ipa_translations.into_iter().collect();
    let json = serde_json::to_string(&ipa_map)?;
    fs::write(ipa_file, json)?;

    Ok(())
}