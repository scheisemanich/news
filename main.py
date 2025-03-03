#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YouTube News Aggregator Pipeline

This script orchestrates the complete news aggregation pipeline:
1. Fetches videos from configured YouTube channels
2. Scores and filters videos based on channel-specific criteria
3. Updates a YouTube playlist with the selected videos

Usage:
  python main.py
"""

import os
import json
import argparse
import sys
import subprocess
import time

def read_api_key(filepath="config/api_key.txt"):
    """Read the YouTube API key from file."""
    try:
        with open(filepath, 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        print(f"Error: API key file not found at {filepath}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Run YouTube News Aggregator Pipeline")
    parser.add_argument("--skip-fetch", action="store_true", help="Skip the fetch videos step")
    parser.add_argument("--skip-update", action="store_true", help="Skip the playlist update step")
    args = parser.parse_args()
    
    print("=" * 50)
    print("STARTING YOUTUBE NEWS AGGREGATOR PIPELINE")
    print("=" * 50)
    
    # Ensure output directory exists
    os.makedirs("output", exist_ok=True)
    
    # Step 1: Fetch and score videos
    if not args.skip_fetch:
        print("\n[STEP 1/2] Fetching and scoring videos...")
        api_key = read_api_key()
        
        # Define channels to fetch from
        channels = [
            "UCupvZG-5ko_eiXAupbDfxWw",  # CNN
            "UCXIJgqnII2ZOINSWNOGFThA",  # Fox News
            "UCg40OxZ1GYh3u3jBntB6DLg",  # Forbes
            "UCMpW4tdyZUid2Ka9_FuDDhQ",  # Handelsblatt
            "UCcPcua2PF7hzik2TeOBx3uw"   # FAZ
        ]
        
        # Quality keywords for scoring
        quality_keywords = [
            "economy", "market", "stocks", "finance", "business", "technology",
            "politics", "policy", "health", "science", "education", "analysis",
            "wirtschaft", "markt", "aktien", "finanzen", "technologie", "politik",
            "gesundheit", "wissenschaft", "bildung", "analyse"
        ]
        
        # Create config dictionary
        config = {
            "api_key": api_key,
            "channels": channels,
            "days_back": 1,
            "max_results": 20,
            "max_videos_per_channel": 5,
            "quality_keywords": quality_keywords,
            "output_dir": "output/"
        }
        
        # Save config to temporary file
        with open("output/temp_config.json", 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
        
        try:
            # Run the fetch-videos.py script
            print("Running fetch-videos.py...")
            subprocess.run([sys.executable, "scripts/fetch_videos.py", 
               "--load-config", "output/temp_config.json"], check=True)
        except subprocess.CalledProcessError as e:
            print(f"Error running fetch-videos.py: {e}")
            sys.exit(1)
        finally:
            # Clean up temporary config file
            if os.path.exists("output/temp_config.json"):
                os.remove("output/temp_config.json")
    else:
        print("\n[STEP 1/2] Skipping fetch videos step...")
    
    # Step 2: Update playlist
    if not args.skip_update:
        print("\n[STEP 2/2] Updating YouTube playlist...")
        
        if not os.path.exists("output/latest_news.json"):
            print("Error: output/latest_news.json not found. Run with --skip-update to skip this step.")
            sys.exit(1)
        
        try:
            # Run the update-news-playlist.py script
            print("Running update-news-playlist.py...")
            subprocess.run([sys.executable, "scripts/update-news-playlist.py", 
                           "--json-file", "output/latest_news.json"], check=True)
        except subprocess.CalledProcessError as e:
            print(f"Error running update-news-playlist.py: {e}")
            sys.exit(1)
    else:
        print("\n[STEP 2/2] Skipping playlist update step...")
    
    print("\n" + "=" * 50)
    print("PIPELINE COMPLETED SUCCESSFULLY")
    print("=" * 50)

if __name__ == "__main__":
    start_time = time.time()
    main()
    elapsed_time = time.time() - start_time
    print(f"\nTotal execution time: {elapsed_time:.2f} seconds")