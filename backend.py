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

def ydl_opts_for_info():
    return {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'noplaylist': True,
        'user_agent': UA,
    }

def ydl_opts_for_download(fmt, quality, outdir):
    quality = normalize_quality(quality)
    if fmt == 'mp3':
        return {
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'outtmpl': os.path.join(outdir, '%(title).80s.%(ext)s'),
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'user_agent': UA,
        }
    if fmt == 'wav':
        return {
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'outtmpl': os.path.join(outdir, '%(title).80s.%(ext)s'),
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'wav',
            }],
            'user_agent': UA,
        }
    # mp4
    if quality:
        fmt_sel = f'bestvideo[height<={quality}]+bestaudio/best[height<={quality}]'
    else:
        fmt_sel = 'bestvideo+bestaudio/best'
    return {
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'outtmpl': os.path.join(outdir, '%(title).80s.%(ext)s'),
        'format': fmt_sel,
        'merge_output_format': 'mp4',
        'user_agent': UA,
    }

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

    if action == 'info':
        try:
            with YoutubeDL(ydl_opts_for_info()) as ydl:
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
            seen = set()
            uniq = []
            for f in sorted(formats, key=lambda x: x['height'], reverse=True):
                if f['height'] not in seen:
                    uniq.append(f)
                    seen.add(f['height'])
            if not uniq and fmt == 'mp4':
                uniq = [{'id': 'best', 'label': 'Best', 'height': 0}]
            return jsonify({'title': title, 'thumbnail': thumb, 'duration': duration, 'uploader': uploader, 'formats': uniq})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    tmpdir = tempfile.mkdtemp(prefix='reclip_')
    try:
        before = set(os.listdir(tmpdir))
        opts = ydl_opts_for_download(fmt, quality, tmpdir)
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if info.get('_type') == 'playlist':
                info = info['entries'][0]
        after = set(os.listdir(tmpdir))
        files = [os.path.join(tmpdir, f) for f in after - before]
        if not files:
            files = [os.path.join(tmpdir, f) for f in os.listdir(tmpdir)]
        files = [f for f in files if os.path.isfile(f)]
        if not files:
            return jsonify({'error': 'No output file was created'}), 500
        path = max(files, key=lambda p: os.path.getsize(p))
        title = safe_name(info.get('title') or 'download')
        ext = fmt
        outname = f'{title}.{ext}'
        return send_file(path, as_attachment=True, download_name=outname, mimetype='application/octet-stream')
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
