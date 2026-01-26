import csv
import os

def main():
    csv_path = 'bingo_stats.csv'
    targets = ['src/data/bingos.txt', 'assets/data/bingos.txt']
    
    threshold = 50
    filtered_words = []
    
    print(f"Reading from {csv_path}...")
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if int(row['AnagramCount']) >= threshold:
                filtered_words.append(row['Word'])
                
    filtered_words.sort() # Ensure alphabetical order or some stable order
    
    print(f"Found {len(filtered_words)} words with >= {threshold} anagrams.")
    
    for target in targets:
        print(f"Updating {target}...")
        with open(target, 'w') as f:
            for word in filtered_words:
                f.write(word + '\n')
                
    print("Done.")

if __name__ == "__main__":
    main()
