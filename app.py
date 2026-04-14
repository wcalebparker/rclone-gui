import os, re, json, queue, shutil, threading, subprocess, uuid, platform, signal, sys, ssl
import urllib.request, zipfile, configparser, webbrowser
from flask import Flask, render_template, jsonify, request, Response, stream_with_context

# ── PyInstaller bundle detection ───────────────────────────────────────────
# When frozen by PyInstaller:
#   sys.frozen     = True
#   sys._MEIPASS   = temp dir where templates/static are extracted
#   sys.executable = path to the actual binary inside the .app
FROZEN      = getattr(sys, 'frozen', False)
BUNDLE_DIR  = sys._MEIPASS if FROZEN else os.path.dirname(os.path.abspath(__file__))
APP_DIR     = os.path.dirname(sys.executable) if FROZEN else os.path.dirname(os.path.abspath(__file__))

# ── SSL certificate fix ────────────────────────────────────────────────────
# PyInstaller strips macOS system SSL cert paths.  We bundle certifi's
# cacert.pem as a data file (see rclone-gui.spec datas list) and point the
# two standard env-vars at it *before* any network code runs.  This is more
# reliable than passing cafile= to each ssl.create_default_context() call
# because it also covers any library that opens its own SSL connections.
if FROZEN:
    _cert_file = os.path.join(BUNDLE_DIR, 'certifi', 'cacert.pem')
    if os.path.isfile(_cert_file):
        os.environ['SSL_CERT_FILE']      = _cert_file
        os.environ['REQUESTS_CA_BUNDLE'] = _cert_file

# When bundled, store rclone in ~/Library/Application Support so it persists
# across app updates (the .app bundle itself is read-only after install).
RCLONE_DATA_DIR = os.path.expanduser('~/Library/Application Support/rclone-gui')
os.makedirs(RCLONE_DATA_DIR, exist_ok=True)

app = Flask(__name__,
            template_folder=os.path.join(BUNDLE_DIR, 'templates'),
            static_folder=os.path.join(BUNDLE_DIR, 'static'))
ANSI = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
active_jobs = {}
APP_VERSION = "1.0.9"

def https_get(url, timeout=15):
    """Perform a simple HTTPS GET and return the response object."""
    req = urllib.request.Request(url, headers={'User-Agent': f'rclone-gui/{APP_VERSION}'})
    return urllib.request.urlopen(req, timeout=timeout)


# ── Helpers ────────────────────────────────────────────────────────────────

def strip_ansi(t):
    return ANSI.sub('', t)

def find_rclone():
    """Check persistent data dir first, then app folder, then system PATH."""
    for candidate in [
        os.path.join(RCLONE_DATA_DIR, 'rclone'),   # bundled app (persistent)
        os.path.join(APP_DIR, 'rclone'),             # dev/project folder
    ]:
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return shutil.which('rclone')

def rclone_conf_path():
    return os.path.expanduser('~/.config/rclone/rclone.conf')

def get_remote_types():
    """Return dict of remote_name: type, e.g. {'gdrive:': 'drive'}"""
    path = rclone_conf_path()
    if not os.path.exists(path):
        return {}
    cfg = configparser.RawConfigParser()
    cfg.optionxform = str
    cfg.read(path)
    return {s + ':': cfg.get(s, 'type', fallback='unknown') for s in cfg.sections()}

def write_remote_config(name, params):
    path = rclone_conf_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    cfg = configparser.RawConfigParser()
    cfg.optionxform = str
    if os.path.exists(path):
        cfg.read(path)
    cfg[name] = params
    with open(path, 'w') as f:
        cfg.write(f)

def _new_job():
    jid = str(uuid.uuid4())
    active_jobs[jid] = {'queue': queue.Queue(), 'process': None}
    return jid

def _run_thread(fn, *args):
    jid = _new_job()
    threading.Thread(target=fn, args=(jid, *args), daemon=True).start()
    return jid


# ── Status ─────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/status')
def status():
    rc = find_rclone()
    if not rc:
        return jsonify({'installed': False, 'remotes': []})
    try:
        ver = subprocess.run([rc, 'version'], capture_output=True, text=True,
                             timeout=8, stdin=subprocess.DEVNULL)
        version = ver.stdout.split('\n')[0].strip() if ver.returncode == 0 else ''
        rem = subprocess.run([rc, 'listremotes'], capture_output=True, text=True,
                             timeout=8, stdin=subprocess.DEVNULL)
        remotes = [r.strip() for r in rem.stdout.strip().split('\n') if r.strip()]
        return jsonify({'installed': True, 'version': version, 'remotes': remotes,
                        'types': get_remote_types(), 'app_version': APP_VERSION})
    except Exception as e:
        return jsonify({'installed': True, 'version': '', 'remotes': [], 'error': str(e),
                        'app_version': APP_VERSION})

@app.route('/api/app-version')
def app_version_route():
    return jsonify({'version': APP_VERSION})

@app.route('/api/check-app-update')
def check_app_update():
    try:
        req = urllib.request.Request(
            'https://api.github.com/repos/wcalebparker/rclone-gui/releases/latest',
            headers={'User-Agent': 'rclone-gui/' + APP_VERSION, 'Accept': 'application/vnd.github+json'})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
        latest = data.get('tag_name', '').lstrip('v')
        if not latest:
            return jsonify({'update_available': False})
        cur_t = tuple(int(x) for x in APP_VERSION.split('.'))
        lat_t = tuple(int(x) for x in latest.split('.'))
        return jsonify({
            'update_available': lat_t > cur_t,
            'latest': latest,
            'current': APP_VERSION,
            'download_url': data.get('html_url', ''),
            'release_notes': data.get('body', '')
        })
    except Exception as e:
        return jsonify({'update_available': False, 'error': str(e)})

@app.route('/api/remotes')
def list_remotes():
    rc = find_rclone()
    if not rc:
        return jsonify({'remotes': []})
    try:
        r = subprocess.run([rc, 'listremotes'], capture_output=True, text=True,
                           timeout=8, stdin=subprocess.DEVNULL)
        return jsonify({'remotes': [x.strip() for x in r.stdout.strip().split('\n') if x.strip()], 'types': get_remote_types()})
    except Exception as e:
        return jsonify({'remotes': [], 'error': str(e)})


# ── Auto-install rclone ────────────────────────────────────────────────────

def _install_rclone(jid):
    q = active_jobs[jid]['queue']
    try:
        arch = 'arm64' if platform.machine().lower() in ('arm64', 'aarch64') else 'amd64'
        url  = f'https://downloads.rclone.org/rclone-current-osx-{arch}.zip'
        dest_bin = os.path.join(RCLONE_DATA_DIR if FROZEN else APP_DIR, 'rclone')
        tmp_zip  = os.path.join(RCLONE_DATA_DIR if FROZEN else APP_DIR, '_rclone_dl.zip')

        q.put({'type': 'status', 'text': 'Downloading…'})

        # Stream download with progress (urlretrieve doesn't support SSL context)
        with https_get(url) as resp:
            total = int(resp.headers.get('Content-Length', 0))
            downloaded = 0
            chunk_size = 65536
            with open(tmp_zip, 'wb') as f:
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total > 0:
                        q.put({'type': 'progress', 'pct': min(99, int(downloaded * 100 / total))})
        q.put({'type': 'status', 'text': 'Unpacking…'})

        with zipfile.ZipFile(tmp_zip, 'r') as zf:
            for name in zf.namelist():
                if name.endswith('/rclone') or name == 'rclone':
                    with zf.open(name) as src, open(dest_bin, 'wb') as out:
                        out.write(src.read())
                    break

        os.chmod(dest_bin, 0o755)
        os.remove(tmp_zip)
        q.put({'type': 'progress', 'pct': 100})
        q.put({'type': 'done', 'success': True})
    except Exception as e:
        q.put({'type': 'done', 'success': False, 'error': str(e)})

@app.route('/api/install-rclone', methods=['POST'])
def install_rclone_route():
    return jsonify({'job_id': _run_thread(_install_rclone)})


# ── Connect cloud storage (OAuth) ──────────────────────────────────────────

def _authorize_remote(jid, name, rtype, extra):
    q = active_jobs[jid]['queue']
    rc = find_rclone()
    try:
        q.put({'type': 'browser_opening'})
        cmd = [rc, 'authorize', rtype]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL, text=True)
        active_jobs[jid]['process'] = proc

        lines = []
        for raw in proc.stdout:
            line = strip_ansi(raw).rstrip()
            lines.append(line)
            q.put({'type': 'line', 'text': line})
        proc.wait()

        # Extract token JSON from rclone output
        full = '\n'.join(lines)
        token = None

        # Primary: between ---> and <---
        m = re.search(r'--->\s*([\s\S]+?)\s*<---', full)
        if m:
            candidate = m.group(1).strip()
            try:
                json.loads(candidate)
                token = candidate
            except Exception:
                pass

        # Fallback: any JSON blob with access_token
        if not token:
            m2 = re.search(r'(\{"access_token"[^\n]+\})', full)
            if m2:
                token = m2.group(1).strip()

        if not token:
            q.put({'type': 'done', 'success': False,
                   'error': 'Could not complete sign-in. Please try again.'})
            return

        write_remote_config(name, {'type': rtype, 'token': token, **extra})
        q.put({'type': 'done', 'success': True})
    except Exception as e:
        q.put({'type': 'done', 'success': False, 'error': str(e)})

@app.route('/api/authorize-remote', methods=['POST'])
def authorize_remote():
    d = request.json or {}
    name  = d.get('name', '').strip()
    rtype = d.get('type', '').strip()
    extra = d.get('extra', {})
    if not name or not rtype:
        return jsonify({'error': 'Name and type required'}), 400
    return jsonify({'job_id': _run_thread(_authorize_remote, name, rtype, extra)})


def _create_keyed_remote(jid, name, params):
    q = active_jobs[jid]['queue']
    try:
        write_remote_config(name, params)
        q.put({'type': 'done', 'success': True})
    except Exception as e:
        q.put({'type': 'done', 'success': False, 'error': str(e)})

@app.route('/api/create-keyed-remote', methods=['POST'])
def create_keyed_remote():
    d = request.json or {}
    name = d.get('name', '').strip()
    params = d.get('params', {})
    if not name or not params:
        return jsonify({'error': 'Name and params required'}), 400
    return jsonify({'job_id': _run_thread(_create_keyed_remote, name, params)})

@app.route('/api/delete-remote', methods=['POST'])
def delete_remote():
    name = (request.json or {}).get('name', '').strip().rstrip(':')
    rc = find_rclone()
    if not rc or not name:
        return jsonify({'ok': False}), 400
    subprocess.run([rc, 'config', 'delete', name], capture_output=True, stdin=subprocess.DEVNULL)
    return jsonify({'ok': True})


def _create_server_remote(jid, name, params, password):
    """Like create-keyed-remote but obscures the password via rclone obscure."""
    q = active_jobs[jid]['queue']
    try:
        if password:
            rc = find_rclone()
            result = subprocess.run([rc, 'obscure', password],
                                    capture_output=True, text=True,
                                    stdin=subprocess.DEVNULL)
            if result.returncode == 0:
                params['pass'] = result.stdout.strip()
        write_remote_config(name, params)
        q.put({'type': 'done', 'success': True})
    except Exception as e:
        q.put({'type': 'done', 'success': False, 'error': str(e)})

@app.route('/api/create-server-remote', methods=['POST'])
def create_server_remote():
    d = request.json or {}
    name     = d.get('name', '').strip()
    params   = d.get('params', {})
    password = d.get('password', '')
    if not name or not params:
        return jsonify({'error': 'Name and params required'}), 400
    return jsonify({'job_id': _run_thread(_create_server_remote, name, params, password)})


# ── Version check / update ─────────────────────────────────────────────────

@app.route('/api/check-update')
def check_update():
    rc = find_rclone()
    if not rc:
        return jsonify({'error': 'rclone not installed'})
    try:
        ver = subprocess.run([rc, 'version'], capture_output=True, text=True,
                             timeout=8, stdin=subprocess.DEVNULL)
        current_line = ver.stdout.split('\n')[0].strip() if ver.returncode == 0 else ''
        m = re.search(r'v(\d+\.\d+\.\d+)', current_line)
        current = m.group(1) if m else ''

        with https_get('https://downloads.rclone.org/version.txt', timeout=8) as resp:
            latest_raw = resp.read().decode().strip()
        m2 = re.search(r'v(\d+\.\d+\.\d+)', latest_raw)
        latest = m2.group(1) if m2 else ''

        update_available = False
        if current and latest:
            cur_t = tuple(int(x) for x in current.split('.'))
            lat_t = tuple(int(x) for x in latest.split('.'))
            update_available = lat_t > cur_t

        return jsonify({'current': current, 'latest': latest,
                        'update_available': update_available})
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/api/update-rclone', methods=['POST'])
def update_rclone_route():
    return jsonify({'job_id': _run_thread(_install_rclone)})


# ── Native macOS folder picker ─────────────────────────────────────────────

@app.route('/api/pick-folder')
def pick_folder():
    script = '''
        tell application "Finder" to activate
        try
            set f to choose folder with prompt "Select a folder:"
            return POSIX path of f
        on error
            return ""
        end try
    '''
    try:
        r = subprocess.run(['osascript', '-e', script],
                           capture_output=True, text=True, timeout=300)
        path = r.stdout.strip()
        if path:
            return jsonify({'path': path})
        return jsonify({'path': None, 'cancelled': True})
    except Exception as e:
        return jsonify({'path': None, 'error': str(e)})


# ── Browse remote directories ──────────────────────────────────────────────

@app.route('/api/browse')
def browse():
    path      = request.args.get('path', '').strip()
    extra_flags = request.args.get('flags', '')   # e.g. '--drive-shared-with-me'
    rc = find_rclone()
    if not path or not rc:
        return jsonify({'items': [], 'error': 'Missing path or rclone'})
    try:
        cmd = [rc, 'lsf', path]
        if extra_flags:
            cmd += [f for f in extra_flags.split(',') if f.strip().startswith('--')]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=20,
                           stdin=subprocess.DEVNULL)
        items = []
        for line in r.stdout.strip().split('\n'):
            line = line.strip()
            if not line:
                continue
            if line.endswith('/'):
                items.append({'name': line.rstrip('/'), 'kind': 'dir'})
            else:
                items.append({'name': line, 'kind': 'file'})
        # Dirs first, then files
        items.sort(key=lambda x: (0 if x['kind'] == 'dir' else 1, x['name'].lower()))
        return jsonify({'items': items, 'error': r.stderr.strip() if r.returncode != 0 else None})
    except subprocess.TimeoutExpired:
        return jsonify({'items': [], 'error': 'Timed out listing folders.'})
    except Exception as e:
        return jsonify({'items': [], 'error': str(e)})


# ── Copy / Check ───────────────────────────────────────────────────────────

def _run_rclone(jid, cmd):
    q = active_jobs[jid]['queue']
    try:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             stdin=subprocess.DEVNULL, text=True, bufsize=1)
        active_jobs[jid]['process'] = p
        for line in p.stdout:
            t = strip_ansi(line).rstrip()
            if t:
                q.put({'type': 'line', 'text': t})
        p.wait()
        q.put({'type': 'done', 'success': p.returncode == 0, 'code': p.returncode})
    except Exception as e:
        q.put({'type': 'line', 'text': f'Error: {e}'})
        q.put({'type': 'done', 'success': False, 'code': -1})

@app.route('/api/copy', methods=['POST'])
def copy():
    d = request.json or {}
    src, dst = d.get('source','').strip(), d.get('dest','').strip()
    if not src or not dst:
        return jsonify({'error': 'Source and destination required'}), 400
    rc = find_rclone()
    cmd = [rc, 'copy', src, dst, '--verbose', '--stats-one-line', '--stats', '2s']
    if d.get('dry_run'):
        cmd.append('--dry-run')
    for flag in d.get('flags', []):
        if flag.startswith('--'):
            cmd.append(flag)
    jid = _new_job()
    threading.Thread(target=_run_rclone, args=(jid, cmd), daemon=True).start()
    return jsonify({'job_id': jid})

@app.route('/api/check', methods=['POST'])
def check():
    d = request.json or {}
    src, dst = d.get('source','').strip(), d.get('dest','').strip()
    if not src or not dst:
        return jsonify({'error': 'Source and destination required'}), 400
    rc = find_rclone()
    cmd = [rc, 'check', src, dst, '--verbose']
    for flag in d.get('flags', []):
        if flag.startswith('--'):
            cmd.append(flag)
    jid = _new_job()
    threading.Thread(target=_run_rclone, args=(jid, cmd), daemon=True).start()
    return jsonify({'job_id': jid})


# ── SSE stream ─────────────────────────────────────────────────────────────

@app.route('/api/stream/<jid>')
def stream(jid):
    if jid not in active_jobs:
        return jsonify({'error': 'Job not found'}), 404
    def generate():
        q = active_jobs[jid]['queue']
        while True:
            try:
                msg = q.get(timeout=30)
                yield f"data: {json.dumps(msg)}\n\n"
                if msg.get('type') == 'done':
                    break
            except queue.Empty:
                yield f"data: {json.dumps({'type':'heartbeat'})}\n\n"
    return Response(stream_with_context(generate()),
                    mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


# ── Quit ───────────────────────────────────────────────────────────────────

@app.route('/api/quit', methods=['POST'])
def quit_app():
    def _stop():
        import time; time.sleep(0.4)
        os.kill(os.getpid(), signal.SIGTERM)
    threading.Thread(target=_stop, daemon=True).start()
    return jsonify({'ok': True})


@app.route('/api/open-browser', methods=['POST'])
def open_browser_route():
    """Called by a second app instance to make the running server open the browser.
    This is more reliable than the short-lived second process trying to call
    webbrowser.open() itself before it exits."""
    threading.Thread(
        target=lambda: webbrowser.open('http://localhost:5001'), daemon=True
    ).start()
    return jsonify({'ok': True})


# ── Launch ─────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import time
    print('rclone GUI → http://localhost:5001')

    if FROZEN:
        import urllib.request as _ur

        # Check if a server is already running on port 5001
        already_running = False
        try:
            _ur.urlopen('http://127.0.0.1:5001', timeout=1)
            already_running = True
        except Exception:
            pass

        if already_running:
            # Tell the running server to open a browser tab, then exit gracefully.
            # We do this via HTTP so the *server* process (which owns the desktop
            # session properly) calls webbrowser.open — much more reliable than
            # the short-lived second instance doing it.
            try:
                req = urllib.request.Request(
                    'http://127.0.0.1:5001/api/open-browser',
                    data=b'', method='POST'
                )
                _ur.urlopen(req, timeout=2)
            except Exception:
                # Fallback: try opening the browser directly
                webbrowser.open('http://localhost:5001')
            # Stay alive briefly so macOS doesn't show "not open anymore"
            time.sleep(1.5)
        else:
            # First instance — poll until Flask is ready, then open browser
            def _open_browser():
                for _ in range(40):
                    try:
                        _ur.urlopen('http://127.0.0.1:5001', timeout=0.5)
                        break
                    except Exception:
                        time.sleep(0.5)
                webbrowser.open('http://localhost:5001')
            threading.Thread(target=_open_browser, daemon=True).start()
            app.run(host='127.0.0.1', port=5001, debug=False, use_reloader=False)
    else:
        app.run(host='127.0.0.1', port=5001, debug=False, use_reloader=False)
