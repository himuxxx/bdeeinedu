# api/webhook.py
import os
import sys
import json
import asyncio
import logging
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram import Update
from bot_logic import build_application

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("vercel-webhook")

APP = build_application()

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            length = int(self.headers.get("content-length", 0))
            body = self.rfile.read(length).decode("utf-8")
            data = json.loads(body)
            update = Update.de_json(data, APP.bot)

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(APP.initialize())
            loop.run_until_complete(APP.process_update(update))
            loop.run_until_complete(APP.shutdown())
            loop.close()

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
