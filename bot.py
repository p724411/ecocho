import sys
import threading
from flask import Flask, request
from briefing import main as run_briefing

sys.stdout.reconfigure(encoding="utf-8")

app = Flask(__name__)


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(silent=True) or {}
    message = data.get("message", {})
    text = message.get("text", "")
    reply_to = message.get("reply_to_message")

    if "요청" in text or reply_to:
        threading.Thread(target=run_briefing, daemon=True).start()

    return "OK", 200


if __name__ == "__main__":
    app.run()
