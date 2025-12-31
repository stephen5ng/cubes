#!/bin/bash -e
# Upload word sounds to GitHub release

RELEASE_TAG="${1:-audio-assets}"
CHUNK_SIZE="100M"

echo "Creating audio archive..."
tar czf word_sounds.tar.gz word_sounds_0/ word_sounds_1/

echo "Splitting into ${CHUNK_SIZE} chunks..."
split -b ${CHUNK_SIZE} word_sounds.tar.gz word_sounds.tar.gz.part.

echo "Checking if release ${RELEASE_TAG} exists..."
if gh release view ${RELEASE_TAG} >/dev/null 2>&1; then
    echo "Release exists, deleting old assets..."
    gh release delete ${RELEASE_TAG} -y
fi

echo "Creating release ${RELEASE_TAG}..."
gh release create ${RELEASE_TAG} \
    --title "Audio Assets for Word Sounds" \
    --notes "Pregenerated TTS audio files for word pronunciations.

**Player 0 (Female):** word_sounds_0/ - en-US-Standard-C voice at pitch +5
**Player 1 (Male):** word_sounds_1/ - en-US-Standard-D voice

To download and extract:
\`\`\`bash
./tools/download_audio_release.sh
\`\`\`

Generated using tools/speak_sowpods_female.sh and tools/speak_sowpods.sh" \
    word_sounds.tar.gz.part.*

echo "Cleaning up temporary files..."
rm -f word_sounds.tar.gz word_sounds.tar.gz.part.*

echo "✓ Upload complete! Release: ${RELEASE_TAG}"
