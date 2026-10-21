# api/webhook.py
# language: Python, runtime: Vercel Serverless (Python 3.12), target: webhook handler
import os
import sys
import json
import asyncio
import logging
from http.server import BaseHTTPRequestHandler

# make sibling bot_logic.py importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram import Update
from bot_logic import build_application

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("vercel-webhook")

APP = build_application()  # cold-start once, reuse across warm invocations


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            length = int(self.headers.get("content-length", 0))
            body = self.rfile.read(length).decode("utf-8")
            data = json.loads(body)
            update = Update.de_json(data, APP.bot)

            asyncio.run(APP.initialize())
            asyncio.run(APP.process_update(update))

            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
        except Exception as e:
            log.exception("webhook failure")
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(e).encode())

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"eiin-bot webhook alive")
