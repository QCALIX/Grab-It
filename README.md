# Grab-It / ReClip-style downloader

## Run locally
1. Install Python 3.11+
2. Create a virtual environment
3. Install dependencies: `pip install -r requirements.txt`
4. Install FFmpeg
5. Start server: `python backend.py`
6. Open `http://localhost:5000`

## Endpoints
- `POST /download` with `{ "url": "...", "action": "info" }`
- `POST /download` with `{ "url": "...", "action": "download", "format": "mp4|mp3|wav", "quality": "720p" }`

## Notes
- MP4 uses yt-dlp merge output.
- MP3/WAV use FFmpegExtractAudio.
- FFmpeg must be installed on the host.
