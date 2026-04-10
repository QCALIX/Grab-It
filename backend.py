import os
import re
import shutil
import tempfile
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from yt_dlp import YoutubeDL

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)
UA = 'Mozilla/5.0'

def normalize_quality(q):
    q = (q or '').strip().lower()
    if q.endswith('p'):
        q = q[:-1]
    return q if q.isdigit() else ''

def safe_name(name):
    name = re.sub(r'[\/:*?"<>|]+', '', name or 'download').strip()
    return name[:80] or 'download'

def ydl_opts_info():
    return {'quiet': True, 'no_warnings': True, 'skip_download': True, 'noplaylist': True, 'user_agent': UA}

def ydl_opts_download(fmt, quality, outdir):
    quality = normalize_quality(quality)
    common = {'quiet': True, 'no_warnings': True, 'noplaylist': True, 'outtmpl': os.path.join(outdir, '%(title).80s.%(ext)s'), 'user_agent': UA}
    if fmt == 'mp3':
        common['format'] = 'bestaudio/best'
        common['postprocessors'] = [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}]
        return common
    if fmt == 'wav':
        common['format'] = 'bestaudio/best'
        common['postprocessors'] = [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'wav'}]
        return common
    common['format'] = f'bestvideo[height<={quality}]+bestaudio/best[height<={quality}]' if quality else 'bestvideo+bestaudio/best'
    common['merge_output_format'] = 'mp4'
    return common

@app.route('/')
def index():
    return app.send_static_file('index.html')

@app.route('/download', methods=['POST'])
def download():
    data = request.get_json(silent=True) or {}
    url = (data.get('url') or '').strip()
    action = (data.get('action') or 'download').strip().lower()
    fmt = (data.get('format') or 'mp4').strip().lower()
    quality = data.get('quality') or ''
    if not url:
        return jsonify({'error': 'Missing URL'}), 400
    if fmt not in {'mp4', 'mp3', 'wav'}:
        return jsonify({'error': 'Invalid format'}), 400
    try:
        if action == 'info':
            with YoutubeDL(ydl_opts_info()) as ydl:
                info = ydl.extract_info(url, download=False)
            title = info.get('title') or 'Untitled'
            thumb = info.get('thumbnail') or ''
            duration = info.get('duration') or 0
            uploader = info.get('uploader') or info.get('channel') or info.get('extractor_key') or ''
            formats = []
            for f in info.get('formats') or []:
                h = f.get('height')
                if h:
                    formats.append({'id': f.get('format_id') or str(h), 'label': f'{h}p', 'height': h})
            uniq = []
            seen = set()
            for f in sorted(formats, key=lambda x: x['height'], reverse=True):
                if f['height'] not in seen:
                    uniq.append(f)
                    seen.add(f['height'])
            if not uniq and fmt == 'mp4':
                uniq = [{'id': 'best', 'label': 'Best', 'height': 0}]
            return jsonify({'title': title, 'thumbnail': thumb, 'duration': duration, 'uploader': uploader, 'formats': uniq})
        tmpdir = tempfile.mkdtemp(prefix='reclip_')
        before = set(os.listdir(tmpdir))
        try:
            opts = ydl_opts_download(fmt, quality, tmpdir)
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if info.get('_type') == 'playlist':
                    info = info['entries'][0]
            after = set(os.listdir(tmpdir))
            files = [os.path.join(tmpdir, f) for f in (after - before)] or [os.path.join(tmpdir, f) for f in os.listdir(tmpdir)]
            files = [f for f in files if os.path.isfile(f)]
            if not files:
                return jsonify({'error': 'No output file was created'}), 500
            path = max(files, key=lambda p: os.path.getsize(p))
            title = safe_name(info.get('title') or 'download')
            return send_file(path, as_attachment=True, download_name=f'{title}.{fmt}', mimetype='application/octet-stream')
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
