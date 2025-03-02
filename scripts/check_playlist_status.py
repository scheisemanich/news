import os
import json
import argparse
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

def check_playlist_status(credentials_file, token_file, playlist_id):
    """
    Check the status of a YouTube playlist.
    
    Args:
        credentials_file (str): Path to the OAuth 2.0 client credentials file
        token_file (str): Path to the token file
        playlist_id (str): YouTube playlist ID
    """
    # Load credentials
    if not os.path.exists(credentials_file) or not os.path.exists(token_file):
        print(f"Error: Credentials files not found.")
        return False
    
    # Load token
    with open(token_file, 'r') as f:
        token_data = json.load(f)
    
    creds = Credentials.from_authorized_user_info(token_data)
    
    if not creds or not creds.valid:
        print("Error: Invalid or expired credentials")
        return False
    
    # Build YouTube API client
    youtube = build('youtube', 'v3', credentials=creds)
    
    try:
        # Get playlist details
        playlist_response = youtube.playlists().list(
            part="snippet,contentDetails,status",
            id=playlist_id
        ).execute()
        
        if not playlist_response.get("items"):
            print(f"Error: Playlist {playlist_id} not found.")
            return False
        
        playlist = playlist_response["items"][0]
        
        print("\nPlaylist Information:")
        print(f"Title: {playlist['snippet']['title']}")
        print(f"Status: {playlist['status']['privacyStatus']}")
        print(f"Video count: {playlist['contentDetails']['itemCount']}")
        print(f"URL: https://www.youtube.com/playlist?list={playlist_id}")
        
        # Get the first few videos
        items_response = youtube.playlistItems().list(
            part="snippet",
            playlistId=playlist_id,
            maxResults=5
        ).execute()
        
        print("\nLatest videos in playlist:")
        for item in items_response.get("items", []):
            print(f"- {item['snippet']['title']}")
        
        return True
        
    except Exception as e:
        print(f"Error checking playlist: {e}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="YouTube Playlist Status Checker")
    parser.add_argument("--credentials", default="config/client_secret.json", 
                       help="Path to the OAuth 2.0 client credentials file")
    parser.add_argument("--token", default="config/token.json",
                       help="Path to the token file")
    parser.add_argument("--playlist-id", help="YouTube playlist ID")
    
    args = parser.parse_args()
    
    # If playlist ID is not provided, try to read from file
    playlist_id = args.playlist_id
    if not playlist_id and os.path.exists("config/playlist_id.txt"):
        with open("config/playlist_id.txt", "r") as f:
            playlist_id = f.read().strip()
    
    if not playlist_id:
        print("Error: No playlist ID provided.")
        exit(1)
    
    check_playlist_status(args.credentials, args.token, playlist_id)