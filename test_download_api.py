#!/usr/bin/env python3
"""
Test script for the new YouTube Download API endpoint
"""

import requests
import json

def test_download_api():
    """Test the download API endpoint"""
    print("🧪 Testing YouTube Download API")
    print("=" * 40)

    # Test URL
    test_url = "https://www.youtube.com/watch?v=-VPYbJxPvzY"

    # API endpoint
    api_url = "http://localhost:4000/api/download"

    # Request payload
    payload = {
        "url": test_url,
        "quality": "best"
    }

    print(f"📺 Testing download for: {test_url}")
    print(f"🎯 API endpoint: {api_url}")
    print(f"📦 Request: {json.dumps(payload, indent=2)}")
    print()

    try:
        print("⏳ Sending download request...")
        response = requests.post(api_url, json=payload, stream=True)

        print(f"📊 Response status: {response.status_code}")

        if response.status_code == 200:
            # Get filename from response headers
            content_disposition = response.headers.get('Content-Disposition', '')
            filename = 'downloaded_video.mp4'  # fallback

            if 'filename=' in content_disposition:
                filename = content_disposition.split('filename=')[1].strip('"')

            print(f"✅ Download successful!")
            print(f"📁 Filename: {filename}")
            print(f"📏 Content length: {response.headers.get('Content-Length', 'Unknown')} bytes")

            # Save the file
            with open(filename, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            print(f"💾 File saved as: {filename}")

        else:
            print("❌ Download failed!")
            try:
                error_data = response.json()
                print(f"🚨 Error: {error_data.get('error', 'Unknown error')}")
            except:
                print(f"🚨 Response: {response.text}")

    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        print("💡 Make sure the API server is running with: python youtube_api.py")

if __name__ == "__main__":
    test_download_api()
