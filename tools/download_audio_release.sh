#!/bin/bash -e
# Download and extract word sounds from GitHub release

# Configuration
RELEASE_TAG="${1:-audio-assets}"
REPO="stephen5ng/cubes"
DOWNLOAD_DIR="${PROJECT_DIR}/audio_download"
PROJECT_DIR="$(pwd)"
ASSETS_DIR="${PROJECT_DIR}/assets"

# Function to cleanup on exit
cleanup() {
    if [ -d "${DOWNLOAD_DIR}" ]; then
        echo "Cleaning up temporary files..."
        rm -rf "${DOWNLOAD_DIR}"
    fi
}

# Set trap for cleanup
trap cleanup EXIT

echo "LexaCube Audio Download Script"
echo "=============================="

# Check if gh is installed
if ! command -v gh >/dev/null 2>&1; then
    echo "Error: GitHub CLI (gh) is not installed."
    echo "Please install it with: sudo apt install gh"
    echo "Then authenticate with: gh auth login"
    exit 1
fi

# Check gh authentication
if ! gh auth status >/dev/null 2>&1; then
    echo "Error: Not authenticated with GitHub."
    echo "Please run: gh auth login"
    exit 1
fi

# Check if audio files already exist
if [ -d "${ASSETS_DIR}/word_sounds_0" ] && [ -d "${ASSETS_DIR}/word_sounds_1" ]; then
    echo "Audio files already exist in assets/"
    read -p "Re-download and overwrite? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Skipping download."
        exit 0
    fi
    echo "Removing existing audio files..."
    rm -rf "${ASSETS_DIR}/word_sounds_0" "${ASSETS_DIR}/word_sounds_1" "${ASSETS_DIR}/word_sounds_2"
fi

# Create download directory
echo "Creating download directory..."
mkdir -p "${DOWNLOAD_DIR}"
cd "${DOWNLOAD_DIR}"

# Check available disk space
DISK_AVAILABLE=$(df -k "${PROJECT_DIR}" | tail -1 | awk '{print $4}')
REQUIRED_SPACE_KB=$((3 * 1024 * 1024))  # 3GB minimum

if [ "${DISK_AVAILABLE}" -lt "${REQUIRED_SPACE_KB}" ]; then
    echo "Error: Not enough disk space."
    echo "Available: ${DISK_AVAILABLE}KB"
    echo "Required: ~${REQUIRED_SPACE_KB}KB (3GB minimum)"
    exit 1
fi

# Check release exists and get asset info
echo "Checking release ${RELEASE_TAG}..."
if ! gh release view "${RELEASE_TAG}" --repo "${REPO}" >/dev/null 2>&1; then
    echo "Error: Release '${RELEASE_TAG}' not found in ${REPO}"
    echo "Available releases:"
    gh release list --repo "${REPO}" --limit 10
    exit 1
fi

# Get release assets
echo "Getting release assets..."
ASSET_URLS=$(gh release view "${RELEASE_TAG}" --repo "${REPO}" --json assets -q '.assets[].url')
PART_COUNT=$(echo "${ASSET_URLS}" | grep -c "word_sounds.tar.gz.part" || echo "0")

if [ "${PART_COUNT}" -eq 0 ]; then
    echo "Error: No word_sounds parts found in release"
    exit 1
fi

echo "Found ${PART_COUNT} parts to download..."

# Download each part
echo "${ASSET_URLS}" | grep "word_sounds.tar.gz.part" | while read -r url; do
    filename=$(basename "${url}")
    echo "Downloading ${filename}..."
    if ! curl -L -H "Accept: application/octet-stream" "${url}" -o "${filename}"; then
        echo "Error: Failed to download ${filename}"
        exit 1
    fi
done

# Check all parts exist
EXPECTED_PARTS=${PART_COUNT}
DOWNLOADED_PARTS=$(ls word_sounds.tar.gz.part.* 2>/dev/null | wc -l)

if [ "${DOWNLOADED_PARTS}" -ne "${EXPECTED_PARTS}" ]; then
    echo "Error: Expected ${EXPECTED_PARTS} parts, downloaded ${DOWNLOADED_PARTS}"
    exit 1
fi

# Reassemble archive
echo "Reassembling archive..."
cat word_sounds.tar.gz.part.* > word_sounds.tar.gz
COMBINED_SIZE=$(ls -lh word_sounds.tar.gz | awk '{print $5}')

# Extract to assets directory
echo "Extracting to assets directory..."
mkdir -p "${ASSETS_DIR}"
tar xzf word_sounds.tar.gz -C "${ASSETS_DIR}"

# Fix directory structure for the game
# The game expects: word_sounds_1 (player 1) and word_sounds_2 (player 2)
# Download provides: word_sounds_0 and word_sounds_1
if [ -d "${ASSETS_DIR}/word_sounds_0" ]; then
    echo "Setting up player directories..."
    # Copy word_sounds_0 to word_sounds_2 for player 2
    cp -r "${ASSETS_DIR}/word_sounds_0" "${ASSETS_DIR}/word_sounds_2"
fi

# Count files
COUNT_0=$(find "${ASSETS_DIR}/word_sounds_0" -name '*.wav' 2>/dev/null | wc -l | tr -d ' ')
COUNT_1=$(find "${ASSETS_DIR}/word_sounds_1" -name '*.wav' 2>/dev/null | wc -l | tr -d ' ')
COUNT_2=$(find "${ASSETS_DIR}/word_sounds_2" -name '*.wav' 2>/dev/null | wc -l | tr -d ' ')

echo ""
echo "✓ Audio files downloaded and extracted successfully!"
echo "  - word_sounds_0/: ${COUNT_0} files"
echo "  - word_sounds_1/: ${COUNT_1} files (Player 1)"
echo "  - word_sounds_2/: ${COUNT_2} files (Player 2)"
echo "  - Combined size: ${COMBINED_SIZE}"
echo ""
echo "The game will now pronounce words when you make correct guesses!"
