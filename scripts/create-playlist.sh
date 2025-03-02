#!/bin/bash
# Simple script to create a YouTube playlist and save its ID to a file

# Configuration
PROJECT_DIR="/Users/brunowinter/Documents/news"
CREDENTIALS_FILE="$PROJECT_DIR/config/client_secret.json"
PLAYLIST_ID_FILE="$PROJECT_DIR/config/playlist_id.txt"

# Make sure config directory exists
mkdir -p "$PROJECT_DIR/config"

echo "========================================="
echo "YouTube Simple Playlist Creator"
echo "========================================="

# Check for credentials
if [ ! -f "$CREDENTIALS_FILE" ]; then
    echo "ERROR: OAuth credentials file not found at $CREDENTIALS_FILE"
    exit 1
fi

# Create a new playlist
echo "Creating a new permanent playlist..."
PLAYLIST_TITLE="News Feed (Permanent)"
PLAYLIST_DESC="Auto-generated news playlist that is continuously updated"

# Use the correct Python command for your system
# If python3 is your command, change python to python3
OUTPUT=$(python3 "$PROJECT_DIR/scripts/youtube_playlist_creator.py" --credentials "$CREDENTIALS_FILE" --title "$PLAYLIST_TITLE" --description "$PLAYLIST_DESC" --privacy "private")

# Extract playlist ID from output
PLAYLIST_ID=$(echo "$OUTPUT" | grep -o "ID: [A-Za-z0-9_-]\+" | sed 's/ID: //')

if [ -n "$PLAYLIST_ID" ]; then
    echo "New playlist created with ID: $PLAYLIST_ID"
    echo "$PLAYLIST_ID" > "$PLAYLIST_ID_FILE"
    echo "Saved playlist ID to $PLAYLIST_ID_FILE"
    echo "Success! You can now use this ID in your automated system."
else
    echo "ERROR: Could not extract playlist ID from output."
    echo "OUTPUT: $OUTPUT"
    exit 1
fi