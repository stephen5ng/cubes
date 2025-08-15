#!/bin/bash -ex
export GOOGLE_APPLICATION_CREDENTIALS="./dark-granite-267721-abb4f420d300.json"
voice=en-US-Neural2-H
voice=en-US-News-K
voice=en-US-Studio-O
voice=en-US-Standard-C
counter=0
for file in word_sounds/*; do
  # Check if it's a regular file
  if [[ -f "$file" ]]; then
    # Extract filename without extension
    filename=$(basename "$file")
    filename="${filename%.*}"
    filename_length=$(echo -n "$filename" | wc -c)
    pitch=$(((6 - filename_length)*2))
    rate=$(((6 - filename_length)/3 + 1))
    
    echo $filename | ./gosling -v $voice -r $rate  --pitch=$pitch - - | sox -t mp3 - -r 48000 -b 16 -c 1 -t wav - >gcptts.length/$filename.wav
    echo $filename >>spoken.txt
  fi
done
