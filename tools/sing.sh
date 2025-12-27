#!/bin/bash

# Configuration
export GOOGLE_APPLICATION_CREDENTIALS="./dark-granite-267721-abb4f420d300.json"

WORDLIST="wordlist.txt"
OUTPUT_DIR="gosling_outputs"
STYLE="Sing the word '%s' in a joyful, celebratory tone, like a musical jingle at a party"

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Check if gosling is installed
if ! command -v ./gosling &> /dev/null; then
    echo "Error: gosling command not found. Please install Gosling."
    exit 1
fi

# Process each word
while IFS= read -r WORD; do
    if [[ -z "$WORD" ]]; then
        continue
    fi

    PROMPT=$(printf "$STYLE" "$WORD")
    OUTFILE="${OUTPUT_DIR}/${WORD}.wav"

    echo "Generating audio for word: $WORD"
    ./gosling generate \
        --prompt "$PROMPT" \
        --output "$OUTFILE"

done < "$WORDLIST"

echo "✅ Done generating all word audio files."
