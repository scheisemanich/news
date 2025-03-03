#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Video Score Calculator Module for YouTube News Aggregator
Implements scoring criteria for US news channels:
- US channels (CNN, Fox News, Forbes): Quality Score (70%) + Viral Score (30%)
"""

import datetime
import re

class VideoScoreCalculator:
    """
    Calculates quality and viral scores for YouTube videos based on channel-specific criteria.
    """
    
    # Channel IDs for US channels
    CHANNEL_CNN = "UCupvZG-5ko_eiXAupbDfxWw"
    CHANNEL_FOX = "UCXIJgqnII2ZOINSWNOGFThA"
    CHANNEL_FORBES = "UCg40OxZ1GYh3u3jBntB6DLg"
    
    def __init__(self, quality_keywords=None):
        """
        Initialize the score calculator with optional quality keywords for thematic relevance.
        
        Args:
            quality_keywords (list): List of keywords for thematic relevance scoring
        """
        self.quality_keywords = quality_keywords or []
    
    def calculate_scores(self, video_info):
        """
        Calculate quality and viral scores for a video based on its metadata.
        
        Args:
            video_info (dict): Dictionary containing video metadata
            
        Returns:
            tuple: (quality_score, viral_score, total_score)
        """
        # Calculate base scores
        quality_score = self.calculate_quality_score(video_info)
        viral_score = self.calculate_viral_score(video_info)
        
        # Calculate total score - 70% quality score, 30% viral score
        total_score = (0.7 * quality_score) + (0.3 * viral_score)
        
        return (quality_score, viral_score, total_score)
    
    def calculate_quality_score(self, video_info):
        """
        Calculate quality score (70% of total for US channels)
        
        Components:
        - Engagement Rate (25%): (Likes/Views) × 10,000
        - Comment Rate (15%): (Comments/Views) × 10,000
        - Video Length (20%): Optimal 7-20 min
        - Information Depth (15%): Tags count and description length
        - Recency (10%): Higher for newer videos
        - Thematic Relevance (15%): Keywords in title/description
        
        Args:
            video_info (dict): Dictionary containing video metadata
            
        Returns:
            float: Quality score (0-1 scale)
        """
        # 1. Engagement Rate (25%)
        view_count = video_info.get('view_count', 0)
        engagement_rate = 0
        if view_count > 0:
            engagement_rate = (video_info.get('like_count', 0) / view_count) * 10000
            # Normalize to 0-1 scale (assuming 300 is a good engagement rate)
            engagement_score = min(1.0, engagement_rate / 300)
        else:
            engagement_score = 0
        
        # 2. Comment Rate (15%)
        comment_rate = 0
        if view_count > 0:
            comment_rate = (video_info.get('comment_count', 0) / view_count) * 10000
            # Normalize to 0-1 scale (assuming 50 is a good comment rate)
            comment_score = min(1.0, comment_rate / 50)
        else:
            comment_score = 0
        
        # 3. Video Length Score (20%)
        duration_min = video_info.get('duration_seconds', 0) / 60
        if 7 <= duration_min <= 20:
            length_score = 1.0
        elif 3 <= duration_min < 7:
            length_score = 0.7
        elif duration_min > 20:
            length_score = 0.8
        else:  # Less than 3 minutes
            length_score = 0.2
        
        # 4. Information Depth (15%)
        # Tags count (40%)
        tags_count = len(video_info.get('tags', []))
        tags_score = min(1.0, tags_count / 10)  # Normalize to 0-1
        
        # Description length (60%)
        desc_length = len(video_info.get('description', ''))
        desc_score = min(1.0, desc_length / 1000)  # Normalize to 0-1
        
        # Combined info depth score
        info_depth_score = (0.4 * tags_score) + (0.6 * desc_score)
        
        # 5. Recency (10%)
        hours_since_published = video_info.get('hours_since_published', 24)
        # Higher score for newer videos (1.0 for just published, 0.0 for 24+ hours)
        recency_score = max(0, 1.0 - (hours_since_published / 24))
        
        # 6. Thematic Relevance (15%)
        thematic_score = self.calculate_thematic_relevance(
            video_info.get('title', ''),
            video_info.get('description', '')
        )
        
        # Calculate weighted quality score
        quality_score = (
            (0.25 * engagement_score) +
            (0.15 * comment_score) +
            (0.20 * length_score) +
            (0.15 * info_depth_score) +
            (0.10 * recency_score) +
            (0.15 * thematic_score)
        )
        
        return quality_score
    
    def calculate_viral_score(self, video_info):
        """
        Calculate viral score (30% of total for US channels)
        
        Components:
        - Views per hour (60%): (views_per_hour / 1000)
        - Like-to-View ratio (25%): (Likes / Views) * 100
        - Comment-to-View ratio (15%): (Comments / Views) * 100
        
        Args:
            video_info (dict): Dictionary containing video metadata
            
        Returns:
            float: Viral score (0-1 scale)
        """
        # Extract required metrics
        view_count = video_info.get('view_count', 0)
        hours_since_published = max(1, video_info.get('hours_since_published', 24))
        like_count = video_info.get('like_count', 0)
        comment_count = video_info.get('comment_count', 0)
        
        # 1. Views per hour (60%)
        views_per_hour = view_count / hours_since_published
        # Normalize to 0-1 scale (assuming 1000 views/hour is viral)
        views_per_hour_score = min(1.0, views_per_hour / 1000)
        
        # 2. Like-to-View ratio (25%)
        like_view_ratio = 0
        if view_count > 0:
            like_view_ratio = (like_count / view_count) * 100
            # Normalize to 0-1 scale (assuming 5% is good)
            like_view_score = min(1.0, like_view_ratio / 5)
        else:
            like_view_score = 0
        
        # 3. Comment-to-View ratio (15%)
        comment_view_ratio = 0
        if view_count > 0:
            comment_view_ratio = (comment_count / view_count) * 100
            # Normalize to 0-1 scale (assuming 1% is good)
            comment_view_score = min(1.0, comment_view_ratio / 1)
        else:
            comment_view_score = 0
        
        # Calculate weighted viral score
        viral_score = (
            (0.60 * views_per_hour_score) +
            (0.25 * like_view_score) +
            (0.15 * comment_view_score)
        )
        
        return viral_score
    
    def calculate_thematic_relevance(self, title, description):
        """
        Calculate thematic relevance based on keyword matches in title and description
        
        Args:
            title (str): Video title
            description (str): Video description
            
        Returns:
            float: Thematic relevance score (0-1 scale)
        """
        if not self.quality_keywords:
            return 0.5  # Default middle score if no keywords defined
        
        # Combine title and description for matching
        combined_text = (title + ' ' + description).lower()
        
        # Count keyword matches
        match_count = sum(1 for keyword in self.quality_keywords 
                         if keyword.lower() in combined_text)
        
        # Normalize score (0-1)
        # Assuming finding 20% of keywords is good enough for max score
        max_expected_matches = max(1, len(self.quality_keywords) * 0.2)
        relevance_score = min(1.0, match_count / max_expected_matches)
        
        return relevance_score


def apply_scores_to_videos(videos, quality_keywords=None):
    """
    Utility function to apply scores to a list of videos
    
    Args:
        videos (list): List of video info dictionaries
        quality_keywords (list): List of keywords for thematic relevance scoring
        
    Returns:
        list: Same videos with score fields added
    """
    calculator = VideoScoreCalculator(quality_keywords)
    
    for video in videos:
        quality_score, viral_score, total_score = calculator.calculate_scores(video)
        
        # Add scores to video info
        video['quality_score'] = quality_score
        video['viral_score'] = viral_score
        video['total_score'] = total_score
    
    return videos