# api/webhook.py
import os
import sys
import json
import asyncio
import logging
from flask import Flask, request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram import Update
from bot_logic import build_application

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("vercel-webhook")

APP = build_application()
app = Flask(__name__)

@app.route("/api/webhook", methods=["POST", "GET"])
def webhook():
    if request.method == "GET":
        return "eiin-bot webhook alive", 200

    try:
        data = request.get_json(force=True)
        update = Update.de_json(data, APP.bot)
        
        # Run the async update processing
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(APP.initialize())
        loop.run_until_complete(APP.process_update(update))
        loop.close()
        
        return "ok", 200
    except Exception as e:
        log.exception("Webhook failed")
        return str(e), 500
