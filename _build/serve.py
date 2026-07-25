#!/usr/bin/env python3
"""Локальный просмотр сайта: python3 _build/serve.py [порт]"""

import functools
import http.server
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8123

handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT)
print(f"http://localhost:{PORT}", flush=True)
http.server.ThreadingHTTPServer(("127.0.0.1", PORT), handler).serve_forever()
