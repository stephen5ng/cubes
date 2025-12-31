#!/bin/bash -ex
export GOOGLE_APPLICATION_CREDENTIALS="./dark-granite-267721-0ee176af2959.json"

# Create output directory if it doesn't exist
mkdir -p word_sounds_0

# Process each word from sowpods.txt
while IFS= read -r word; do
    # Skip empty lines
    if [[ -z "$word" ]]; then
        continue
    fi

    # Get word length
    word_length=$(echo -n "$word" | wc -c)

    # Only process words that are 3-6 letters long
    if [[ $word_length -ge 3 && $word_length -le 6 ]]; then
        # Generate SSML with lively style
        ssml="<speak><google:style name=\"lively\">$word</google:style></speak>"

        # Generate speech with female voice (higher pitch for contrast) and convert to WAV
        echo "$ssml" | ./gosling -v en-US-Standard-C --pitch=5 --ssml - - | \
            sox -t mp3 - -r 48000 -b 16 -c 1 -t wav - >"word_sounds_0/$word.wav"

        # Record processed word
        echo "$word" >>spoken_sowpods_female.txt
    fi
done < sowpods.txt
