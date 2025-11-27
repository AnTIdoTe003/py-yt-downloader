# YouTube Video/Shorts Downloader

A Python tool to download YouTube videos and shorts with various quality options.

## ⚠️ Legal Warning

**This tool is for educational purposes only.** Downloading YouTube videos may violate YouTube's Terms of Service. Always ensure you have permission to download and use the content. Respect copyright laws and content creators' rights.

## Installation

1. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

   Or install yt-dlp directly:
   ```bash
   pip install yt-dlp
   ```

2. **Make the script executable (optional):**
   ```bash
   chmod +x youtube_downloader.py
   ```

## Usage

### Basic Usage

Download a video in best quality:
```bash
python youtube_downloader.py "https://www.youtube.com/watch?v=VIDEO_ID"
```

### Command Line Options

- `url`: YouTube video URL (required)
- `-o, --output`: Output directory (default: `downloads`)
- `-q, --quality`: Download quality - `best` or `audio` (default: `best`)
- `-f, --format`: Specific format ID to download
- `-l, --list`: List available formats without downloading
- `-i, --info`: Show video information without downloading

### Examples

**1. Download video in best quality:**
```bash
python youtube_downloader.py "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

**2. Download audio only (MP3):**
```bash
python youtube_downloader.py "https://www.youtube.com/watch?v=dQw4w9WgXcQ" -q audio
```

**3. List available formats:**
```bash
python youtube_downloader.py "https://www.youtube.com/watch?v=dQw4w9WgXcQ" -l
```

**4. Show video information:**
```bash
python youtube_downloader.py "https://www.youtube.com/watch?v=dQw4w9WgXcQ" -i
```

**5. Download to custom directory:**
```bash
python youtube_downloader.py "https://www.youtube.com/watch?v=dQw4w9WgXcQ" -o /path/to/downloads
```

**6. Download specific format:**
```bash
python youtube_downloader.py "https://www.youtube.com/watch?v=dQw4w9WgXcQ" -f 22
```

## API Usage

The project now includes a REST API that returns downloadable video links instead of downloading videos directly.

### Starting the API Server

```bash
python youtube_api.py
```

The API will be available at: `http://localhost:5000`

### API Endpoints

**1. Get Download Links:**
- **Endpoint:** `POST /api/download-links`
- **Content-Type:** `application/json`

**Request Body:**
```json
{
    "url": "https://www.youtube.com/watch?v=VIDEO_ID",
    "quality": "best"
}
```

**Parameters:**
- `url` (required): YouTube video URL
- `quality` (optional): "best" or "audio" (default: "best")

**Response:**
```json
{
    "success": true,
    "data": {
        "title": "Video Title",
        "uploader": "Uploader Name",
        "duration": 300,
        "view_count": 1000000,
        "upload_date": "20231201",
        "thumbnail": "https://...",
        "download_links": [
            {
                "quality": "720p HD",
                "format": "mp4",
                "url": "https://...",
                "filesize": 50000000,
                "resolution": "1280x720"
            }
        ]
    }
}
```

**2. Health Check:**
- **Endpoint:** `GET /health`
- **Response:** `{"status": "healthy"}`

### API Examples

**Get best quality download links:**
```bash
curl -X POST http://localhost:5000/api/download-links \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}'
```

**Get audio-only download links:**
```bash
curl -X POST http://localhost:5000/api/download-links \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "quality": "audio"}'
```

### Supported URLs

- Regular YouTube videos: `https://www.youtube.com/watch?v=VIDEO_ID`
- YouTube Shorts: `https://www.youtube.com/shorts/SHORT_ID`
- Mobile URLs: `https://youtu.be/VIDEO_ID`
- Playlist URLs (downloads first video only)

## Features

- ✅ Downloads YouTube videos and shorts
- ✅ Multiple quality options (best video, audio only)
- ✅ Shows video information (title, uploader, duration, views)
- ✅ Lists available formats with file sizes
- ✅ Downloads to custom directories
- ✅ Supports specific format selection
- ✅ Progress indicators during download
- ✅ Error handling for invalid URLs
- ✅ **NEW:** REST API for getting downloadable video links

## Troubleshooting

**"yt-dlp not installed" error:**
```bash
pip install yt-dlp
```

**Download fails:**
- Check if the video is available and not private
- Some videos may be region-restricted
- Try updating yt-dlp: `pip install --upgrade yt-dlp`

**Permission errors:**
- Ensure you have write permissions in the output directory
- On macOS/Linux, you may need to adjust folder permissions

## How it Works

The tool uses `yt-dlp`, which is a fork of youtube-dl that's actively maintained and supports the latest YouTube changes. It handles:

- Video format selection
- Audio/video merging
- Subtitles (if available)
- Metadata extraction
- Anti-bot detection bypass

## Dependencies

- `yt-dlp`: Command-line program to download videos from YouTube and other sites

## License

This project is for educational purposes. Please respect copyright and platform terms of service.
