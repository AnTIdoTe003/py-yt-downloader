#!/usr/bin/env python3
"""
YouTube Video Download Link API
===============================

A REST API that accepts YouTube URLs and returns downloadable video links.

LEGAL WARNING:
This tool is for educational purposes only. Downloading YouTube videos
may violate YouTube's Terms of Service. Always ensure you have permission
to download and use the content.

Requirements:
pip install yt-dlp flask

Usage:
python youtube_api.py

API Endpoint:
POST /api/download-links
Content-Type: application/json

Request body:
{
    "url": "https://www.youtube.com/watch?v=VIDEO_ID",
    "quality": "best"  // optional: "best" or "audio"
}

Response:
{
    "success": true,
    "data": {
        "title": "Video Title",
        "uploader": "Uploader Name",
        "duration": 300,
        "view_count": 1000000,
        "upload_date": "20231201",
        "download_links": [
            {
                "quality": "720p",
                "format": "mp4",
                "url": "https://...",
                "filesize": 50000000,
                "headers": {
                    "User-Agent": "...",
                    "Referer": "https://www.youtube.com/",
                    "Accept-Language": "..."
                },
                "requires_headers": true
            }
        ]
    }
}
"""

import os
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Dict, Any, Optional
from flask import Flask, request, jsonify, send_file, after_this_request

try:
    import yt_dlp
except ImportError:
    print("Error: yt-dlp not installed. Install with: pip install yt-dlp")
    sys.exit(1)

try:
    from flask import Flask
except ImportError:
    print("Error: flask not installed. Install with: pip install flask")
    sys.exit(1)


def _build_common_ydl_opts(extra_opts: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Build a yt-dlp options dict with headers/cookies support"""
    opts: Dict[str, Any] = {
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'restrictfilenames': True,
    }

    cookie_file = os.getenv('YDL_COOKIES')
    if cookie_file:
        cookie_path = Path(cookie_file).expanduser()
        if cookie_path.exists():
            opts['cookiefile'] = str(cookie_path)
        else:
            print(f"Warning: cookie file {cookie_path} not found. Continuing without cookies.")

    user_agent = os.getenv(
        'YDL_USER_AGENT',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
        'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    )
    accept_language = os.getenv('YDL_ACCEPT_LANGUAGE', 'en-US,en;q=0.9')

    opts['http_headers'] = {
        'User-Agent': user_agent,
        'Accept-Language': accept_language,
        'Referer': 'https://www.youtube.com/',
        'Accept': '*/*'
    }

    proxy = os.getenv('YDL_PROXY')
    if proxy:
        opts['proxy'] = proxy

    if extra_opts:
        opts.update(extra_opts)

    return opts


class YouTubeLinkExtractor:
    def __init__(self):
        pass

    def get_video_info_and_links(self, url, quality='best'):
        """Get video information and downloadable links"""
        try:
            # Configure yt-dlp options to get URLs without downloading
            ydl_opts = _build_common_ydl_opts()

            # Get headers for download requests
            headers = ydl_opts.get('http_headers', {})

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Extract info without downloading
                info = ydl.extract_info(url, download=False)

                # Get available formats with headers
                formats = self._get_downloadable_formats(info, quality, headers)

                return {
                    'title': info.get('title', 'Unknown'),
                    'uploader': info.get('uploader', 'Unknown'),
                    'duration': info.get('duration', 0),
                    'view_count': info.get('view_count', 0),
                    'upload_date': info.get('upload_date', 'Unknown'),
                    'thumbnail': info.get('thumbnail', ''),
                    'download_links': formats
                }

        except Exception as e:
            print(f"Error extracting video info: {e}")
            return None

    def _get_downloadable_formats(self, info, quality, headers):
        """Get downloadable format URLs with required headers"""
        formats = []

        if quality == 'audio':
            # Get best audio format
            audio_format = None
            for f in info.get('formats', []):
                if f.get('acodec') != 'none' and f.get('vcodec') == 'none':
                    if not audio_format or f.get('abr', 0) > audio_format.get('abr', 0):
                        audio_format = f

            if audio_format:
                # Get the actual download URL - prioritize direct URL
                download_url = audio_format.get('url', '')
                if not download_url:
                    # Try fragment base URL as fallback
                    download_url = audio_format.get('fragment_base_url', '')

                # Ensure we have a valid URL
                if download_url:
                    formats.append({
                        'quality': 'Audio Only',
                        'format': audio_format.get('ext', 'unknown'),
                        'url': download_url,
                        'filesize': audio_format.get('filesize', 0),
                        'bitrate': audio_format.get('abr', 0),
                        'headers': headers,
                        'requires_headers': True,
                        'download_instructions': {
                            'curl': f"curl -L '{download_url}' -H 'User-Agent: {headers.get('User-Agent', '')}' -H 'Referer: {headers.get('Referer', '')}' -o output.{audio_format.get('ext', 'mp3')}",
                            'wget': f"wget --header='User-Agent: {headers.get('User-Agent', '')}' --header='Referer: {headers.get('Referer', '')}' '{download_url}' -O output.{audio_format.get('ext', 'mp3')}",
                            'python': "Use requests library with the provided headers"
                        }
                    })

        else:  # quality == 'best'
            # Get video formats with audio
            video_formats = []
            for f in info.get('formats', []):
                if (f.get('ext') in ['mp4', 'webm'] and
                    f.get('vcodec') != 'none' and
                    f.get('acodec') != 'none' and
                    f.get('url')):
                    video_formats.append(f)

            # Sort by quality (height, then width)
            video_formats.sort(key=lambda x: (
                x.get('height', 0) or 0,
                x.get('width', 0) or 0
            ), reverse=True)

            # Take top 3 quality options
            for fmt in video_formats[:3]:
                quality_label = f"{fmt.get('height', 'unknown')}p"
                if fmt.get('height') == 1080:
                    quality_label = "1080p HD"
                elif fmt.get('height') == 720:
                    quality_label = "720p HD"
                elif fmt.get('height') == 480:
                    quality_label = "480p"
                elif fmt.get('height') == 360:
                    quality_label = "360p"
                elif fmt.get('height') == 240:
                    quality_label = "240p"

                # Get the actual download URL - prioritize direct URL
                download_url = fmt.get('url', '')
                if not download_url:
                    # Try fragment base URL as fallback
                    download_url = fmt.get('fragment_base_url', '')

                # Ensure we have a valid URL
                if download_url:
                    formats.append({
                        'quality': quality_label,
                        'format': fmt.get('ext', 'unknown'),
                        'url': download_url,
                        'filesize': fmt.get('filesize', 0),
                        'resolution': f"{fmt.get('width', 0)}x{fmt.get('height', 0)}",
                        'headers': headers,
                        'requires_headers': True,
                        'download_instructions': {
                            'curl': f"curl -L '{download_url}' -H 'User-Agent: {headers.get('User-Agent', '')}' -H 'Referer: {headers.get('Referer', '')}' -o output.{fmt.get('ext', 'mp4')}",
                            'wget': f"wget --header='User-Agent: {headers.get('User-Agent', '')}' --header='Referer: {headers.get('Referer', '')}' '{download_url}' -O output.{fmt.get('ext', 'mp4')}",
                            'python': "Use requests library with the provided headers"
                        }
                    })

        return formats

    def validate_url(self, url):
        """Validate if URL is a YouTube URL"""
        return any(domain in url.lower() for domain in ['youtube.com', 'youtu.be'])


# Flask API
app = Flask(__name__)

@app.route('/api/download-links', methods=['POST'])
def get_download_links():
    """API endpoint to get downloadable video links"""
    try:
        # Get JSON data from request
        data = request.get_json()

        if not data or 'url' not in data:
            return jsonify({
                'success': False,
                'error': 'Missing required field: url'
            }), 400

        url = data['url']
        quality = data.get('quality', 'best')

        # Validate quality parameter
        if quality not in ['best', 'audio']:
            return jsonify({
                'success': False,
                'error': 'Invalid quality. Must be "best" or "audio"'
            }), 400

        # Create extractor instance
        extractor = YouTubeLinkExtractor()

        # Validate URL
        if not extractor.validate_url(url):
            return jsonify({
                'success': False,
                'error': 'Invalid YouTube URL. Must be a youtube.com or youtu.be link'
            }), 400

        # Get video info and download links
        result = extractor.get_video_info_and_links(url, quality)

        if result is None:
            return jsonify({
                'success': False,
                'error': 'Failed to extract video information. Video may be private, unavailable, or region-restricted.'
            }), 404

        if not result['download_links']:
            return jsonify({
                'success': False,
                'error': 'No downloadable formats found for this video'
            }), 404

        return jsonify({
            'success': True,
            'data': result,
            'note': 'Download URLs require the provided headers to work. Each download link includes headers and example commands (curl/wget) in the download_instructions field. URLs may expire after some time, so download promptly.'
        })

    except Exception as e:
        print(f"API Error: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@app.route('/api/download', methods=['POST'])
def download_video():
    """API endpoint to download video directly"""
    try:
        # Get JSON data from request
        data = request.get_json()

        if not data or 'url' not in data:
            return jsonify({
                'success': False,
                'error': 'Missing required field: url'
            }), 400

        url = data['url']
        quality = data.get('quality', 'best')

        # Validate quality parameter
        if quality not in ['best', 'audio']:
            return jsonify({
                'success': False,
                'error': 'Invalid quality. Must be "best" or "audio"'
            }), 400

        # Create extractor instance
        extractor = YouTubeLinkExtractor()

        # Validate URL
        if not extractor.validate_url(url):
            return jsonify({
                'success': False,
                'error': 'Invalid YouTube URL. Must be a youtube.com or youtu.be link'
            }), 400

        # Get video info first
        info = extractor.get_video_info_and_links(url, quality)
        if not info:
            return jsonify({
                'success': False,
                'error': 'Failed to extract video information'
            }), 404

        # Create temporary directory for download
        temp_dir = Path(tempfile.gettempdir()) / f"youtube_dl_{uuid.uuid4()}"
        temp_dir.mkdir(exist_ok=True)

        # Configure yt-dlp options for download
        ydl_opts = _build_common_ydl_opts({
            'outtmpl': str(temp_dir / '%(title)s.%(ext)s')
        })

        if quality == 'best':
            ydl_opts['format'] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
        elif quality == 'audio':
            ydl_opts['format'] = 'bestaudio/best'
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]

        # Download the video
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                download_info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(download_info)

            file_path = Path(filename)

            # Check if file exists
            if not file_path.exists():
                return jsonify({
                    'success': False,
                    'error': 'Download failed - file not found'
                }), 500

            # Send file and clean up after
            @after_this_request
            def cleanup(response):
                try:
                    file_path.unlink(missing_ok=True)
                    temp_dir.rmdir()
                except:
                    pass
                return response

            return send_file(
                file_path,
                as_attachment=True,
                download_name=file_path.name,
                mimetype='video/mp4' if quality == 'best' else 'audio/mpeg'
            )

        except Exception as e:
            # Clean up on error
            try:
                for f in temp_dir.glob('*'):
                    f.unlink(missing_ok=True)
                temp_dir.rmdir()
            except:
                pass

            return jsonify({
                'success': False,
                'error': f'Download failed: {str(e)}'
            }), 500

    except Exception as e:
        print(f"Download API Error: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy'})


@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'success': False,
        'error': 'Endpoint not found'
    }), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        'success': False,
        'error': 'Internal server error'
    }), 500


if __name__ == '__main__':
    print("Starting YouTube Download Link API...")
    print("API will be available at: http://localhost:4000")
    print("Endpoints:")
    print("  POST /api/download-links  - Get streaming URLs (for info only)")
    print("  POST /api/download        - Download video directly")
    print("  GET /health              - Health check")

    app.run(debug=True, host='0.0.0.0', port=4000)
