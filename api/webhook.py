# api/webhook.py
# language: Python, runtime: Vercel Serverless (Python 3.12), target: Webhook handler
import os
import json
import logging
from http.server import BaseHTTPRequestHandler

from telegram import Update
from telegram.ext import Application

# import your handlers from bot_logic.py
from bot_logic import build_application

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("vercel-webhook")

BOT_TOKEN = os.environ["BOT_TOKEN"]
# APP is created once per cold start — reuse across warm invocations
APP: Application = build_application(BOT_TOKEN)


class handler(BaseHTTPRequestHandler):
    """Vercel expects a class named `handler` in api/*.py."""

    def do_POST(self):
        try:
            length = int(self.headers.get("content-length", 0))
            body = self.rfile.read(length).decode("utf-8")
            data = json.loads(body)
            update = Update.de_json(data, APP.bot)

            # process the update asynchronously
            import asyncio
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
        """Health check — useful to verify the function is alive."""
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"eiin-bot webhook alive")
