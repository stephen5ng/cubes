#!/bin/bash -e
voice=en-US-Neural2-H
voice=en-US-News-K
voice=en-US-Studio-O
voice=en-US-Standard-C
voice=en-GB-Standard-F
counter=0
voice=Alex
voice=Kate
voices="Alex Allison Ava Evan Fiona Isha Joelle Mathilda Nicky Stephanie Tom Zoe"


# echo hi | ./gosling - - | play -t mp3 -
# cat ./speech.ssml | ./gosling -s - - | play -t mp3 -
# exit 0
record_word() {
  echo recording $1 $2
  say $1 -v $2 -o /tmp/$1_$2.aiff
  sox  -v 0.97 /tmp/$1_$2.aiff -r 48000 -b 16 -c 1 -t wav - >$2/$1.wav
  rm /tmp/$1_$2.aiff
}
export -f record_word
cd voices
for voice in $voices; do
  mkdir -p $voice
done
mkdir -p merged
for file in ../word_sounds/*; do
# test_words="../word_sounds/afflux.wav ../word_sounds/abacus.wav ../word_sounds/serial.wav ../word_sounds/search.wav ../word_sounds/abjure.wav"
# for file in $test_words; do
  # Check if it's a regular file
  if [[ -f "$file" ]]; then
      # Extract filename without extension
      filename=$(basename "$file")
      filename="${filename%.*}"
      if [[ ${#filename} -eq 6 ]]; then
        echo $voices | xargs -P 0 -I{} -n1 bash -c 'record_word "$@"' _ $filename {}
        voice_files=$(echo "$voices" | sed -E "s/([^ ]+)/\1\/$filename.wav/g")
        voice_files="$voice_files ../gcptts/$filename.wav merged/$filename.wav"
        echo "$voice_files" | xargs sox -m

        # for voice in $voices; do
        #   record_word $filename $voice
        # done
        # sed "s/search/$filename/g" ./speech.ssml | ./gosling -s - - | sox -t mp3 - -r 48000 -b 16 -c 1 -t wav - >gcptts_chorus/$filename.wav
       # echo $filename | ./gosling -v $voice --pitch=2 - - | sox -t mp3 - -r 48000 -b 16 -c 1 -t wav - >gcptts_bingo/$filename.wav
	     echo $filename >>spokenchorus.txt
#	play gcptts_bingo/$filename.wav
    fi
  fi
done
