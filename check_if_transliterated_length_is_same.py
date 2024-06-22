import epitran

# Initialize the Epitran object for Czech
ces = epitran.Epitran('pol-Latn')

# Function to process each line
def process_line(line):
    tuples = ces.word_to_tuples(line)
    replaced = line.replace('ch', 'x')
    
    if len(tuples) != len(replaced):
        print(f"Original: {line.strip()}")
        print(f"Transliterated: {ces.transliterate(line)}")
        print(f"Replaced: {replaced}")

# Read the file line by line and process each line
def main():
    input_file = 'work/pl.wls'  # replace with your actual file path
    with open(input_file, 'r', encoding='utf-8') as file:
        for line in file:
            process_line(line)

if __name__ == "__main__":
    main()