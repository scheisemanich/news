import os
import json
import argparse
from datetime import datetime
from collections import defaultdict
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# Define the scopes required for the YouTube Data API
SCOPES = [
    'https://www.googleapis.com/auth/youtube',
    'https://www.googleapis.com/auth/youtube.force-ssl'
]

class YouTubePlaylistCreator:
    def __init__(self, credentials_file, token_file="config/token.json"):
        """
        Initialize the YouTube Playlist Creator.
        
        Args:
            credentials_file (str): Path to the OAuth 2.0 client credentials file
            token_file (str): Path to save the authorization token
        """
        self.credentials_file = credentials_file
        self.token_file = token_file
        self.youtube = self._authenticate()
    
    def _authenticate(self):
        """Authenticate with YouTube API using OAuth 2.0."""
        creds = None
        
        # Load existing token if available
        if os.path.exists(self.token_file):
            creds = Credentials.from_authorized_user_info(
                json.loads(open(self.token_file, 'r').read())
            )
        
        # If credentials don't exist or are invalid, get new ones
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_file, SCOPES
                )
                creds = flow.run_local_server(port=0)
            
            # Save credentials for future use
            with open(self.token_file, 'w') as token:
                token.write(creds.to_json())
        
        # Build YouTube API client
        return build('youtube', 'v3', credentials=creds)
    
    def create_playlist(self, title, description="", privacy_status="private"):
        """
        Create a new YouTube playlist.
        
        Args:
            title (str): Playlist title
            description (str): Playlist description
            privacy_status (str): Privacy status ("public", "private", or "unlisted")
            
        Returns:
            str: ID of the created playlist, or None if failed
        """
        try:
            response = self.youtube.playlists().insert(
                part="snippet,status",
                body={
                    "snippet": {
                        "title": title,
                        "description": description
                    },
                    "status": {
                        "privacyStatus": privacy_status
                    }
                }
            ).execute()
            
            playlist_id = response["id"]
            print(f"Created playlist: {title} (ID: {playlist_id})")
            return playlist_id
            
        except HttpError as e:
            print(f"Error creating playlist: {e}")
            return None
    
    def add_video_to_playlist(self, playlist_id, video_id):
        """
        Add a video to a playlist.
        
        Args:
            playlist_id (str): YouTube playlist ID
            video_id (str): YouTube video ID
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            self.youtube.playlistItems().insert(
                part="snippet",
                body={
                    "snippet": {
                        "playlistId": playlist_id,
                        "resourceId": {
                            "kind": "youtube#video",
                            "videoId": video_id
                        }
                    }
                }
            ).execute()
            
            return True
            
        except HttpError as e:
            print(f"Error adding video {video_id} to playlist: {e}")
            return False
    
    def clear_playlist(self, playlist_id):
        """
        Remove all videos from a playlist.
        
        Args:
            playlist_id (str): YouTube playlist ID
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Get all items in the playlist
            request = self.youtube.playlistItems().list(
                part="id",
                playlistId=playlist_id,
                maxResults=50
            )
            
            while request:
                response = request.execute()
                
                # Delete each item
                for item in response.get("items", []):
                    self.youtube.playlistItems().delete(
                        id=item["id"]
                    ).execute()
                
                # Get next page of results
                request = self.youtube.playlistItems().list_next(request, response)
            
            print(f"Cleared all videos from playlist {playlist_id}")
            return True
            
        except HttpError as e:
            print(f"Error clearing playlist: {e}")
            return False
    
    def get_playlist_stats(self, playlist_id):
        """
        Get statistics for a playlist.
        
        Args:
            playlist_id (str): YouTube playlist ID
            
        Returns:
            dict: Dictionary with playlist statistics
        """
        try:
            # Get playlist details
            playlist_response = self.youtube.playlists().list(
                part="snippet,contentDetails",
                id=playlist_id
            ).execute()
            
            if not playlist_response.get("items"):
                print(f"Playlist {playlist_id} not found")
                return None
            
            playlist = playlist_response["items"][0]
            
            # Get items in the playlist
            items_response = self.youtube.playlistItems().list(
                part="snippet",
                playlistId=playlist_id,
                maxResults=50
            ).execute()
            
            return {
                "title": playlist["snippet"]["title"],
                "description": playlist["snippet"]["description"],
                "item_count": playlist["contentDetails"]["itemCount"],
                "created_at": playlist["snippet"]["publishedAt"],
                "url": f"https://www.youtube.com/playlist?list={playlist_id}",
                "items": [
                    {
                        "title": item["snippet"]["title"],
                        "video_id": item["snippet"]["resourceId"]["videoId"],
                        "position": item["snippet"]["position"],
                        "channel_id": item["snippet"]["channelId"] if "channelId" in item["snippet"] else None,
                        "channel_title": item["snippet"]["channelTitle"] if "channelTitle" in item["snippet"] else None
                    }
                    for item in items_response.get("items", [])
                ]
            }
            
        except HttpError as e:
            print(f"Error getting playlist stats: {e}")
            return None


def update_news_playlist(json_file, credentials_file, playlist_id=None, playlist_title=None,
                        playlist_description=None, privacy_status="private", max_videos_per_channel=5):
    """
    Update a YouTube playlist with the latest news videos.
    
    Args:
        json_file (str): Path to the JSON file generated by the YouTube News Aggregator
        credentials_file (str): Path to the OAuth 2.0 client credentials file
        playlist_id (str, optional): Existing playlist ID to update
        playlist_title (str, optional): Title for a new playlist
        playlist_description (str, optional): Description for a new playlist
        privacy_status (str): Privacy status for a new playlist
        max_videos_per_channel (int): Maximum number of videos per channel
        
    Returns:
        str: Playlist ID
    """
    # Load videos from JSON file
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            videos = json.load(f)
            
        if not videos:
            print("No videos found in JSON file")
            return None
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading JSON file: {e}")
        return None
    
    # Initialize YouTube Playlist Creator
    creator = YouTubePlaylistCreator(credentials_file)
    
    # Create or use existing playlist
    if playlist_id:
        # Clear existing playlist
        creator.clear_playlist(playlist_id)
    else:
        # Create new playlist
        if not playlist_title:
            playlist_title = f"News Feed {datetime.now().strftime('%Y-%m-%d')}"
        
        if not playlist_description:
            playlist_description = f"Auto-generated news playlist created on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        playlist_id = creator.create_playlist(
            title=playlist_title,
            description=playlist_description,
            privacy_status=privacy_status
        )
        
        if not playlist_id:
            print("Failed to create playlist")
            return None
    
    # Apply channel limit (max 5 videos per channel)
    # Group videos by channel
    videos_by_channel = defaultdict(list)
    for video in videos:
        channel_id = video.get('channel_id')
        if channel_id:
            videos_by_channel[channel_id].append(video)
        else:
            # Fallback to channel title if ID not available
            channel_title = video.get('channel_title')
            if channel_title:
                videos_by_channel[channel_title].append(video)
    
    # Select top videos per channel based on total_score
    selected_videos = []
    for channel, channel_videos in videos_by_channel.items():
        # Sort videos by total_score (highest first)
        channel_videos.sort(key=lambda x: x.get('total_score', 0), reverse=True)
        # Take top N videos
        selected_videos.extend(channel_videos[:max_videos_per_channel])
    
    # Sort all selected videos by total_score
    selected_videos.sort(key=lambda x: x.get('total_score', 0), reverse=True)
    
    # Add videos to playlist
    successful_adds = 0
    for video in selected_videos:
        video_id = video['id']
        success = creator.add_video_to_playlist(playlist_id, video_id)
        if success:
            successful_adds += 1
            print(f"Added video: {video.get('title', video_id)} (Score: {video.get('total_score', 'N/A')})")
    
    print(f"Added {successful_adds} of {len(selected_videos)} videos to playlist")
    print(f"Applied channel limit: maximum {max_videos_per_channel} videos per channel")
    
    # Get and display playlist stats
    stats = creator.get_playlist_stats(playlist_id)
    if stats:
        print("\nPlaylist Information:")
        print(f"Title: {stats['title']}")
        print(f"URL: {stats['url']}")
        print(f"Total videos: {stats['item_count']}")
        
        # Count videos per channel
        channels_count = defaultdict(int)
        for item in stats.get('items', []):
            channel = item.get('channel_title', 'Unknown')
            channels_count[channel] += 1
        
        print("\nVideos per channel:")
        for channel, count in channels_count.items():
            print(f"- {channel}: {count}")
        
        print("\nYou can now view this playlist in your YouTube app!")
    
    return playlist_id


# Example usage with command-line interface
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="YouTube Playlist Creator")
    parser.add_argument("--json-file", default="./output/latest_news.json", 
                       help="Path to the JSON file with videos")
    parser.add_argument("--credentials", default="./config/client_secret.json", 
                       help="Path to the OAuth 2.0 client credentials file")
    parser.add_argument("--playlist-id", help="Existing playlist ID to update")
    parser.add_argument("--title", help="Title for a new playlist")
    parser.add_argument("--description", help="Description for a new playlist")
    parser.add_argument("--privacy", default="private", choices=["public", "private", "unlisted"], 
                       help="Privacy status for the playlist")
    parser.add_argument("--max-per-channel", type=int, default=5,
                       help="Maximum number of videos per channel (default: 5)")
    
    args = parser.parse_args()
    
    update_news_playlist(
        json_file=args.json_file,
        credentials_file=args.credentials,
        playlist_id=args.playlist_id,
        playlist_title=args.title,
        playlist_description=args.description,
        privacy_status=args.privacy,
        max_videos_per_channel=args.max_per_channel
    )