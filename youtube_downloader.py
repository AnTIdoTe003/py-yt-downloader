#!/usr/bin/env python3
"""
YouTube Video/Shorts Downloader Tool
====================================

LEGAL WARNING:
This tool is for educational purposes only. Downloading YouTube videos
may violate YouTube's Terms of Service. Always ensure you have permission
to download and use the content.

Requirements:
pip install yt-dlp

Usage:
python youtube_downloader.py "https://www.youtube.com/watch?v=VIDEO_ID"
"""

import os
import sys
import argparse
from pathlib import Path

try:
    import yt_dlp
except ImportError:
    print("Error: yt-dlp not installed. Install with: pip install yt-dlp")
    sys.exit(1)


class YouTubeDownloader:
    def __init__(self, output_dir="downloads"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

    def get_video_info(self, url):
        """Get video information without downloading"""
        try:
            with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                info = ydl.extract_info(url, download=False)
                return {
                    'title': info.get('title', 'Unknown'),
                    'uploader': info.get('uploader', 'Unknown'),
                    'duration': info.get('duration', 0),
                    'view_count': info.get('view_count', 0),
                    'upload_date': info.get('upload_date', 'Unknown'),
                    'formats': self._get_available_formats(info)
                }
        except Exception as e:
            print(f"Error getting video info: {e}")
            return None

    def _get_available_formats(self, info):
        """Get available download formats"""
        formats = []
        for f in info.get('formats', []):
            if f.get('ext') in ['mp4', 'webm'] and f.get('vcodec') != 'none':
                formats.append({
                    'format_id': f.get('format_id'),
                    'ext': f.get('ext'),
                    'resolution': f.get('resolution', 'unknown'),
                    'filesize': f.get('filesize', 0),
                    'vcodec': f.get('vcodec'),
                    'acodec': f.get('acodec')
                })
        return formats

    def download_video(self, url, format_id=None, quality='best'):
        """Download video with specified quality"""

        # Configure yt-dlp options
        ydl_opts = {
            'outtmpl': str(self.output_dir / '%(title)s.%(ext)s'),
            'noplaylist': True,  # Only download single video, not playlist
        }

        if format_id:
            ydl_opts['format'] = format_id
        elif quality == 'best':
            ydl_opts['format'] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
        elif quality == 'audio':
            ydl_opts['format'] = 'bestaudio/best'
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                print(f"Downloading to: {self.output_dir}")
                ydl.download([url])
                print("Download completed successfully!")
                return True
        except Exception as e:
            print(f"Error downloading video: {e}")
            return False

    def list_formats(self, url):
        """List available download formats for a video"""
        info = self.get_video_info(url)
        if not info:
            return

        print(f"\nTitle: {info['title']}")
        print(f"Uploader: {info['uploader']}")
        print(".2f")
        print(f"Views: {info['view_count']:,}")
        print(f"Upload Date: {info['upload_date']}")
        print("\nAvailable Formats:")

        for fmt in info['formats']:
            size_mb = fmt['filesize'] / (1024 * 1024) if fmt['filesize'] else 0
            print(f"  ID: {fmt['format_id']} | {fmt['resolution']} | {fmt['ext']} | "
                  ".1f")


def main():
    parser = argparse.ArgumentParser(description='Download YouTube videos and shorts')
    parser.add_argument('url', help='YouTube video URL')
    parser.add_argument('-o', '--output', default='downloads',
                       help='Output directory (default: downloads)')
    parser.add_argument('-q', '--quality', choices=['best', 'audio'],
                       default='best', help='Download quality (default: best)')
    parser.add_argument('-f', '--format', help='Specific format ID to download')
    parser.add_argument('-l', '--list', action='store_true',
                       help='List available formats without downloading')
    parser.add_argument('-i', '--info', action='store_true',
                       help='Show video information without downloading')

    args = parser.parse_args()

    downloader = YouTubeDownloader(args.output)

    # Validate URL
    if not any(domain in args.url.lower() for domain in ['youtube.com', 'youtu.be']):
        print("Error: Please provide a valid YouTube URL")
        sys.exit(1)

    if args.list or args.info:
        info = downloader.get_video_info(args.url)
        if info and args.info:
            print(f"\nTitle: {info['title']}")
            print(f"Uploader: {info['uploader']}")
            print(".2f")
            print(f"Views: {info['view_count']:,}")
            print(f"Upload Date: {info['upload_date']}")

        if args.list:
            downloader.list_formats(args.url)
    else:
        print("Starting download...")
        success = downloader.download_video(args.url, args.format, args.quality)
        if success:
            print(f"\nVideo downloaded to: {downloader.output_dir}")
        else:
            sys.exit(1)


if __name__ == "__main__":
    main()
