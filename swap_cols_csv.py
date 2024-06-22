import csv
import sys

def swap_columns(input_file, output_file):
    with open(input_file, mode='r', encoding='utf-8') as infile, open(output_file, mode='w', encoding='utf-8', newline='') as outfile:
        reader = csv.reader(infile)
        writer = csv.writer(outfile)
        
        for row in reader:
            # swap the columns
            swapped_row = [row[1], row[0]]
            writer.writerow(swapped_row)
    
    print(f'columns swapped. output written to {output_file}')

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: python script.py <input_file> <output_file>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    
    swap_columns(input_file, output_file)