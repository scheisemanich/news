import os
import json
import datetime
import argparse
import time
import schedule
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

class YouTubeNewsAggregator:
    def __init__(self, api_key, channels=None, min_duration_minutes=15, max_results=10):
        """
        Initialize the YouTube News Aggregator.
        
        Args:
            api_key (str): Your YouTube Data API key
            channels (list): List of channel IDs or usernames to monitor
            min_duration_minutes (int): Minimum video duration in minutes
            max_results (int): Maximum number of results per channel
        """
        self.api_key = api_key
        self.channels = channels or []
        self.min_duration_seconds = min_duration_minutes * 60
        self.max_results = max_results
        self.youtube = build('youtube', 'v3', developerKey=api_key)
        
    def add_channel(self, channel_id_or_username):
        """Add a channel to the monitoring list."""
        if channel_id_or_username not in self.channels:
            self.channels.append(channel_id_or_username)
            
    def remove_channel(self, channel_id_or_username):
        """Remove a channel from the monitoring list."""
        if channel_id_or_username in self.channels:
            self.channels.remove(channel_id_or_username)
    
    def _resolve_channel_id(self, channel_id_or_username):
        """Resolve a channel username to its ID if needed."""
        # If it looks like a channel ID, return it directly
        if channel_id_or_username.startswith('UC'):
            return channel_id_or_username
            
        # Otherwise, try to resolve the username
        try:
            response = self.youtube.channels().list(
                part='id',
                forUsername=channel_id_or_username
            ).execute()
            
            if response['items']:
                return response['items'][0]['id']
            else:
                print(f"Could not resolve username: {channel_id_or_username}")
                return None
        except HttpError as e:
            print(f"Error resolving channel ID: {e}")
            return None
    
    def _get_video_details(self, video_ids):
        """Get detailed information about specific videos."""
        if not video_ids:
            return []
            
        results = []
        # Process in batches of 50 (API limit)
        for i in range(0, len(video_ids), 50):
            batch = video_ids[i:i+50]
            try:
                response = self.youtube.videos().list(
                    part='snippet,contentDetails,statistics',
                    id=','.join(batch)
                ).execute()
                
                for item in response.get('items', []):
                    duration = self._parse_duration(item['contentDetails']['duration'])
                    if duration >= self.min_duration_seconds:
                        published_at = datetime.datetime.fromisoformat(
                            item['snippet']['publishedAt'].replace('Z', '+00:00')
                        )
                        
                        results.append({
                            'id': item['id'],
                            'title': item['snippet']['title'],
                            'channel_title': item['snippet']['channelTitle'],
                            'published_at': published_at.isoformat(),
                            'thumbnail': item['snippet']['thumbnails']['high']['url'],
                            'duration_seconds': duration,
                            'duration_formatted': self._format_duration(duration),
                            'view_count': int(item['statistics'].get('viewCount', 0)),
                            'like_count': int(item['statistics'].get('likeCount', 0)),
                            'url': f"https://www.youtube.com/watch?v={item['id']}"
                        })
            except HttpError as e:
                print(f"Error fetching video details: {e}")
                
        return results
        
    def _parse_duration(self, duration_str):
        """Parse ISO 8601 duration format to seconds."""
        duration = 0
        # Remove the "PT" prefix
        time_str = duration_str[2:]
        
        # Hours
        if 'H' in time_str:
            h_index = time_str.index('H')
            hours = int(time_str[:h_index])
            duration += hours * 3600
            time_str = time_str[h_index+1:]
            
        # Minutes
        if 'M' in time_str:
            m_index = time_str.index('M')
            minutes = int(time_str[:m_index])
            duration += minutes * 60
            time_str = time_str[m_index+1:]
            
        # Seconds
        if 'S' in time_str:
            s_index = time_str.index('S')
            seconds = int(time_str[:s_index])
            duration += seconds
            
        return duration
    
    def _format_duration(self, seconds):
        """Format seconds into a readable duration string."""
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes}:{seconds:02d}"
    
    def get_latest_videos(self, days_back=7):
        """
        Get the latest news videos from all monitored channels.
        
        Args:
            days_back (int): How many days back to search
            
        Returns:
            list: A list of video information dictionaries sorted by publish date
        """
        all_videos = []
        
        for channel in self.channels:
            channel_id = self._resolve_channel_id(channel)
            if not channel_id:
                continue
                
            try:
                # Get uploads playlist ID for the channel
                channel_response = self.youtube.channels().list(
                    part='contentDetails',
                    id=channel_id
                ).execute()
                
                if not channel_response.get('items'):
                    print(f"No channel found for ID: {channel_id}")
                    continue
                    
                uploads_playlist_id = channel_response['items'][0]['contentDetails']['relatedPlaylists']['uploads']
                
                # Get recent uploads
                published_after = (datetime.datetime.now() - datetime.timedelta(days=days_back)).isoformat() + 'Z'
                
                playlist_response = self.youtube.playlistItems().list(
                    part='snippet',
                    playlistId=uploads_playlist_id,
                    maxResults=self.max_results
                ).execute()
                
                video_ids = [item['snippet']['resourceId']['videoId'] 
                            for item in playlist_response.get('items', [])]
                
                # Get detailed information and filter by duration
                channel_videos = self._get_video_details(video_ids)
                all_videos.extend(channel_videos)
                
            except HttpError as e:
                print(f"Error fetching videos for channel {channel}: {e}")
        
        # Sort by publish date (newest first)
        all_videos.sort(key=lambda x: x['published_at'], reverse=True)
        return all_videos
    
    def export_to_json(self, videos, filename="latest_news.json"):
        """Export video results to a JSON file."""
        # Ensure directory exists
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(videos, f, ensure_ascii=False, indent=2)
        print(f"Exported {len(videos)} videos to {filename}")
    
    def export_to_html(self, videos, filename="latest_news.html"):
        """Export video results to a simple HTML page."""
        # Ensure directory exists
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Latest News Videos</title>
            <style>
                body { font-family: Arial, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; }
                .video-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 20px; }
                .video-card { border: 1px solid #ddd; border-radius: 8px; overflow: hidden; }
                .video-card img { width: 100%%; height: auto; }
                .video-info { padding: 15px; }
                .video-title { font-weight: bold; margin-bottom: 10px; }
                .video-meta { color: #666; font-size: 0.9em; }
                .video-duration { font-weight: bold; color: #333; }
                .updated-time { text-align: right; margin: 20px 0; color: #666; }
            </style>
        </head>
        <body>
            <h1>Latest News Videos</h1>
            <div class="updated-time">Updated: %s</div>
            <div class="video-grid">
        """ % datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        for video in videos:
            html += """
                <div class="video-card">
                    <a href="%s" target="_blank">
                        <img src="%s" alt="%s">
                        <div class="video-info">
                            <div class="video-title">%s</div>
                            <div class="video-meta">
                                <div>%s</div>
                                <div>%s views</div>
                                <div class="video-duration">Duration: %s</div>
                            </div>
                        </div>
                    </a>
                </div>
            """ % (
                video['url'],
                video['thumbnail'],
                video['title'],
                video['title'],
                video['channel_title'],
                "{:,}".format(video['view_count']),
                video['duration_formatted']
            )
        
        html += """
            </div>
        </body>
        </html>
        """
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"Exported {len(videos)} videos to {filename}")


def update_news_feed(api_key, channels, min_duration=15, days_back=3, max_results=20, output_dir="./output/"):
    """Update the news feed and generate output files."""
    print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Updating news feed...")
    
    # Stelle sicher, dass output_dir kein absoluter Pfad ist
    if output_dir.startswith('/'):
        # Konvertiere absoluten Pfad zu relativen Pfad
        print(f"Warnung: Absoluter Pfad '{output_dir}' erkannt. Verwende stattdessen relativen Pfad './output/'.")
        output_dir = "./output/"
    
    aggregator = YouTubeNewsAggregator(
        api_key=api_key,
        min_duration_minutes=min_duration,
        max_results=max_results
    )
    
    for channel in channels:
        aggregator.add_channel(channel)
    
    latest_videos = aggregator.get_latest_videos(days_back=days_back)
    
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Export results
    json_path = os.path.join(output_dir, "latest_news.json")
    html_path = os.path.join(output_dir, "latest_news.html")
    
    aggregator.export_to_json(latest_videos, filename=json_path)
    aggregator.export_to_html(latest_videos, filename=html_path)
    
    print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Found {len(latest_videos)} news videos matching your criteria.")
    print(f"Output saved to {html_path} and {json_path}")
    return latest_videos

def start_scheduler(api_key, channels, min_duration=15, days_back=3, max_results=20, 
                   output_dir="./output/", update_time="08:00", run_once=False):
    """Start the scheduler for regular updates."""
    # Ensure output directory exists
    if output_dir.startswith('/'):
        # Konvertiere absoluten Pfad zu relativen Pfad
        print(f"Warnung: Absoluter Pfad '{output_dir}' erkannt. Verwende stattdessen relativen Pfad './output/'.")
        output_dir = "./output/"
        
    os.makedirs(output_dir, exist_ok=True)
    
    if run_once:
        update_news_feed(api_key, channels, min_duration, days_back, max_results, output_dir)
        return
    
    # Schedule daily update
    schedule.every().day.at(update_time).do(
        update_news_feed, api_key, channels, min_duration, days_back, max_results, output_dir
    )
    
    print(f"Scheduler started. Will update daily at {update_time}.")
    print("Press Ctrl+C to stop.")
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    except KeyboardInterrupt:
        print("Scheduler stopped.")

def save_config(config, filename="config.json"):
    """Save configuration to a JSON file."""
    # Stelle sicher, dass config kein absoluter Pfad für output_dir enthält
    if 'output_dir' in config and config['output_dir'].startswith('/'):
        config['output_dir'] = "./output/"
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    print(f"Configuration saved to {filename}")

def load_config(filename="config.json"):
    """Load configuration from a JSON file."""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            config = json.load(f)
            
        # Stelle sicher, dass der Pfad kein absoluter Pfad ist
        if 'output_dir' in config and config['output_dir'].startswith('/'):
            config['output_dir'] = "./output/"
            print(f"Warnung: Absoluter Pfad in config erkannt. Verwende stattdessen relativen Pfad './output/'.")
            
        return config
    except FileNotFoundError:
        return None

# Example usage with command-line interface
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="YouTube News Aggregator")
    parser.add_argument("--api-key", help="YouTube API Key")
    parser.add_argument("--min-duration", type=int, default=15, help="Minimum video duration in minutes")
    parser.add_argument("--days-back", type=int, default=3, help="How many days back to search")
    parser.add_argument("--max-results", type=int, default=20, help="Maximum results per channel")
    parser.add_argument("--output-dir", default="./output/", help="Directory for output files")
    parser.add_argument("--update-time", default="08:00", help="Daily update time (24h format)")
    parser.add_argument("--channels", nargs="+", help="List of channel IDs or usernames")
    parser.add_argument("--now", action="store_true", help="Run update immediately")
    parser.add_argument("--save-config", help="Save configuration to file")
    parser.add_argument("--load-config", help="Load configuration from file")
    parser.add_argument("--schedule", action="store_true", help="Run as a scheduled service")
    
    args = parser.parse_args()
    
    # Überprüfe, ob output_dir ein absoluter Pfad ist
    if args.output_dir and args.output_dir.startswith('/'):
        print(f"Warnung: Absoluter Pfad '{args.output_dir}' wird nicht unterstützt. Verwende stattdessen relativen Pfad './output/'.")
        args.output_dir = "./output/"
    
    # Load configuration if specified
    config = None
    if args.load_config:
        config = load_config(args.load_config)
        if config:
            print(f"Loaded configuration from {args.load_config}")
    
    # Use arguments or config values
    api_key = args.api_key or (config and config.get("api_key")) or os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        print("Error: YouTube API Key is required. Provide it via --api-key argument, config file, or YOUTUBE_API_KEY environment variable.")
        exit(1)
    
    channels = args.channels or (config and config.get("channels")) or [
        "CNNInternational",
        "BBCNews",
        "DeutscheWelleEnglish",
        # Add your preferred channels here
    ]
    
    min_duration = args.min_duration or (config and config.get("min_duration", 15))
    days_back = args.days_back or (config and config.get("days_back", 3))
    max_results = args.max_results or (config and config.get("max_results", 20))
    # Stelle sicher, dass output_dir ein relativer Pfad ist
    output_dir = args.output_dir or (config and config.get("output_dir", "./output/"))
    if output_dir.startswith('/'):
        output_dir = "./output/"
    
    update_time = args.update_time or (config and config.get("update_time", "08:00"))
    
    # Save configuration if specified
    if args.save_config:
        save_config({
            "api_key": api_key,
            "channels": channels,
            "min_duration": min_duration,
            "days_back": days_back,
            "max_results": max_results,
            "output_dir": output_dir,
            "update_time": update_time
        }, args.save_config)
    
    # Run update now or start scheduler
    if args.schedule:
        start_scheduler(api_key, channels, min_duration, days_back, max_results, output_dir, update_time)
    else:
        # Always run once if not scheduling
        update_news_feed(api_key, channels, min_duration, days_back, max_results, output_dir)
