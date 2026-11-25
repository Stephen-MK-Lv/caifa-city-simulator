"""Local-only entry point. Never stops an unrelated service on a busy port."""
import os
from pathlib import Path
import socket
import sys
import threading
import time
from urllib.request import urlopen
import webbrowser

ROOT = Path(__file__).resolve().parent


def main():
    os.chdir(ROOT)
    os.environ.setdefault('CAIFA_AUTH_REQUIRED', '1')
    try:
        # Railway and similar platforms provide PORT at runtime. Keep the
        # existing local port defaults for desktop use.
        port = int(os.environ.get('CAIFA_PORT') or os.environ.get('MINGCHUAN_PORT')
                   or os.environ.get('PORT') or '8765')
        if not 1024 <= port <= 65535:
            raise ValueError
    except ValueError:
        print('CAIFA_PORT must be an integer between 1024 and 65535.')
        return 1
    try:
        host = os.environ.get('CAIFA_HOST', '127.0.0.1')
        with socket.socket() as probe:
            probe.bind((host, port))
    except OSError:
        print(f'Port {port} is already in use. No existing process was stopped.')
        print(f'If this application is already running, open http://{host}:{port}')
        print('Otherwise set CAIFA_PORT to another unused port.')
        return 1
    import uvicorn
    browser_host = '127.0.0.1' if host in {'0.0.0.0', '::'} else host
    url = f'http://{browser_host}:{port}'
    print(f'Caifa city simulator: {url}\nPress Ctrl+C to stop the local server.')

    def open_when_ready():
        for _ in range(50):
            try:
                with urlopen(url+'/api/health', timeout=1) as response:
                    if response.status == 200:
                        webbrowser.open(url)
                        return
            except OSError:
                time.sleep(.2)

    if '--no-browser' not in sys.argv:
        threading.Thread(target=open_when_ready, daemon=True).start()
    # One process owns the teaching clock. Do not use --reload for classroom runs.
    uvicorn.run('app.main:app', host=host, port=port, workers=1, log_level='info')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
