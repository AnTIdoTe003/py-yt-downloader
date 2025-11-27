#!/usr/bin/env python3
"""
Demo script showing how to use the YouTube Download Link API
with the specific video URL requested by the user.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from youtube_api import YouTubeLinkExtractor
import json

def demo_api():
    """Demo the API with the user's requested YouTube URL"""
    print("🎬 YouTube Download Link API Demo")
    print("=" * 50)

    # The user's requested URL
    video_url = "https://www.youtube.com/watch?v=-VPYbJxPvzY"

    print(f"📺 Getting download links for: {video_url}")
    print()

    # Create extractor
    extractor = YouTubeLinkExtractor()

    # Get video info and download links
    print("⏳ Extracting video information and download links...")
    result = extractor.get_video_info_and_links(video_url, 'best')

    if result:
        print("✅ Success!")
        print()

        # Display video information
        print("📋 Video Information:")
        print(f"   Title: {result['title']}")
        print(f"   Uploader: {result['uploader']}")
        print(".2f")
        print(f"   Views: {result['view_count']:,}")
        print(f"   Upload Date: {result['upload_date']}")
        print(f"   Thumbnail: {result['thumbnail']}")
        print()

        # Display download links
        print("🔗 Download Links:")
        for i, link in enumerate(result['download_links'], 1):
            print(f"   {i}. Quality: {link['quality']}")
            print(f"      Format: {link['format']}")
            print(f"      Resolution: {link['resolution']}")
            print(f"      URL: {link['url'][:80]}...")
            if link['filesize']:
                print(".1f")
            print()

        print("💡 Usage Instructions:")
        print("   - These URLs can be used with video players or download managers")
        print("   - For direct download, you can use tools like wget, curl, or ffmpeg")
        print("   - Example: ffmpeg -i 'URL' -c copy output.mp4")
        print()

        # Example API response format
        print("📤 API Response Format:")
        api_response = {
            "success": True,
            "data": result
        }
        print(json.dumps(api_response, indent=2)[:500] + "...")

    else:
        print("❌ Failed to extract video information")
        print("   This might be due to:")
        print("   - Video is private or unavailable")
        print("   - Regional restrictions")
        print("   - YouTube API changes")

if __name__ == "__main__":
    demo_api()
