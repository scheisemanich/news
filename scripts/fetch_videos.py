#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Integrated YouTube News Aggregator with Scoring
"""

import os
import json
import argparse
from datetime import datetime, timedelta
import time
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# Import the VideoScoreCalculator directly
from score_calculator import VideoScoreCalculator, apply_scores_to_videos

def is_faz_fruehdenker(video_info):
    """
    Check if a video is a FAZ Frühdenker video
    
    Criteria:
    - Upload time between 5:00 and 7:00 AM
    - Title with bullet points (•)
    - Similar length (9-11 minutes)
    - Description starts with "Das Wichtigste" or "Die Nachrichten"
    
    Args:
        video_info (dict): Dictionary containing video metadata
        
    Returns:
        bool: True if matches Frühdenker criteria
    """
    title = video_info.get('title', '')
    
    # Get published time from ISO format
    published_at = video_info.get('published_at', '')
    if published_at:
        try:
            published_time = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
            hour = published_time.hour
            
            # Check time (5-7 AM)
            if not (5 <= hour <= 7):
                return False
        except (ValueError, TypeError):
            return False
    
    # Check for bullet points in title
    if '•' not in title:
        return False
    
    # Check video duration (9-11 minutes)
    duration_sec = video_info.get('duration_seconds', 0)
    duration_min = duration_sec / 60
    if not (8 <= duration_min <= 12):  # Slightly expanded range for flexibility
        return False
    
    # Check description
    description = video_info.get('description', '').lower()
    description_start = description[:30].lower()
    if not (description_start.startswith('das wichtigste') or 
            description_start.startswith('die nachrichten')):
        return False
    
    # All criteria met
    return True

def is_faz_podcast(video_info):
    """
    Check if a video is a FAZ podcast video
    
    Criteria:
    - Contains specific podcast name in title
    - Longer format (>10 minutes)
    - Interview format often with question marks or colons in title
    
    Args:
        video_info (dict): Dictionary containing video metadata
        
    Returns:
        bool: True if matches podcast criteria
    """
    title = video_info.get('title', '').lower()
    
    # Check for podcast keywords
    podcast_keywords = [
        'podcast für deutschland',
        'f.a.z. digitalwirtschaft',
        'f.a.z. einspruch',
        'f.a.z. gesundheit',
        'f.a.z. finanzen & immobilien'
    ]
    
    # Explicit podcast in title
    if any(keyword in title for keyword in podcast_keywords):
        return True
    
    # Check for interview format with longer duration
    duration_sec = video_info.get('duration_seconds', 0)
    duration_min = duration_sec / 60
    
    # Longer videos (typically 20-60 minutes for podcasts)
    if duration_min < 10:
        return False
    
    # Format criteria
    has_interview_format = (':' in title or '?' in title)
    has_expert_format = any(expert + ':' in title.replace(' ', '') for expert in ['interview', 'gespräch', 'experte', 'analyse'])
    
    # Title format checks
    podcast_format = False
    
    # Check common podcast formats
    if ' - ' in title and duration_min >= 20:
        podcast_format = True
    
    # Expert name followed by quote
    if ('"' in title or '"' in title) and duration_min >= 20:
        podcast_format = True
    
    return has_interview_format or has_expert_format or podcast_format

# Define the scopes required for the YouTube Data API
SCOPES = [
    'https://www.googleapis.com/auth/youtube.readonly'
]

class YouTubeNewsAggregator:
    def __init__(self, api_key=None, credentials_file=None, token_file=None):
        """
        Initialize the YouTube News Aggregator.
        
        Args:
            api_key (str, optional): YouTube Data API key
            credentials_file (str, optional): Path to the OAuth 2.0 client credentials file
            token_file (str, optional): Path to save the authorization token
        """
        self.api_key = api_key
        self.credentials_file = credentials_file
        self.token_file = token_file
        self.youtube = None
        
        # Connect to YouTube API
        if api_key:
            self.youtube = build('youtube', 'v3', developerKey=api_key)
        elif credentials_file and token_file:
            self.youtube = self._authenticate_oauth()
        else:
            raise ValueError("Either API key or OAuth credentials must be provided")
    
    def _authenticate_oauth(self):
        """Authenticate with YouTube API using OAuth 2.0."""
        creds = None
        
        # Load existing token if available
        if os.path.exists(self.token_file):
            try:
                creds = Credentials.from_authorized_user_info(
                    json.loads(open(self.token_file, 'r').read()),
                    SCOPES
                )
            except Exception as e:
                print(f"Error loading token: {e}")
        
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
    
    def get_channel_uploads_playlist(self, channel_id):
        """
        Get the uploads playlist ID for a YouTube channel.
        
        Args:
            channel_id (str): YouTube channel ID
            
        Returns:
            str: Uploads playlist ID or None if not found
        """
        try:
            # Get channel details
            channel_response = self.youtube.channels().list(
                part="contentDetails",
                id=channel_id
            ).execute()
            
            # Extract uploads playlist ID
            if "items" in channel_response and channel_response["items"]:
                uploads_playlist_id = channel_response["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
                return uploads_playlist_id
            
            return None
            
        except HttpError as e:
            print(f"Error getting uploads playlist for channel {channel_id}: {e}")
            return None
    
    def get_videos_from_playlist(self, playlist_id, published_after=None, max_results=50):
        """
        Get videos from a YouTube playlist.
        
        Args:
            playlist_id (str): YouTube playlist ID
            published_after (datetime, optional): Only include videos published after this date
            max_results (int, optional): Maximum number of videos to retrieve
            
        Returns:
            list: List of video items
        """
        videos = []
        
        try:
            # Convert datetime to RFC 3339 format for the API
            published_after_str = None
            if published_after:
                published_after_str = published_after.isoformat() + "Z"
            
            # Get videos from playlist
            request = self.youtube.playlistItems().list(
                part="snippet,contentDetails",
                playlistId=playlist_id,
                maxResults=min(50, max_results)  # API limit is 50 per request
            )
            
            # For storing videos that meet the criteria
            total_retrieved = 0
            
            while request and total_retrieved < max_results:
                response = request.execute()
                
                # Process each video
                for item in response.get("items", []):
                    # Extract video details
                    video_id = item["contentDetails"]["videoId"]
                    published_at = item["snippet"]["publishedAt"]
                    published_at_dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
                    
                    # Skip videos published before the cutoff date
                    if published_after and published_at_dt < published_after:
                        continue
                    
                    # Add video to the list
                    videos.append({
                        "id": video_id,
                        "title": item["snippet"]["title"],
                        "description": item["snippet"]["description"],
                        "published_at": published_at,
                        "channel_id": item["snippet"]["channelId"],
                        "channel_title": item["snippet"]["channelTitle"],
                        "thumbnail": item["snippet"]["thumbnails"]["high"]["url"] if "high" in item["snippet"]["thumbnails"] else item["snippet"]["thumbnails"]["default"]["url"]
                    })
                    
                    total_retrieved += 1
                    if total_retrieved >= max_results:
                        break
                
                # Get next page of results
                request = self.youtube.playlistItems().list_next(request, response)
            
            return videos
            
        except HttpError as e:
            print(f"Error getting videos from playlist {playlist_id}: {e}")
            return []
    
    def get_video_details(self, video_ids):
        """
        Get detailed information about YouTube videos.
        
        Args:
            video_ids (list): List of YouTube video IDs
            
        Returns:
            dict: Dictionary mapping video IDs to their details
        """
        video_details = {}
        
        # Process videos in batches of 50 (API limit)
        for i in range(0, len(video_ids), 50):
            batch = video_ids[i:i+50]
            
            try:
                # Get video details
                response = self.youtube.videos().list(
                    part="snippet,contentDetails,statistics",
                    id=",".join(batch)
                ).execute()
                
                # Process each video
                for item in response.get("items", []):
                    video_id = item["id"]
                    
                    # Extract duration in seconds
                    duration = item["contentDetails"]["duration"]
                    duration_seconds = self._parse_duration(duration)
                    
                    # Format duration for display (MM:SS)
                    minutes = duration_seconds // 60
                    seconds = duration_seconds % 60
                    duration_formatted = f"{minutes}:{seconds:02d}"
                    if minutes >= 60:
                        hours = minutes // 60
                        minutes = minutes % 60
                        duration_formatted = f"{hours}:{minutes:02d}:{seconds:02d}"
                    
                    # Extract statistics
                    statistics = item.get("statistics", {})
                    view_count = int(statistics.get("viewCount", 0))
                    like_count = int(statistics.get("likeCount", 0))
                    comment_count = int(statistics.get("commentCount", 0))
                    
                    # Extract tags
                    tags = item["snippet"].get("tags", [])
                    
                    # Calculate hours since published
                    published_at = item["snippet"]["publishedAt"]
                    published_at_dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
                    hours_since_published = (datetime.now().astimezone() - published_at_dt).total_seconds() / 3600
                    
                    # Store details
                    video_details[video_id] = {
                        "duration_seconds": duration_seconds,
                        "duration_formatted": duration_formatted,
                        "view_count": view_count,
                        "like_count": like_count,
                        "comment_count": comment_count,
                        "tags": tags,
                        "hours_since_published": hours_since_published
                    }
            
            except HttpError as e:
                print(f"Error getting video details: {e}")
        
        return video_details
    
    def _parse_duration(self, duration_str):
        """
        Parse ISO 8601 duration string to seconds.
        
        Args:
            duration_str (str): ISO 8601 duration string (e.g., "PT1H2M3S")
            
        Returns:
            int: Duration in seconds
        """
        seconds = 0
        
        # Remove "PT" prefix
        duration_str = duration_str[2:]
        
        # Extract hours, minutes, and seconds
        hours_pos = duration_str.find("H")
        minutes_pos = duration_str.find("M")
        seconds_pos = duration_str.find("S")
        
        if hours_pos != -1:
            hours = int(duration_str[:hours_pos])
            seconds += hours * 3600
            duration_str = duration_str[hours_pos+1:]
            minutes_pos = duration_str.find("M")
            seconds_pos = duration_str.find("S")
        
        if minutes_pos != -1:
            minutes = int(duration_str[:minutes_pos])
            seconds += minutes * 60
            duration_str = duration_str[minutes_pos+1:]
            seconds_pos = duration_str.find("S")
        
        if seconds_pos != -1:
            seconds += int(duration_str[:seconds_pos])
        
        return seconds
    
    def get_news_videos(self, channels, days_back=1, max_results=20):
        """
        Get recent news videos from multiple YouTube channels.
        
        Args:
            channels (list): List of YouTube channel IDs
            days_back (int, optional): Number of days to look back for videos
            max_results (int, optional): Maximum number of videos per channel
            
        Returns:
            list: List of news videos with details
        """
        all_videos = []
        
        # Calculate the cutoff date for recent videos
        published_after = datetime.now().astimezone() - timedelta(days=days_back)
        
        for channel_id in channels:
            print(f"Processing channel: {channel_id}")
            
            # Get uploads playlist ID for the channel
            uploads_playlist_id = self.get_channel_uploads_playlist(channel_id)
            if not uploads_playlist_id:
                print(f"Skipping channel {channel_id}: No uploads playlist found")
                continue
            
            # Get videos from the uploads playlist
            channel_videos = self.get_videos_from_playlist(
                uploads_playlist_id,
                published_after=published_after,
                max_results=max_results
            )
            
            print(f"Found {len(channel_videos)} recent videos from channel {channel_id}")
            all_videos.extend(channel_videos)
        
        # Get detailed information about the videos
        if all_videos:
            video_ids = [video["id"] for video in all_videos]
            video_details = self.get_video_details(video_ids)
            
            # Add details to videos
            for video in all_videos:
                video_id = video["id"]
                if video_id in video_details:
                    video.update(video_details[video_id])
        
        return all_videos


def run_news_aggregator(config, output_dir="output/"):
    """
    Run the YouTube News Aggregator.
    
    Args:
        config (dict): Configuration dictionary
        output_dir (str, optional): Output directory for results
    """
    # Extract configuration parameters
    api_key = config.get("api_key")
    channels = config.get("channels", [])
    days_back = config.get("days_back", 1)
    max_results = config.get("max_results", 20)
    quality_keywords = config.get("quality_keywords", [])
    
    # Initialize the aggregator
    aggregator = YouTubeNewsAggregator(api_key=api_key)
    
    # Get news videos
    print(f"Collecting videos from {len(channels)} channels...")
    print(f"- Looking back {days_back} days")
    print(f"- Max {max_results} videos per channel")
    
    videos = aggregator.get_news_videos(
        channels=channels,
        days_back=days_back,
        max_results=max_results
    )
    
    print(f"Total videos collected: {len(videos)}")
    
    # Separate videos by channel type
    us_channels = ["UCupvZG-5ko_eiXAupbDfxWw", "UCXIJgqnII2ZOINSWNOGFThA", "UCg40OxZ1GYh3u3jBntB6DLg"]  # CNN, Fox News, Forbes
    german_channels = ["UCMpW4tdyZUid2Ka9_FuDDhQ", "UCcPcua2PF7hzik2TeOBx3uw"]  # Handelsblatt, FAZ
    
    us_videos = [v for v in videos if v.get('channel_id') in us_channels]
    german_videos = [v for v in videos if v.get('channel_id') in german_channels]
    
    print(f"US channel videos: {len(us_videos)}")
    print(f"German channel videos: {len(german_videos)}")
    
    # Process US videos with Score Calculator
    print("Applying scores to US channel videos...")
    scored_us_videos = apply_scores_to_videos(us_videos, quality_keywords)
    
    # Sort US videos by total score (highest first)
    scored_us_videos.sort(key=lambda x: x.get('total_score', 0), reverse=True)
    
    # Filter German videos based on specific criteria
    filtered_german_videos = []
    
    for video in german_videos:
        channel_id = video.get('channel_id')
        
        # Handelsblatt criteria (Podcasts and content with Koch)
        if channel_id == "UCMpW4tdyZUid2Ka9_FuDDhQ":  # Handelsblatt
            title = video.get('title', '').lower()
            description = video.get('description', '').lower()
            
            # Check for Koch content
            if 'koch' in title or 'koch' in description:
                filtered_german_videos.append(video)
                print(f"✓ Handelsblatt Koch video: {video.get('title')}")
        
        # FAZ criteria (Frühdenker videos and Podcasts)
        elif channel_id == "UCcPcua2PF7hzik2TeOBx3uw":  # FAZ
            if is_faz_fruehdenker(video) or is_faz_podcast(video):
                filtered_german_videos.append(video)
                print(f"✓ FAZ selected video: {video.get('title')}")
    
    print(f"German videos after filtering: {len(filtered_german_videos)}")
    
    # Limit US videos to maximum 5 per channel
    max_videos_per_channel = config.get("max_videos_per_channel", 5)
    channel_counts = {}
    filtered_us_videos = []
    
    for video in scored_us_videos:
        channel_id = video.get('channel_id')
        if channel_id not in channel_counts:
            channel_counts[channel_id] = 0
        
        if channel_counts[channel_id] < max_videos_per_channel:
            filtered_us_videos.append(video)
            channel_counts[channel_id] += 1
    
    print(f"US videos after filtering: {len(filtered_us_videos)}")
    
    # Combine filtered videos from both types of channels
    filtered_videos = filtered_us_videos + filtered_german_videos
    
    # Limit the total number of videos to 25
    if len(filtered_videos) > 25:
        # If we need to trim, keep all German videos and trim US videos as needed
        if len(filtered_german_videos) <= 25:
            us_videos_to_keep = 25 - len(filtered_german_videos)
            filtered_videos = filtered_us_videos[:us_videos_to_keep] + filtered_german_videos
        else:
            # If we have more than 25 German videos (unlikely), keep only the first 25
            filtered_videos = filtered_german_videos[:25]
    
    print(f"Final video count: {len(filtered_videos)}")
    
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Save results to JSON file
    json_file = os.path.join(output_dir, "latest_news.json")
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(filtered_videos, f, indent=2, ensure_ascii=False)
    
    print(f"Results saved to {json_file}")
    
    # Removed backup code that created previous_news.json
    
    return filtered_videos


def main():
    parser = argparse.ArgumentParser(description="YouTube News Aggregator")
    parser.add_argument("--load-config", help="Path to the configuration file")
    parser.add_argument("--api-key", help="YouTube Data API key")
    parser.add_argument("--channels", nargs="+", help="YouTube channel IDs")
    parser.add_argument("--days-back", type=int, default=1, help="Number of days to look back")
    parser.add_argument("--max-results", type=int, default=20, help="Maximum results per channel")
    parser.add_argument("--output-dir", default="output/", help="Output directory")
    parser.add_argument("--max-videos-per-channel", type=int, default=5, help="Maximum videos per channel")
    parser.add_argument("--json-file", help="Output JSON file path")
    parser.add_argument("--credentials", help="Path to OAuth credentials file")
    parser.add_argument("--now", action="store_true", help="Use current time instead of specified update time")
    
    args = parser.parse_args()
    
    # Load configuration from file if specified
    config = {}
    if args.load_config:
        try:
            with open(args.load_config, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except Exception as e:
            print(f"Error loading configuration file: {e}")
            return
    
    # Override configuration with command line arguments
    if args.api_key:
        config["api_key"] = args.api_key
    if args.channels:
        config["channels"] = args.channels
    if args.days_back:
        config["days_back"] = args.days_back
    if args.max_results:
        config["max_results"] = args.max_results
    if args.max_videos_per_channel:
        config["max_videos_per_channel"] = args.max_videos_per_channel
    
    # Validate configuration
    if not config.get("api_key"):
        print("Error: YouTube API key is required")
        return
    
    if not config.get("channels"):
        print("Error: At least one YouTube channel ID is required")
        return
    
    # Determine output directory
    output_dir = args.output_dir if args.output_dir else config.get("output_dir", "output/")
    
    # Run the aggregator
    run_news_aggregator(config, output_dir)


if __name__ == "__main__":
    main()