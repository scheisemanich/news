#!/bin/bash
# Single Playlist Update Script
# Creates a single playlist on first run and always updates that same playlist afterward

# Configuration
PROJECT_DIR=$(pwd)
CONFIG_FILE="$PROJECT_DIR/config/config.json"
CREDENTIALS_FILE="$PROJECT_DIR/config/client_secret.json"
OUTPUT_JSON="$PROJECT_DIR/output/latest_news.json"
PLAYLIST_ID_FILE="$PROJECT_DIR/config/playlist_id.txt"
LOG_FILE="$PROJECT_DIR/logs/update_log.txt"

# Create necessary directories
mkdir -p config output logs

# Print header
echo "========================================="
echo "YouTube News Single Playlist Update Tool"
echo "========================================="
echo "Running in: $PROJECT_DIR"
echo ""

# Step 1: Check for credentials
if [ ! -f "$CREDENTIALS_FILE" ]; then
    echo "ERROR: OAuth credentials file not found at $CREDENTIALS_FILE"
    echo "Please ensure you have a valid client_secret.json file in the config directory."
    exit 1
fi

# Step 2: Collect news videos
echo "Collecting news videos..."
python scripts/youtube_news_aggregator.py --load-config "$CONFIG_FILE" --days-back 1 --output-file "$OUTPUT_JSON"

if [ $? -ne 0 ] || [ ! -f "$OUTPUT_JSON" ]; then
    echo "ERROR: Failed to collect news videos. Check the script output above."
    exit 1
fi

VIDEO_COUNT=$(grep -o "\"id\":" "$OUTPUT_JSON" | wc -l)
echo "Successfully collected $VIDEO_COUNT videos."

# Step 3: Check for existing playlist ID
if [ -f "$PLAYLIST_ID_FILE" ] && [ -s "$PLAYLIST_ID_FILE" ]; then
    PLAYLIST_ID=$(cat "$PLAYLIST_ID_FILE")
    echo "Found existing playlist ID: $PLAYLIST_ID"
    echo "Updating existing playlist..."
    
    python scripts/youtube_playlist_creator.py --json-file "$OUTPUT_JSON" --credentials "$CREDENTIALS_FILE" --playlist-id "$PLAYLIST_ID" --max-per-channel 5
    
    UPDATE_RESULT=$?
    if [ $UPDATE_RESULT -ne 0 ]; then
        echo "WARNING: Error updating existing playlist (error code: $UPDATE_RESULT)."
        echo "The playlist ID may be invalid."
        
        # Instead of creating a new playlist, prompt for a valid ID
        echo "Please enter a valid playlist ID to use, or leave empty to create a new one (ONE TIME ONLY):"
        read MANUAL_PLAYLIST_ID
        
        if [ -n "$MANUAL_PLAYLIST_ID" ]; then
            echo "$MANUAL_PLAYLIST_ID" > "$PLAYLIST_ID_FILE"
            echo "Saved manual playlist ID. Will use this ID for all future updates."
            exit 0
        fi
        
        # Only create a new playlist if explicitly confirmed
        echo "Are you sure you want to create a NEW playlist? This should only be done once. (y/n):"
        read CONFIRM_CREATE
        if [ "$CONFIRM_CREATE" != "y" ]; then
            echo "Operation cancelled. Please fix the playlist ID issue and try again."
            exit 1
        fi
    else
        echo "Playlist successfully updated."
        echo "Update completed at $(date)" >> "$LOG_FILE"
        exit 0
    fi
else
    echo "No existing playlist ID found."
    echo "This appears to be the first run - will create a new playlist."
fi

# Step 4: First run only - create a new playlist
echo "Creating a new playlist (ONE TIME OPERATION)..."
PLAYLIST_TITLE="News Feed (Permanent)"
PLAYLIST_DESC="Auto-generated news playlist that is continuously updated"

echo "Running playlist creator..."
OUTPUT=$(python scripts/youtube_playlist_creator.py --json-file "$OUTPUT_JSON" --credentials "$CREDENTIALS_FILE" --title "$PLAYLIST_TITLE" --description "$PLAYLIST_DESC" --privacy "private" --max-per-channel 5)

CREATE_RESULT=$?
if [ $CREATE_RESULT -ne 0 ]; then
    echo "ERROR: Failed to create new playlist (error code: $CREATE_RESULT)."
    echo "$OUTPUT"
    exit 1
fi

# Extract playlist ID from output
NEW_PLAYLIST_ID=$(echo "$OUTPUT" | grep -o "ID: [A-Za-z0-9_-]\+" | sed 's/ID: //')

if [ -n "$NEW_PLAYLIST_ID" ]; then
    echo "New playlist created with ID: $NEW_PLAYLIST_ID"
    echo "$NEW_PLAYLIST_ID" > "$PLAYLIST_ID_FILE"
    echo "Saved playlist ID to $PLAYLIST_ID_FILE"
    echo "*** IMPORTANT: This playlist ID will be used for all future updates. ***"
    echo "*** DO NOT delete the $PLAYLIST_ID_FILE file. ***"
else
    echo "ERROR: Could not extract playlist ID from output."
    echo "OUTPUT: $OUTPUT"
    exit 1
fi

# Step 5: Update logs
echo "Update completed at $(date)" >> "$LOG_FILE"

echo ""
echo "========================================="
echo "Process completed successfully!"
echo "The YouTube playlist has been updated with the latest news videos."
echo "All future runs will update the same playlist."
echo "========================================="