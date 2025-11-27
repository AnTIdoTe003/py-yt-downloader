#!/usr/bin/env python3
"""
YouTube Video Downloader & Uploader API
Downloads YouTube videos and uploads them to SafronStays storage.
"""

import base64
import json
import os
import random
import re
import subprocess
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

import requests
import yt_dlp
from flask import Flask, jsonify, request

app = Flask(__name__)

UPLOAD_API_URL = "https://go.saffronstays.com/api/upload-file"

# Free proxy sources (some might work)
FREE_PROXY_SOURCES = [
    "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=https&timeout=10000&country=all&ssl=all&anonymity=all",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
]

# Rotating user agents to avoid detection
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/121.0',
]


def _normalize_proxy_url(proxy: Optional[str]) -> Optional[str]:
    """Ensure proxies include a scheme so requests/yt-dlp understand them."""
    if not proxy:
        return None
    proxy = proxy.strip()
    if not proxy:
        return None
    if "://" not in proxy:
        proxy = f"http://{proxy}"
    return proxy


FORCED_PROXY = _normalize_proxy_url(os.getenv('YTDL_PROXY') or os.getenv('PROXY_URL'))
STATIC_PROXY_POOL = [
    normalized for normalized in (
        _normalize_proxy_url(entry) for entry in os.getenv('YTDL_PROXY_POOL', '').split(',')
    ) if normalized
]
ALLOW_DIRECT_CONNECTION = os.getenv('YTDL_ALLOW_DIRECT', '1') != '0'
ENABLE_FREE_PROXY_FALLBACK = os.getenv('YTDL_ENABLE_FREE_PROXIES', '1') != '0'

INVIDIOUS_INSTANCES = [
    # Popular mirrors - automatically rotated. We intentionally include only mirrors
    # that historically allow API access without auth.
    "https://yt.artemislena.eu",
    "https://invidious.protokolla.fi",
    "https://invidious.jing.rocks",
    "https://invidious.privacydev.net",
    "https://invidious.fdn.fr",
    "https://yt.mnt.lv",
]
INVIDIOUS_VERIFY_TLS = os.getenv('INVIDIOUS_VERIFY_TLS', '1').lower() not in {'0', 'false', 'no'}

PIPED_API_INSTANCES = [
    # API-only instances that expose proxied stream URLs (Render friendly).
    "https://pipedapi.kavin.rocks",
    "https://pipedapi-libre.kavin.rocks",
    "https://pipedapi.leptons.xyz",
    "https://pipedapi.nosebs.ru",
    "https://piped-api.codespace.cz",
    "https://pipedapi.reallyaweso.me",
    "https://api.piped.private.coffee",
    "https://pipedapi.ducks.party",
    "https://pipedapi.darkness.services",
    "https://pipedapi.orangenet.cc",
]
PIPED_VERIFY_TLS = True
WATCH_BASE_URL = "https://www.youtube.com/watch"
YOUTUBEI_PLAYER_ENDPOINT = "https://www.youtube.com/youtubei/v1/player"
YOUTUBE_WEB_CLIENT_VERSION = "2.20251125.06.00"
YOUTUBE_WEB_CLIENT_NAME = "WEB"
YOUTUBEI_KEY = "AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8"


def _build_proxy_candidates(include_direct: bool = True) -> List[Optional[str]]:
    """Assemble proxy candidates honoring env configuration."""
    candidates: List[Optional[str]] = []

    if FORCED_PROXY:
        candidates.append(FORCED_PROXY)

    candidates.extend(STATIC_PROXY_POOL)

    if include_direct and ALLOW_DIRECT_CONNECTION:
        candidates.append(None)

    if ENABLE_FREE_PROXY_FALLBACK:
        free_proxy = get_free_proxy()
        if free_proxy:
            candidates.append(free_proxy)

    filtered: List[Optional[str]] = []
    seen = set()
    for proxy in candidates:
        key = proxy or "DIRECT"
        if key in seen:
            continue
        seen.add(key)
        filtered.append(proxy)

    return filtered or [None]


_COOKIE_FILE_CACHE: Optional[Path] = None


def _resolve_cookie_file() -> Optional[str]:
    """Return a cookie file path if available (env file path or inline base64)."""
    global _COOKIE_FILE_CACHE

    if _COOKIE_FILE_CACHE:
        return str(_COOKIE_FILE_CACHE)

    inline_cookie = os.getenv('YTDL_COOKIES_B64') or os.getenv('YTDL_COOKIES_INLINE')
    if inline_cookie:
        try:
            decoded = base64.b64decode(inline_cookie).decode('utf-8')
            temp_cookie_path = Path(tempfile.gettempdir()) / f"yt_cookies_{os.getpid()}.txt"
            temp_cookie_path.write_text(decoded)
            _COOKIE_FILE_CACHE = temp_cookie_path
            return str(temp_cookie_path)
        except Exception as exc:
            print(f"Failed to decode inline cookies: {exc}")

    cookie_file = os.getenv('YTDL_COOKIES', 'cookies.txt')
    cookie_path = Path(cookie_file)
    if cookie_path.exists():
        _COOKIE_FILE_CACHE = cookie_path
        return str(cookie_path)

    return None


def get_free_proxy() -> Optional[str]:
    """Get a working free proxy"""
    for source_url in FREE_PROXY_SOURCES:
        try:
            response = requests.get(source_url, timeout=10)
            if response.status_code == 200:
                proxies = response.text.strip().split('\n')
                # Filter out empty lines and comments
                valid_proxies = [p.strip() for p in proxies if p.strip() and not p.startswith('#')]
                if valid_proxies:
                    # Try a few proxies to find one that works
                    for proxy in random.sample(valid_proxies, min(3, len(valid_proxies))):
                        proxy_url = f"https://{proxy}" if 'https' in source_url else f"http://{proxy}"
                        # Quick test if proxy is accessible
                        try:
                            test_response = requests.get('https://httpbin.org/ip', proxies={'https': proxy_url}, timeout=5)
                            if test_response.status_code == 200:
                                return proxy_url
                        except:
                            continue
                    # If none work, return the first one anyway
                    proxy = random.choice(valid_proxies)
                    return f"https://{proxy}" if 'https' in source_url else f"http://{proxy}"
        except Exception as e:
            print(f"Failed to get proxies from {source_url}: {e}")
            continue
    return None


def get_random_user_agent() -> str:
    """Get a random user agent"""
    return random.choice(USER_AGENTS)


def _proxy_dict(proxy: Optional[str]) -> Optional[Dict[str, str]]:
    """requests-friendly proxy dict"""
    if not proxy:
        return None
    return {
        'http': proxy,
        'https': proxy,
    }


def extract_video_id(url: str) -> Optional[str]:
    """Extract the video id from different YouTube URL formats"""
    try:
        parsed = urlparse(url)
        if 'youtube' in parsed.netloc:
            query = parse_qs(parsed.query)
            if 'v' in query:
                return query['v'][0]
            # Short URLs like /shorts/<id>
            path_parts = [part for part in parsed.path.split('/') if part]
            if path_parts:
                return path_parts[-1]
        elif 'youtu.be' in parsed.netloc:
            return parsed.path.lstrip('/')
    except Exception as e:
        print(f"Failed to parse video id from {url}: {e}")
    return None


def _public_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Strip internal-only keys before returning metadata to clients."""
    if not metadata:
        return {}
    return {k: v for k, v in metadata.items() if not k.startswith('__')}


def _normalize_iso_date(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).strftime('%Y%m%d')
    except Exception:
        return value.replace('-', '') if isinstance(value, str) else None


def _format_upload_date(timestamp: Optional[int]) -> Optional[str]:
    """Return YYYYMMDD string if timestamp is provided"""
    if not timestamp:
        return None
    try:
        return datetime.utcfromtimestamp(int(timestamp)).strftime('%Y%m%d')
    except Exception:
        return None


def _normalize_simple_date(date_str: Optional[str]) -> Optional[str]:
    """Accept YYYY-MM-DD or YYYY/MM/DD strings and return YYYYMMDD."""
    if not date_str or not isinstance(date_str, str):
        return None
    clean = date_str.strip()
    if not clean:
        return None
    clean = clean.replace('/', '-')
    parts = clean.split('-')
    if len(parts) == 3 and all(part.isdigit() for part in parts):
        return ''.join(part.zfill(2) if idx else part.zfill(4) for idx, part in enumerate(parts))
    if clean.isdigit() and len(clean) == 8:
        return clean
    return None


def _map_invidious_metadata(data: Dict[str, Any], instance: str) -> Dict[str, Any]:
    """Normalize Invidious response to our metadata schema"""
    thumbnails = data.get('videoThumbnails', [])
    thumbnail_url = thumbnails[-1]['url'] if thumbnails else data.get('thumbnail')
    genre = data.get('genre')
    if isinstance(genre, list):
        categories = genre
    elif isinstance(genre, str):
        categories = [genre]
    else:
        categories = []

    try:
        duration_value = int(data.get('lengthSeconds')) if data.get('lengthSeconds') is not None else None
    except (TypeError, ValueError):
        duration_value = None

    metadata = {
        'id': data.get('videoId') or data.get('id'),
        'title': data.get('title'),
        'description': data.get('description'),
        'uploader': data.get('author'),
        'uploader_id': data.get('authorId'),
        'uploader_url': f"{instance}{data.get('authorUrl')}" if data.get('authorUrl') else None,
        'channel': data.get('author'),
        'channel_id': data.get('authorId'),
        'channel_url': f"{instance}{data.get('authorUrl')}" if data.get('authorUrl') else None,
        'duration': duration_value,
        'duration_string': data.get('lengthSeconds'),
        'view_count': data.get('viewCount'),
        'like_count': data.get('likeCount') or data.get('likes'),
        'comment_count': data.get('commentCount'),
        'upload_date': _format_upload_date(data.get('published')),
        'release_date': data.get('premiereTimestamp'),
        'thumbnail': thumbnail_url,
        'thumbnails': thumbnails,
        'tags': data.get('keywords') or [],
        'categories': categories,
        'age_limit': None,
        'is_live': data.get('liveNow'),
        'was_live': data.get('liveNow'),
        'live_status': 'live' if data.get('liveNow') else 'not_live',
        'webpage_url': f"https://www.youtube.com/watch?v={data.get('videoId')}",
        'original_url': f"https://www.youtube.com/watch?v={data.get('videoId')}",
        'availability': 'public',
        'playable_in_embed': True,
        'average_rating': data.get('averageRating'),
        'chapters': data.get('chapters'),
        'subtitles': [caption.get('languageCode') for caption in (data.get('captions') or []) if caption.get('languageCode')],
        'automatic_captions': [],
        '__mirror_streams': {
            'formatStreams': data.get('formatStreams', []),
            'adaptiveFormats': data.get('adaptiveFormats', []),
        }
    }

    metadata['__mirror_type'] = 'invidious'
    return metadata


def _map_piped_metadata(data: Dict[str, Any], instance: str) -> Dict[str, Any]:
    """Normalize Piped /streams response to our metadata schema."""
    try:
        duration_value = int(data.get('duration')) if data.get('duration') is not None else None
    except (TypeError, ValueError):
        duration_value = None

    subtitles = data.get('subtitles') or []

    thumbnail_url = data.get('thumbnailUrl')
    thumbnails = [{'url': thumbnail_url}] if thumbnail_url else []

    video_id = data.get('id') or data.get('videoId')

    metadata = {
        'id': video_id,
        'title': data.get('title'),
        'description': data.get('description'),
        'uploader': data.get('uploader'),
        'uploader_id': data.get('uploaderId'),
        'uploader_url': data.get('uploaderUrl'),
        'channel': data.get('uploader'),
        'channel_id': data.get('uploaderId'),
        'channel_url': data.get('uploaderUrl'),
        'duration': duration_value,
        'duration_string': str(duration_value) if duration_value is not None else None,
        'view_count': data.get('views'),
        'like_count': data.get('likes'),
        'comment_count': None,
        'upload_date': _normalize_simple_date(data.get('uploadDate')) or _format_upload_date(data.get('uploadedTimestamp')),
        'release_date': data.get('uploadedDate'),
        'thumbnail': thumbnail_url,
        'thumbnails': thumbnails,
        'tags': data.get('tags') or [],
        'categories': [],
        'age_limit': 18 if data.get('nsfw') else None,
        'is_live': data.get('livestream'),
        'was_live': data.get('livestream'),
        'live_status': 'live' if data.get('livestream') else 'not_live',
        'webpage_url': f"https://www.youtube.com/watch?v={video_id}" if video_id else data.get('url'),
        'original_url': data.get('url'),
        'availability': 'public',
        'playable_in_embed': True,
        'average_rating': None,
        'chapters': [],
        'subtitles': [subtitle.get('code') for subtitle in subtitles if subtitle.get('code')],
        'automatic_captions': [],
        '__mirror_streams': {
            'videoStreams': data.get('videoStreams', []),
            'audioStreams': data.get('audioStreams', []),
            'proxyUrl': data.get('proxyUrl'),
        },
        '__mirror_type': 'piped',
        '__mirror_instance': instance,
        '__source': 'piped',
        '__piped_proxy_url': data.get('proxyUrl'),
    }
    return metadata


def _map_player_response_metadata(player_data: Dict[str, Any], proxy: Optional[str], strategy: str) -> Optional[Dict[str, Any]]:
    if not player_data:
        return None

    video_details = player_data.get('videoDetails') or {}
    microformat = (player_data.get('microformat') or {}).get('playerMicroformatRenderer') or {}
    streaming = player_data.get('streamingData') or {}
    captions = ((player_data.get('captions') or {}).get('playerCaptionsTracklistRenderer') or {}).get('captionTracks') or []

    if not video_details.get('title'):
        return None

    duration_value: Optional[int]
    try:
        duration_value = int(video_details.get('lengthSeconds')) if video_details.get('lengthSeconds') else None
    except (TypeError, ValueError):
        duration_value = None

    thumbnails = (video_details.get('thumbnail') or {}).get('thumbnails', [])
    micro_thumbnails = microformat.get('thumbnail', {}).get('thumbnails', [])
    if micro_thumbnails:
        thumbnails = thumbnails or micro_thumbnails

    metadata = {
        'id': video_details.get('videoId'),
        'title': video_details.get('title'),
        'description': video_details.get('shortDescription') or microformat.get('description'),
        'uploader': video_details.get('author') or microformat.get('ownerChannelName'),
        'uploader_id': microformat.get('externalChannelId'),
        'uploader_url': microformat.get('ownerProfileUrl'),
        'channel': microformat.get('ownerChannelTitle') or video_details.get('author'),
        'channel_id': microformat.get('externalChannelId'),
        'channel_url': microformat.get('ownerProfileUrl'),
        'duration': duration_value,
        'duration_string': video_details.get('lengthSeconds'),
        'view_count': video_details.get('viewCount'),
        'like_count': None,
        'comment_count': None,
        'upload_date': _normalize_iso_date(microformat.get('uploadDate') or microformat.get('publishDate')),
        'release_date': microformat.get('publishDate'),
        'thumbnail': thumbnails[-1]['url'] if thumbnails else None,
        'thumbnails': thumbnails,
        'tags': video_details.get('keywords', []),
        'categories': [microformat.get('category')] if microformat.get('category') else [],
        'age_limit': 18 if microformat.get('isFamilySafe') is False else None,
        'is_live': video_details.get('isLiveContent'),
        'was_live': video_details.get('isLiveContent'),
        'live_status': 'live' if video_details.get('isLiveContent') else 'not_live',
        'webpage_url': f"https://www.youtube.com/watch?v={video_details.get('videoId')}",
        'original_url': f"https://www.youtube.com/watch?v={video_details.get('videoId')}",
        'availability': microformat.get('availability'),
        'playable_in_embed': microformat.get('isEmbedRestricted') is not True,
        'average_rating': video_details.get('averageRating'),
        'chapters': [],
        'subtitles': [track.get('languageCode') for track in captions if track.get('languageCode')],
        'automatic_captions': [],
        '__proxy': proxy,
        '__strategy': strategy,
        '__source': strategy,
        '__mirror_streams': {
            'formatStreams': streaming.get('formats', []),
            'adaptiveFormats': streaming.get('adaptiveFormats', []),
        },
        '__player_response': player_data,
    }
    return metadata


def fetch_metadata_from_invidious(url: str, proxy_candidates: Optional[List[Optional[str]]] = None) -> Optional[Dict[str, Any]]:
    """Fallback metadata extraction using Invidious mirrors"""
    video_id = extract_video_id(url)
    if not video_id:
        print("Could not extract video id for mirror fallback")
        return None

    instances = random.sample(INVIDIOUS_INSTANCES, len(INVIDIOUS_INSTANCES))
    proxy_candidates = proxy_candidates or _build_proxy_candidates()

    headers = {
        'User-Agent': get_random_user_agent(),
        'Accept': 'application/json',
    }

    for instance in instances:
        api_url = f"{instance.rstrip('/')}/api/v1/videos/{video_id}"
        for proxy in proxy_candidates:
            try:
                response = requests.get(
                    api_url,
                    headers=headers,
                    timeout=15,
                    proxies=_proxy_dict(proxy),
                    verify=INVIDIOUS_VERIFY_TLS
                )
                if response.status_code == 200:
                    data = response.json()
                    metadata = _map_invidious_metadata(data, instance)
                    metadata['__source'] = 'invidious'
                    metadata['__proxy'] = proxy
                    metadata['__mirror_instance'] = instance
                    print(f"Invidious fallback succeeded via {instance}")
                    return metadata
                print(f"Invidious {instance} returned status {response.status_code}")
            except Exception as e:
                print(f"Invidious fetch failed for {instance} via {proxy or 'DIRECT'}: {e}")
                continue
    return None


def fetch_metadata_from_piped(url: str) -> Optional[Dict[str, Any]]:
    """Use public Piped API instances to fetch metadata + proxied streams."""
    video_id = extract_video_id(url)
    if not video_id:
        return None

    instances = random.sample(PIPED_API_INSTANCES, len(PIPED_API_INSTANCES))
    headers = {
        'User-Agent': get_random_user_agent(),
        'Accept': 'application/json',
    }

    for instance in instances:
        api_url = f"{instance.rstrip('/')}/streams/{video_id}"
        try:
            response = requests.get(
                api_url,
                headers=headers,
                timeout=25,
                verify=PIPED_VERIFY_TLS
            )
            if response.status_code == 200:
                data = response.json()
                if not data:
                    continue
                metadata = _map_piped_metadata(data, instance)
                print(f"Piped fallback succeeded via {instance}")
                return metadata
            print(f"Piped {instance} returned status {response.status_code}")
        except Exception as exc:
            print(f"Piped fetch failed for {instance}: {exc}")
            continue
    return None


def fetch_metadata_from_youtubei(url: str, proxy_candidates: Optional[List[Optional[str]]] = None) -> Optional[Dict[str, Any]]:
    """Use the internal youtubei player endpoint to fetch metadata."""
    video_id = extract_video_id(url)
    if not video_id:
        return None

    proxy_candidates = proxy_candidates or _build_proxy_candidates()

    for proxy in proxy_candidates:
        headers = {
            'User-Agent': get_random_user_agent(),
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        }
        payload = {
            'context': {
                'client': {
                    'clientName': YOUTUBE_WEB_CLIENT_NAME,
                    'clientVersion': YOUTUBE_WEB_CLIENT_VERSION,
                    'hl': 'en',
                    'gl': 'US',
                    'utcOffsetMinutes': 0,
                }
            },
            'videoId': video_id,
            'contentCheckOk': True,
            'racyCheckOk': True,
        }
        try:
            response = requests.post(
                f"{YOUTUBEI_PLAYER_ENDPOINT}?key={YOUTUBEI_KEY}",
                headers=headers,
                json=payload,
                timeout=20,
                proxies=_proxy_dict(proxy),
            )
            if response.status_code != 200:
                print(f"youtubei player endpoint returned {response.status_code}")
                continue

            player_data = response.json()
            metadata = _map_player_response_metadata(player_data, proxy, 'youtubei_player')
            if metadata:
                print("Metadata fetched through youtubei player endpoint.")
                return metadata
        except Exception as exc:
            print(f"youtubei metadata fetch failed via {proxy or 'DIRECT'}: {exc}")
            continue
    return None


def _extract_json_from_html(pattern: str, html: str) -> Optional[Dict[str, Any]]:
    match = re.search(pattern, html, re.DOTALL)
    if not match:
        return None
    blob = match.group(1)
    try:
        return json.loads(blob)
    except Exception as exc:
        print(f"Failed to parse JSON blob from watch html: {exc}")
        return None


def fetch_metadata_from_watch_html(url: str, proxy_candidates: Optional[List[Optional[str]]] = None) -> Optional[Dict[str, Any]]:
    """Fallback metadata extraction by scraping the YouTube watch page directly."""
    video_id = extract_video_id(url)
    if not video_id:
        return None

    proxy_candidates = proxy_candidates or _build_proxy_candidates()
    params = {
        'v': video_id,
        'hl': 'en',
        'bpctr': str(int(datetime.utcnow().timestamp())),
        'has_verified': '1',
    }

    for proxy in proxy_candidates:
        headers = {
            'User-Agent': get_random_user_agent(),
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Connection': 'keep-alive',
            'Referer': 'https://www.youtube.com/',
        }
        try:
            response = requests.get(
                WATCH_BASE_URL,
                params=params,
                headers=headers,
                timeout=20,
                proxies=_proxy_dict(proxy),
            )
            if response.status_code != 200:
                print(f"Watch HTML request failed ({response.status_code}) via {proxy or 'DIRECT'}")
                continue

            player_data = _extract_json_from_html(r"var ytInitialPlayerResponse\s*=\s*(\{.+?\});", response.text)
            if not player_data:
                print("ytInitialPlayerResponse not found in watch html.")
                continue
            metadata = _map_player_response_metadata(player_data, proxy, 'watch_html_scrape')
            if metadata:
                print("Watch page scraping succeeded.")
                return metadata
        except Exception as exc:
            print(f"Watch HTML fetch failed via {proxy or 'DIRECT'}: {exc}")
            continue
    return None


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
        'source_address': '0.0.0.0',  # Bind to all interfaces
        'socket_timeout': 15,
        'retries': 10,
        'fragment_retries': 10,
        'continuedl': True,
        'ignoreerrors': True,
        'forceipv4': True,
    }

    cookie_file = _resolve_cookie_file()
    if cookie_file:
        opts['cookiefile'] = cookie_file

    merged_opts = dict(extra_opts or {})
    if 'proxy' not in merged_opts and FORCED_PROXY:
        merged_opts['proxy'] = FORCED_PROXY

    opts.update(merged_opts)

    return opts


def get_full_video_metadata(url: str) -> Optional[Dict[str, Any]]:
    """Extract complete video metadata from YouTube URL"""
    # Try multiple extraction strategies with proxies and rotating user agents
    strategies = [
        # Strategy 1: With free proxy (if available)
        lambda: {
            'extractor_args': {
                'youtube': {
                    'player_client': ['web'],
                    'player_skip': ['js', 'webpage'],
                }
            },
            'http_headers': {
                'User-Agent': get_random_user_agent(),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
            },
        },
        # Strategy 2: Rotating user agent without proxy
        lambda: {
            'extractor_args': {
                'youtube': {
                    'player_client': ['web', 'android'],
                    'player_skip': ['js'],
                }
            },
            'http_headers': {
                'User-Agent': get_random_user_agent(),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Referer': 'https://www.youtube.com/',
            }
        },
        # Strategy 3: Minimal with different client
        lambda: {
            'extractor_args': {
                'youtube': {
                    'player_client': ['ios'],
                }
            },
            'http_headers': {
                'User-Agent': get_random_user_agent(),
                'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Connection': 'keep-alive',
            }
        },
        # Strategy 4: Fallback without extractor args
        lambda: {
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (compatible; yt-dlp/2024.12.13; +https://github.com/yt-dlp/yt-dlp)',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
            }
        }
    ]

    last_error = None
    proxy_candidates = _build_proxy_candidates()
    for proxy in proxy_candidates:
        for i, strategy_func in enumerate(strategies):
            try:
                print(f"Trying extraction strategy {i+1} via {'DIRECT' if not proxy else proxy}...")
                strategy_opts = strategy_func()
                if proxy:
                    strategy_opts['proxy'] = proxy
                ydl_opts = _build_ydl_opts(strategy_opts)

                # Add additional options for cloud environments
                ydl_opts.update({
                    'quiet': True,
                    'no_warnings': True,
                    'geo_bypass': True,
                    'sleep_interval': 1,
                    'max_sleep_interval': 3,
                })

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)

                    if not info or not info.get('title'):
                        print(f"Strategy {i+1}: No title found in metadata")
                        continue

                    print(f"Strategy {i+1}: SUCCESS - extracted metadata for '{info.get('title')}'")
                    metadata = {
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
                        '__proxy': proxy,
                        '__strategy': f'yt_dlp_strategy_{i+1}',
                    }
                    return metadata
            except Exception as e:
                import traceback
                last_error = e
                print(f"Strategy {i+1} failed via {proxy or 'DIRECT'}: {str(e)}")
                print(traceback.format_exc())
                continue

    print(f"Primary extraction strategies failed. Last error: {last_error}")

    youtubei_metadata = fetch_metadata_from_youtubei(url, proxy_candidates)
    if youtubei_metadata:
        return youtubei_metadata

    html_metadata = fetch_metadata_from_watch_html(url, proxy_candidates)
    if html_metadata:
        return html_metadata

    mirror_metadata = fetch_metadata_from_invidious(url, proxy_candidates)
    if mirror_metadata:
        return mirror_metadata

    piped_metadata = fetch_metadata_from_piped(url)
    if piped_metadata:
        return piped_metadata

    print("All extraction strategies including mirrors failed.")
    return None


def _select_mirror_stream(metadata_context: Optional[Dict[str, Any]], quality: str) -> Optional[Dict[str, Any]]:
    """Pick the best available stream from mirror metadata."""
    if not metadata_context:
        return None

    streams = metadata_context.get('__mirror_streams') or {}
    mirror_type = metadata_context.get('__mirror_type') or ('piped' if 'videoStreams' in streams else 'invidious')

    def _score_quality(label: Optional[str], fallback: Optional[int] = None) -> int:
        if isinstance(label, int):
            return label
        if isinstance(label, str):
            digits = ''.join(ch for ch in label if ch.isdigit())
            if digits:
                return int(digits)
        return fallback or 0

    if mirror_type == 'piped':
        video_streams = [s for s in streams.get('videoStreams', []) if s.get('url')]
        audio_streams = [s for s in streams.get('audioStreams', []) if s.get('url')]

        def _clone(stream: Dict[str, Any]) -> Dict[str, Any]:
            clone = dict(stream)
            clone['__mirror_type'] = 'piped'
            return clone

        if quality == 'audio':
            if not audio_streams:
                return None

            def _audio_score(stream: Dict[str, Any]) -> int:
                bitrate = stream.get('bitrate') or stream.get('avgBitrate') or stream.get('averageBitrate')
                if isinstance(bitrate, str):
                    digits = ''.join(ch for ch in bitrate if ch.isdigit())
                    return int(digits or 0)
                try:
                    return int(bitrate or 0)
                except (TypeError, ValueError):
                    return 0

            audio_streams.sort(key=_audio_score, reverse=True)
            return _clone(audio_streams[0])

        combined = [s for s in video_streams if not s.get('videoOnly')]
        if not combined:
            combined = [s for s in video_streams if s.get('hasAudio')]
        if not combined:
            return None
        combined.sort(key=lambda s: (_score_quality(s.get('quality'), s.get('height')), s.get('height') or 0), reverse=True)
        return _clone(combined[0])

    # Default to invidious mapping
    format_streams = [s for s in streams.get('formatStreams', []) if s.get('url')]
    adaptive_streams = [s for s in streams.get('adaptiveFormats', []) if s.get('url')]

    def _quality_score(stream: Dict[str, Any]) -> int:
        label = stream.get('qualityLabel') or stream.get('quality')
        score = _score_quality(label)
        if score:
            return score
        return int(stream.get('height') or 0)

    def _is_audio(stream: Dict[str, Any]) -> bool:
        mime = (stream.get('mimeType') or stream.get('type') or '').lower()
        return 'audio' in mime and 'video' not in mime

    if quality == 'audio':
        audio_streams = [s for s in adaptive_streams if _is_audio(s)]
        if not audio_streams:
            audio_streams = [s for s in format_streams if _is_audio(s)]
        if not audio_streams:
            return None
        audio_streams.sort(key=lambda s: s.get('bitrate', 0) or s.get('averageBitrate', 0), reverse=True)
        return audio_streams[0]

    progressive = [s for s in format_streams if not _is_audio(s)]
    if not progressive:
        # As a fallback try adaptive video-only streams (caller would still need to merge audio, so we skip)
        return None

    progressive.sort(key=_quality_score, reverse=True)
    return progressive[0]


def _infer_extension(stream: Dict[str, Any], default: str = 'mp4') -> str:
    mime = (stream.get('mimeType') or stream.get('type') or '').lower()
    container = (stream.get('container') or '').lower()

    if 'webm' in mime or 'webm' in container:
        return 'webm'
    if 'mp4' in mime or 'mp4' in container:
        return 'mp4'
    if 'm4a' in mime:
        return 'm4a'
    if 'mp3' in mime:
        return 'mp3'
    if container:
        return container
    return default


def _download_stream_via_requests(stream: Dict[str, Any], temp_dir: Path, metadata_context: Dict[str, Any]) -> Optional[Path]:
    """Download stream URL exposed by mirror to local temp file."""
    url = stream.get('url')
    if not url:
        return None

    ext = _infer_extension(stream, 'mp4')
    temp_file = temp_dir / f"{uuid.uuid4()}.{ext}"
    headers = {
        'User-Agent': get_random_user_agent(),
    }

    mirror_instance = metadata_context.get('__mirror_instance')
    if mirror_instance:
        headers['Referer'] = mirror_instance

    stream_headers = stream.get('__headers')
    if isinstance(stream_headers, dict):
        headers.update(stream_headers)

    proxies = _proxy_dict(metadata_context.get('__proxy'))

    verify_tls = INVIDIOUS_VERIFY_TLS
    if metadata_context.get('__mirror_type') == 'piped':
        verify_tls = PIPED_VERIFY_TLS

    try:
        with requests.get(
            url,
            headers=headers,
            stream=True,
            timeout=30,
            proxies=proxies,
            verify=verify_tls
        ) as response:
            response.raise_for_status()
            with open(temp_file, 'wb') as fh:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        fh.write(chunk)
        print(f"Downloaded via mirror stream to {temp_file}")
        return temp_file
    except Exception as exc:
        print(f"Mirror download failed: {exc}")
        temp_file.unlink(missing_ok=True)
        return None


def _convert_audio_to_mp3(source_path: Path) -> Optional[Path]:
    """Convert downloaded audio-only file to mp3 via ffmpeg if available."""
    target_path = source_path.with_suffix('.mp3')
    try:
        result = subprocess.run(
            [
                'ffmpeg',
                '-y',
                '-i', str(source_path),
                '-vn',
                '-ar', '44100',
                '-ac', '2',
                '-b:a', '192k',
                str(target_path)
            ],
            capture_output=True,
            check=False
        )
        if result.returncode == 0 and target_path.exists():
            source_path.unlink(missing_ok=True)
            return target_path
        else:
            stderr = result.stderr.decode('utf-8', errors='ignore') if result.stderr else ''
            print(f"FFmpeg conversion failed ({result.returncode}): {stderr[:400]}")
    except FileNotFoundError:
        print("ffmpeg not available for audio conversion.")
    except Exception as exc:
        print(f"Audio conversion error: {exc}")
    return source_path


def _download_via_mirror(metadata_context: Optional[Dict[str, Any]], quality: str, temp_dir: Path) -> Optional[Path]:
    """Attempt to download using mirror-provided stream URLs."""
    stream = _select_mirror_stream(metadata_context, quality)
    if not stream:
        return None
    file_path = _download_stream_via_requests(stream, temp_dir, metadata_context or {})
    if not file_path:
        return None
    if quality == 'audio':
        return _convert_audio_to_mp3(file_path)
    return file_path


def download_video(url: str, quality: str = 'best', metadata_context: Optional[Dict[str, Any]] = None) -> Optional[Path]:
    """Download video to temp directory"""
    temp_dir = Path(tempfile.gettempdir()) / f"yt_dl_{uuid.uuid4()}"
    temp_dir.mkdir(exist_ok=True)

    extra_opts: Dict[str, Any] = {
        'outtmpl': str(temp_dir / '%(title)s.%(ext)s'),
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best' if quality == 'best' else 'bestaudio/best',
    }

    proxy = (metadata_context or {}).get('__proxy')
    if proxy:
        extra_opts['proxy'] = proxy

    ydl_opts = _build_ydl_opts(extra_opts)

    if quality == 'audio':
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]

    # Prefer mirror downloads when available (Render safe).
    mirror_first = _download_via_mirror(metadata_context, quality, temp_dir)
    if mirror_first:
        return mirror_first

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
        print(f"Download error via yt-dlp: {e}")

    # Attempt mirror-based download fallback
    mirror_file = _download_via_mirror(metadata_context, quality, temp_dir)
    if mirror_file:
        return mirror_file

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
        metadata_context = get_full_video_metadata(url)
        if not metadata_context:
            return jsonify({'success': False, 'error': 'Failed to extract video metadata'}), 500
        metadata = _public_metadata(metadata_context)

        # Download video
        file_path = download_video(url, quality, metadata_context)
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

        metadata_context = get_full_video_metadata(url)
        if not metadata_context:
            return jsonify({'success': False, 'error': 'Failed to extract video metadata'}), 404
        metadata = _public_metadata(metadata_context)

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

