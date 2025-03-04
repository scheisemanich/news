#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Service Account Authentication for YouTube API

This script provides authentication functionality using a Google Cloud service account
to access the YouTube Data API. It's designed to replace OAuth-based authentication
for automated processes like GitHub Actions workflows.

Usage:
    from service_account_auth import get_youtube_client
    youtube = get_youtube_client()
"""

import os
import json
import google.oauth2.service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Path to the service account credentials file
DEFAULT_SERVICE_ACCOUNT_FILE = "config/service-account.json"

# Define the scopes required for YouTube API
SCOPES = [
    'https://www.googleapis.com/auth/youtube',
    'https://www.googleapis.com/auth/youtube.force-ssl',
    'https://www.googleapis.com/auth/youtube.readonly'
]

def get_youtube_client(service_account_file=DEFAULT_SERVICE_ACCOUNT_FILE):
    """
    Create an authenticated YouTube API client using service account credentials.
    
    Args:
        service_account_file (str): Path to the service account JSON key file
    
    Returns:
        googleapiclient.discovery.Resource: Authenticated YouTube API client
        
    Raises:
        FileNotFoundError: If the service account file doesn't exist
        ValueError: If the service account credentials are invalid
    """
    if not os.path.exists(service_account_file):
        raise FileNotFoundError(f"Service account file not found: {service_account_file}")
    
    try:
        # Load service account credentials
        credentials = google.oauth2.service_account.Credentials.from_service_account_file(
            service_account_file, 
            scopes=SCOPES
        )
        
        # Build the YouTube API client
        youtube = build('youtube', 'v3', credentials=credentials)
        
        return youtube
    
    except Exception as e:
        raise ValueError(f"Failed to create YouTube client with service account: {e}")

def get_playlist_items(youtube, playlist_id, max_results=50):
    """
    Get items from a YouTube playlist.
    
    Args:
        youtube: Authenticated YouTube API client
        playlist_id (str): YouTube playlist ID
        max_results (int): Maximum number of results to return
    
    Returns:
        list: List of playlist items
    """
    items = []
    
    try:
        request = youtube.playlistItems().list(
            part="snippet,contentDetails",
            playlistId=playlist_id,
            maxResults=min(50, max_results)  # API limit is 50 per request
        )
        
        while request and len(items) < max_results:
            response = request.execute()
            items.extend(response.get("items", []))
            
            # Get the next page of results
            request = youtube.playlistItems().list_next(request, response)
            
            if len(items) >= max_results:
                break
        
        return items[:max_results]
    
    except HttpError as e:
        print(f"Error getting playlist items: {e}")
        return []

def clear_playlist(youtube, playlist_id):
    """
    Remove all items from a YouTube playlist.
    
    Args:
        youtube: Authenticated YouTube API client
        playlist_id (str): YouTube playlist ID
    
    Returns:
        int: Number of items removed
    """
    items_removed = 0
    
    try:
        # Get all playlist items
        request = youtube.playlistItems().list(
            part="id",
            playlistId=playlist_id,
            maxResults=50
        )
        
        while request:
            response = request.execute()
            
            # Delete each item
            for item in response.get("items", []):
                youtube.playlistItems().delete(
                    id=item["id"]
                ).execute()
                items_removed += 1
            
            # Get the next page of results
            request = youtube.playlistItems().list_next(request, response)
        
        return items_removed
    
    except HttpError as e:
        print(f"Error clearing playlist: {e}")
        return items_removed

def add_video_to_playlist(youtube, playlist_id, video_id, position=0):
    """
    Add a video to a YouTube playlist.
    
    Args:
        youtube: Authenticated YouTube API client
        playlist_id (str): YouTube playlist ID
        video_id (str): YouTube video ID
        position (int): Position in the playlist (0 = first)
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        youtube.playlistItems().insert(
            part="snippet",
            body={
                "snippet": {
                    "playlistId": playlist_id,
                    "resourceId": {
                        "kind": "youtube#video",
                        "videoId": video_id
                    },
                    "position": position
                }
            }
        ).execute()
        
        return True
    
    except HttpError as e:
        print(f"Error adding video to playlist: {e}")
        return False

# Example usage
if __name__ == "__main__":
    import sys
    
    # Get the service account file path from command line or use default
    service_account_file = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SERVICE_ACCOUNT_FILE
    
    try:
        # Test authentication
        youtube = get_youtube_client(service_account_file)
        print("Authentication successful!")
        
        # Read playlist ID from file
        playlist_id_file = "config/playlist_id.txt"
        if os.path.exists(playlist_id_file):
            with open(playlist_id_file, 'r') as f:
                playlist_id = f.read().strip()
            
            # Get playlist info
            playlist_response = youtube.playlists().list(
                part="snippet",
                id=playlist_id
            ).execute()
            
            if playlist_response.get("items"):
                playlist = playlist_response["items"][0]
                print(f"Successfully connected to playlist: {playlist['snippet']['title']}")
                print(f"URL: https://www.youtube.com/playlist?list={playlist_id}")
            else:
                print(f"Playlist with ID {playlist_id} not found or not accessible")
        else:
            print(f"Playlist ID file not found: {playlist_id_file}")
    
    except Exception as e:
        print(f"Authentication failed: {e}")
        sys.exit(1)
