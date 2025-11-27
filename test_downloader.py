#!/usr/bin/env python3
"""
Simple test script for YouTube downloader
This demonstrates the basic functionality without actually downloading
"""

from youtube_downloader import YouTubeDownloader

def test_downloader():
    # Create downloader instance
    downloader = YouTubeDownloader("test_downloads")

    # Test with a sample YouTube URL (this won't download, just shows info)
    test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # Rick Roll

    print("Testing YouTube Downloader Tool")
    print("=" * 40)

    print(f"Test URL: {test_url}")
    print("\nGetting video information...")

    # Get video info
    info = downloader.get_video_info(test_url)

    if info:
        print("✅ Successfully retrieved video info!")
        print(f"Title: {info['title']}")
        print(f"Uploader: {info['uploader']}")
        print(".2f")
        print(f"Views: {info['view_count']:,}")
        print(f"Available formats: {len(info['formats'])}")

        print("\nFirst 3 available formats:")
        for i, fmt in enumerate(info['formats'][:3]):
            size_mb = fmt['filesize'] / (1024 * 1024) if fmt['filesize'] else 0
            print(f"  {i+1}. {fmt['resolution']} {fmt['ext']} - "
                  ".1f")
    else:
        print("❌ Failed to get video information")
        print("Note: This might be due to network restrictions in the test environment")

    print("\nTo use the full tool:")
    print("1. Install yt-dlp: pip install yt-dlp")
    print("2. Run: python youtube_downloader.py 'YOUR_YOUTUBE_URL'")
    print("3. Add -l flag to list formats: python youtube_downloader.py 'URL' -l")

if __name__ == "__main__":
    test_downloader()
