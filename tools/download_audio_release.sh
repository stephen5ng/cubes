#!/bin/bash -e
# Download and extract word sounds from GitHub release

RELEASE_TAG="${1:-audio-assets}"

echo "Checking if audio files already exist..."
if [ -d "word_sounds_0" ] && [ -d "word_sounds_1" ]; then
    read -p "Audio files exist. Re-download? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Skipping download."
        exit 0
    fi
    echo "Removing existing files..."
    rm -rf word_sounds_0 word_sounds_1
fi

echo "Downloading audio assets from release ${RELEASE_TAG}..."
mkdir -p /tmp/audio_download
cd /tmp/audio_download

# Download all parts
gh release download ${RELEASE_TAG} --pattern "word_sounds.tar.gz.part.*"

echo "Reassembling archive..."
cat word_sounds.tar.gz.part.* > word_sounds.tar.gz

echo "Extracting to project directory..."
tar xzf word_sounds.tar.gz -C "${OLDPWD}"

echo "Cleaning up temporary files..."
cd "${OLDPWD}"
rm -rf /tmp/audio_download

echo "✓ Audio files downloaded and extracted successfully!"
echo "  - word_sounds_0/: $(find word_sounds_0 -name '*.wav' 2>/dev/null | wc -l | tr -d ' ') files"
echo "  - word_sounds_1/: $(find word_sounds_1 -name '*.wav' 2>/dev/null | wc -l | tr -d ' ') files"
