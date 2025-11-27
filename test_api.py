#!/usr/bin/env python3
"""
Test script for YouTube Download Link API
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from youtube_api import YouTubeLinkExtractor
import json

def test_api():
    """Test the API functionality"""
    print("Testing YouTube Download Link API...")

    # Test URL
    test_url = "https://www.youtube.com/watch?v=-VPYbJxPvzY"

    # Create extractor
    extractor = YouTubeLinkExtractor()

    # Test URL validation
    print(f"URL validation for {test_url}: {extractor.validate_url(test_url)}")

    # Test getting video info and links
    print("Extracting video information and download links...")
    result = extractor.get_video_info_and_links(test_url, 'best')

    if result:
        print("✅ Success! Video information extracted:")
        print(json.dumps(result, indent=2))
    else:
        print("❌ Failed to extract video information")

if __name__ == "__main__":
    test_api()
