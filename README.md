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

## 🚀 Deployment on EC2 (Free & Works!)

Unlike Render/Heroku, EC2 instances work great with YouTube downloads. Here's how to deploy:

### EC2 Setup (Free Tier)
1. **Launch EC2 Instance:**
   - AMI: Amazon Linux 2 or Ubuntu
   - Instance Type: t2.micro (free tier)
   - Security Group: Allow HTTP (80) and Custom TCP (8000)

2. **Connect via SSH and install dependencies:**
   ```bash
   # Update system
   sudo yum update -y  # Amazon Linux
   # OR
   sudo apt update && sudo apt upgrade -y  # Ubuntu

   # Install Python and ffmpeg
   sudo yum install python3 python3-pip ffmpeg -y  # Amazon Linux
   # OR
   sudo apt install python3 python3-pip ffmpeg -y  # Ubuntu
   ```

3. **Deploy the application:**
   ```bash
   # Clone and setup
   git clone https://github.com/AnTIdoTe003/py-yt-downloader.git
   cd py-yt-downloader
   pip3 install -r requirements.txt

   # Run the API
   python3 app.py
   ```

4. **Access your API:**
   - URL: `http://your-ec2-public-ip:5000`
   - Health check: `http://your-ec2-public-ip:5000/health`

### Why EC2 Works Better
- ✅ **Direct IP access** (not blocked like Render)
- ✅ **Free tier available** (750 hours/month)
- ✅ **Full network control**
- ✅ **Proxy support built-in** for extra reliability

### Running on Render/Other PaaS

Render blocks some outbound requests to YouTube directly. The API now includes:

- **Automatic proxy rotation** (configure with `YTDL_PROXY` or `YTDL_PROXY_POOL`)
- **Inline cookies** via `YTDL_COOKIES_B64` (Base64 encoded Netscape cookie file)
- **Mirror metadata fallback** (Invidious instances) with optional TLS opt-out `INVIDIOUS_VERIFY_TLS=0`
- **Mirror downloads** when YouTube is unreachable

For Render:
1. Make sure `ffmpeg` is installed in `render.yaml` (already included).
2. Add environment variables in the Render dashboard:
   - `YTDL_PROXY`: `http://user:pass@proxyhost:port` (or use `YTDL_PROXY_POOL` for comma-separated list)
   - `YTDL_COOKIES_B64`: Paste a Base64 string of your cookies.txt if you need age-restricted videos.
   - `INVIDIOUS_VERIFY_TLS`: set to `0` only if your Render region has TLS issues with some mirrors.
3. Deploy as usual – the API will transparently retry on different strategies before failing.

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
- ✅ **NEW:** Proxy support for bypassing restrictions
- ✅ **NEW:** Rotating user agents for better compatibility
- ✅ **NEW:** Cloud-ready (works on EC2, not blocked like Render)
- ✅ **NEW:** Multiple fallback strategies for reliability

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
