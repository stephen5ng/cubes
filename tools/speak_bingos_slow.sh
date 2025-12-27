#!/bin/bash -ex
voice=en-US-Neural2-H
voice=en-US-News-K
voice=en-US-Studio-O
voice=en-US-Standard-C
voice=en-GB-Standard-F
counter=0
for file in word_sounds/*; do
  # Check if it's a regular file
  if [[ -f "$file" ]]; then
      # Extract filename without extension
      filename=$(basename "$file")
      filename="${filename%.*}" 
      if [[ ${#filename} -eq 6 ]]; then
	echo $filename | ./gosling -v $voice --speaking-rate=0.7 --pitch=0 - - | sox -t mp3 - -r 48000 -b 16 -c 1 -t wav - >gcptts_bingo_slow/$filename.wav
	echo $filename >>spokenbingoslow.txt
	play gcptts_bingo_slow/$filename.wav
    fi
  fi
done
