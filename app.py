#!/usr/bin/env python3
"""
YouTube Video Downloader & Uploader API
Downloads YouTube videos and uploads them to SafronStays storage.
"""

import os
import tempfile
import uuid
from pathlib import Path
from typing import Dict, Any, Optional

import requests
import yt_dlp
from flask import Flask, request, jsonify

app = Flask(__name__)

UPLOAD_API_URL = "https://go.saffronstays.com/api/upload-file"


def _build_ydl_opts(extra_opts: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Build yt-dlp options"""
    opts: Dict[str, Any] = {
        'noplaylist': True,
        'quiet': False,
        'no_warnings': False,
        'restrictfilenames': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['web', 'android', 'ios', 'tv'],
                'player_skip': ['js', 'webpage'],
                'skip': ['dash', 'hls'],
            }
        },
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0',
        },
        'geo_bypass': True,
        'sleep_interval': 1,
        'max_sleep_interval': 5,
    }

    cookie_file = os.getenv('YDL_COOKIES', 'cookies.txt')
    if Path(cookie_file).exists():
        opts['cookiefile'] = cookie_file

    if extra_opts:
        opts.update(extra_opts)

    return opts


def get_full_video_metadata(url: str) -> Optional[Dict[str, Any]]:
    """Extract complete video metadata from YouTube URL"""
    # Try multiple extraction strategies
    strategies = [
        # Strategy 1: Default configuration
        {
            'extractor_args': {
                'youtube': {
                    'player_client': ['web', 'android', 'ios', 'tv'],
                    'player_skip': ['js', 'webpage'],
                    'skip': ['dash', 'hls'],
                }
            }
        },
        # Strategy 2: Simplified configuration
        {
            'extractor_args': {
                'youtube': {
                    'player_client': ['web'],
                    'player_skip': ['js'],
                }
            }
        },
        # Strategy 3: Minimal configuration
        {}
    ]

    last_error = None
    for i, strategy_opts in enumerate(strategies):
        try:
            print(f"Trying extraction strategy {i+1}...")
            ydl_opts = _build_ydl_opts(strategy_opts)

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

                if not info or not info.get('title'):
                    continue

                return {
                    'id': info.get('id'),
                    'title': info.get('title'),
                    'description': info.get('description'),
                    'uploader': info.get('uploader'),
                    'uploader_id': info.get('uploader_id'),
                    'uploader_url': info.get('uploader_url'),
                    'channel': info.get('channel'),
                    'channel_id': info.get('channel_id'),
                    'channel_url': info.get('channel_url'),
                    'duration': info.get('duration'),
                    'duration_string': info.get('duration_string'),
                    'view_count': info.get('view_count'),
                    'like_count': info.get('like_count'),
                    'comment_count': info.get('comment_count'),
                    'upload_date': info.get('upload_date'),
                    'release_date': info.get('release_date'),
                    'thumbnail': info.get('thumbnail'),
                    'thumbnails': info.get('thumbnails', []),
                    'tags': info.get('tags', []),
                    'categories': info.get('categories', []),
                    'age_limit': info.get('age_limit'),
                    'is_live': info.get('is_live'),
                    'was_live': info.get('was_live'),
                    'live_status': info.get('live_status'),
                    'webpage_url': info.get('webpage_url'),
                    'original_url': info.get('original_url'),
                    'availability': info.get('availability'),
                    'playable_in_embed': info.get('playable_in_embed'),
                    'average_rating': info.get('average_rating'),
                    'chapters': info.get('chapters'),
                    'subtitles': list(info.get('subtitles', {}).keys()),
                    'automatic_captions': list(info.get('automatic_captions', {}).keys()),
                }
        except Exception as e:
            import traceback
            last_error = e
            print(f"Strategy {i+1} failed: {e}")
            if i == len(strategies) - 1:  # Last strategy
                print("All strategies failed. Full traceback:")
                print(traceback.format_exc())
            continue

    print(f"All extraction strategies failed. Last error: {last_error}")
    return None


def download_video(url: str, quality: str = 'best') -> Optional[Path]:
    """Download video to temp directory"""
    temp_dir = Path(tempfile.gettempdir()) / f"yt_dl_{uuid.uuid4()}"
    temp_dir.mkdir(exist_ok=True)

    ydl_opts = _build_ydl_opts({
        'outtmpl': str(temp_dir / '%(title)s.%(ext)s'),
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best' if quality == 'best' else 'bestaudio/best',
    })

    if quality == 'audio':
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

            file_path = Path(filename)
            if quality == 'audio':
                file_path = file_path.with_suffix('.mp3')

            if file_path.exists():
                return file_path
    except Exception as e:
        print(f"Download error: {e}")

    return None


def upload_to_saffronstays(file_path: Path, folder_name: str = "yt-videos") -> Dict[str, Any]:
    """Upload file to SafronStays API"""
    try:
        with open(file_path, 'rb') as f:
            files = {'file': (file_path.name, f)}
            data = {'folderName': folder_name}

            response = requests.post(
                UPLOAD_API_URL,
                files=files,
                data=data,
                timeout=300
            )

            return {
                'success': response.ok,
                'status_code': response.status_code,
                'response': response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text
            }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


def validate_youtube_url(url: str) -> bool:
    """Check if URL is a valid YouTube URL"""
    return any(domain in url.lower() for domain in ['youtube.com', 'youtu.be'])


@app.route('/api/process', methods=['POST'])
def process_video():
    """
    Main endpoint: Get metadata, download video, upload to SafronStays

    Request body:
    {
        "url": "https://www.youtube.com/watch?v=VIDEO_ID",
        "quality": "best"  // optional: "best" or "audio"
    }
    """
    try:
        data = request.get_json()

        if not data or 'url' not in data:
            return jsonify({'success': False, 'error': 'Missing required field: url'}), 400

        url = data['url']
        quality = data.get('quality', 'best')

        if not validate_youtube_url(url):
            return jsonify({'success': False, 'error': 'Invalid YouTube URL'}), 400

        if quality not in ['best', 'audio']:
            return jsonify({'success': False, 'error': 'Invalid quality. Must be "best" or "audio"'}), 400

        # Get full metadata
        metadata = get_full_video_metadata(url)
        if not metadata:
            return jsonify({'success': False, 'error': 'Failed to extract video metadata'}), 404

        # Download video
        file_path = download_video(url, quality)
        if not file_path:
            return jsonify({
                'success': False,
                'error': 'Failed to download video',
                'metadata': metadata
            }), 500

        # Upload to SafronStays
        upload_result = upload_to_saffronstays(file_path)

        # Cleanup
        try:
            file_path.unlink(missing_ok=True)
            file_path.parent.rmdir()
        except:
            pass

        return jsonify({
            'success': upload_result.get('success', False),
            'metadata': metadata,
            'upload_response': upload_result
        })

    except Exception as e:
        print(f"API Error: {e}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


@app.route('/api/metadata', methods=['POST'])
def get_metadata():
    """Get only video metadata without downloading"""
    try:
        data = request.get_json()

        if not data or 'url' not in data:
            return jsonify({'success': False, 'error': 'Missing required field: url'}), 400

        url = data['url']

        if not validate_youtube_url(url):
            return jsonify({'success': False, 'error': 'Invalid YouTube URL'}), 400

        metadata = get_full_video_metadata(url)
        if not metadata:
            return jsonify({'success': False, 'error': 'Failed to extract video metadata'}), 404

        return jsonify({'success': True, 'metadata': metadata})

    except Exception as e:
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy'})


@app.route('/', methods=['GET'])
def index():
    return jsonify({
        'service': 'YouTube Video Processor',
        'endpoints': {
            'POST /api/process': 'Download video, get metadata, upload to storage',
            'POST /api/metadata': 'Get video metadata only',
            'GET /health': 'Health check'
        }
    })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 4000))
    app.run(host='0.0.0.0', port=port)

