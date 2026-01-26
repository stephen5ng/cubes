import sys
import os
import csv

# Add src to python path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
src_dir = os.path.join(project_root, 'src')
sys.path.append(src_dir)

# Change CWD to project root so that relative paths in config work
os.chdir(project_root)

from core.anagram_helper import AnagramHelper
from config import game_config

def main():
    print(f"Working directory: {os.getcwd()}")
    print("Initializing AnagramHelper...")
    # AnagramHelper singleton initialization
    try:
        helper = AnagramHelper.get_instance()
    except Exception as e:
        print(f"Failed to initialize AnagramHelper: {e}")
        # Try to fix path if needed?
        import traceback
        traceback.print_exc()
        return

    # Use the path from config if possible, else construct it
    # game_config.BINGOS_PATH is likely relative "assets/data/bingos.txt"
    bingos_path = game_config.BINGOS_PATH
    if not os.path.isabs(bingos_path):
        bingos_path = os.path.join(project_root, bingos_path)
        
    output_path = os.path.join(project_root, 'bingo_stats.csv')
    
    print(f"Reading bingos from {bingos_path}...")
    
    if not os.path.exists(bingos_path):
        print(f"Error: Could not find bingos file at {bingos_path}")
        return

    results = []
    
    with open(bingos_path, 'r') as f:
        bingos = [line.strip().upper() for line in f if line.strip()]
    
    print(f"Found {len(bingos)} bingo words. Calculating anagram counts...")
    
    count = 0
    total = len(bingos)
    
    for word in bingos:
        anagram_count = helper.count_anagrams(word)
        results.append((word, anagram_count))
        
        count += 1
        if count % 100 == 0:
            print(f"Processed {count}/{total}...", end='\r')
            
    print(f"Processed {total}/{total}. Done.")
    
    # Sort by anagram count descending
    results.sort(key=lambda x: x[1], reverse=True)
    
    print(f"Writing results to {output_path}...")
    with open(output_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Word', 'AnagramCount'])
        writer.writerows(results)
        
    print("Success!")

if __name__ == "__main__":
    main()
