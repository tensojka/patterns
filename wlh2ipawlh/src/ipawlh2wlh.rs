use std::env;
use std::path::Path;
use transform_hyphens::get_language;

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

    Ok(())
}