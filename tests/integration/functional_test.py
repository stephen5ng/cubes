#!/usr/bin/env python3

import argparse
import difflib
import filecmp
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def run_replay_test(test_name):
    """Run a test in replay mode and compare output with golden files."""
    replay_file = f"replay/{test_name}/game_replay.jsonl"
    golden_dir = f"goldens/{test_name}"
    output_dir = "output"
    
    if not os.path.exists(replay_file):
        print(f"Error: Replay file {replay_file} not found")
        return False
    
    if not os.path.exists(golden_dir):
        print(f"Error: Golden directory {golden_dir} not found")
        return False
    
    # Clean output directory
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    os.makedirs(output_dir)
    
    # Run the replay
    cmd = ["python", "./runpygame.py", "--replay", replay_file]
    print(f"Running: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd)
        print(f"Replay completed with return code: {result.returncode}")
        if result.returncode != 0:
            print(f"Warning: Replay exited with non-zero return code: {result.returncode}")
            
    except subprocess.TimeoutExpired:
        print("Error: Replay timed out after 30 seconds")
        return False
    except Exception as e:
        print(f"Error running replay: {e}")
        return False
    
    # Compare output files with golden files
    golden_files = list(Path(golden_dir).glob("*.jsonl"))
    if not golden_files:
        print(f"Error: No golden files found in {golden_dir}")
        return False
    
    all_match = True
    for golden_file in golden_files:
        output_file = Path(output_dir) / golden_file.name
        if not output_file.exists():
            print(f"Error: Output file {output_file} not found")
            all_match = False
            continue
        
        if not filecmp.cmp(golden_file, output_file, shallow=False):
            print(f"Error: Files differ: {golden_file} vs {output_file}")
            print("Diff:")
            try:
                with open(golden_file, 'r') as f1, open(output_file, 'r') as f2:
                    golden_lines = f1.readlines()
                    output_lines = f2.readlines()
                    diff = difflib.unified_diff(
                        golden_lines, output_lines,
                        fromfile=str(golden_file), tofile=str(output_file),
                        lineterm=''
                    )
                    for line in diff:
                        print(line)
            except Exception as e:
                print(f"Error reading files for diff: {e}")
            all_match = False
        else:
            print(f"✓ {golden_file.name} matches")
    
    return all_match


def rerecord_test(test_name):
    """Run a test in replay mode and overwrite golden files with new output."""
    replay_file = f"replay/{test_name}/game_replay.jsonl"
    golden_dir = f"goldens/{test_name}"
    output_dir = "output"
    
    if not os.path.exists(replay_file):
        print(f"Error: Replay file {replay_file} not found")
        return False
    
    # Clean output directory
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    os.makedirs(output_dir)
    
    # Run the replay
    cmd = ["python", "./runpygame.py", "--replay", replay_file]
    print(f"Running: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd)
        print(f"Replay completed with return code: {result.returncode}")
        if result.returncode != 0:
            print(f"Warning: Replay exited with non-zero return code: {result.returncode}")
            
    except subprocess.TimeoutExpired:
        print("Error: Replay timed out after 30 seconds")
        return False
    except Exception as e:
        print(f"Error running replay: {e}")
        return False
    
    if not os.path.exists(output_dir):
        print(f"Error: Output directory {output_dir} not found after replay")
        return False
    
    # Create golden directory if it doesn't exist
    os.makedirs(golden_dir, exist_ok=True)
    
    # Copy output files to golden directory (overwriting old ones)
    output_files = list(Path(output_dir).glob("*.jsonl"))
    if not output_files:
        print(f"Error: No output files found in {output_dir}")
        return False
    
    for output_file in output_files:
        golden_file = Path(golden_dir) / output_file.name
        shutil.copy2(output_file, golden_file)
        print(f"Updated: {golden_file}")
    
    # Move game_replay.jsonl to replay directory if it exists (overwriting old one)
    replay_file_path = Path("game_replay.jsonl")
    if replay_file_path.exists():
        replay_dir = f"replay/{test_name}"
        os.makedirs(replay_dir, exist_ok=True)
        replay_dest = Path(replay_dir) / "game_replay.jsonl"
        shutil.move(replay_file_path, replay_dest)
        print(f"Updated: {replay_dest}")
    
    return True


def record_golden_files(test_name):
    """Record golden files from current output directory."""
    output_dir = "output"
    golden_dir = f"goldens/{test_name}"
    replay_dir = f"replay/{test_name}"
    
    # Clean output directory
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    os.makedirs(output_dir)
    
    # Run the game to generate output files and replay
    cmd = ["python", "./runpygame.py"]
    print(f"Running: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd)
        print(f"Game completed with return code: {result.returncode}")
        if result.returncode != 0:
            print(f"Warning: Game exited with non-zero return code: {result.returncode}")
            
    except subprocess.TimeoutExpired:
        print("Error: Game timed out after 30 seconds")
        return False
    except Exception as e:
        print(f"Error running game: {e}")
        return False
    
    if not os.path.exists(output_dir):
        print(f"Error: Output directory {output_dir} not found after game run")
        return False
    
    # Create golden directory
    os.makedirs(golden_dir, exist_ok=True)
    
    # Copy output files to golden directory
    output_files = list(Path(output_dir).glob("*.jsonl"))
    if not output_files:
        print(f"Error: No output files found in {output_dir}")
        return False
    
    for output_file in output_files:
        golden_file = Path(golden_dir) / output_file.name
        shutil.copy2(output_file, golden_file)
        print(f"Recorded: {golden_file}")
    
    # Move game_replay.jsonl to replay directory
    replay_file = Path("game_replay.jsonl")
    if replay_file.exists():
        os.makedirs(replay_dir, exist_ok=True)
        replay_dest = Path(replay_dir) / "game_replay.jsonl"
        shutil.move(replay_file, replay_dest)
        print(f"Moved: {replay_dest}")
    
    return True


def main():
    parser = argparse.ArgumentParser(description="Functional testing for cubes game")
    parser.add_argument("mode", choices=["replay", "record", "rerecord"], 
                       help="Test mode: replay (compare with goldens), record (create goldens), or rerecord (overwrite goldens)")
    parser.add_argument("test_name", help="Name of the test (e.g., 'smoke')")
    
    args = parser.parse_args()
    if args.mode == "replay":
        success = run_replay_test(args.test_name)
        if success:
            print(f"\n✓ Test '{args.test_name}' passed")
            sys.exit(0)
        else:
            print(f"\n✗ Test '{args.test_name}' failed")
            sys.exit(1)
    elif args.mode == "rerecord":
        success = rerecord_test(args.test_name)
        if success:
            print(f"\n✓ Test '{args.test_name}' rerecorded")
            sys.exit(0)
        else:
            print(f"\n✗ Failed to rerecord test '{args.test_name}'")
            sys.exit(1)
    else:  # record mode
        success = record_golden_files(args.test_name)
        if success:
            print(f"\n✓ Golden files recorded for test '{args.test_name}'")
            sys.exit(0)
        else:
            print(f"\n✗ Failed to record golden files for test '{args.test_name}'")
            sys.exit(1)


if __name__ == "__main__":
    main() 