import sys
import re
import threading
from flask import Flask, request
from briefing import run_briefing, run_card, load_config

sys.stdout.reconfigure(encoding="utf-8")

app = Flask(__name__)


def _get_run_token():
    return load_config().get("RUN_TOKEN", "")


@app.route("/run", methods=["GET", "POST"])
def scheduled_run():
    token = request.args.get("token", "")
    if not token or token != _get_run_token():
        return "Unauthorized", 401
    config = load_config()
    threading.Thread(target=run_briefing, args=(config,), daemon=True).start()
    return "OK", 200


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(silent=True) or {}
    message = data.get("message", {})
    text = message.get("text", "")

    if "브리핑" in text:
        config = load_config()
        threading.Thread(target=run_briefing, args=(config,), daemon=True).start()

    elif "카드" in text:
        config = load_config()
        threading.Thread(target=run_card, args=(config,), daemon=True).start()

    elif "http" in text:
        url_match = re.search(r"https?://\S+", text)
        if url_match:
            config = load_config()
            source_url = url_match.group()
            threading.Thread(
                target=run_card,
                args=(config,),
                kwargs={"source_url": source_url},
                daemon=True,
            ).start()

    return "OK", 200


if __name__ == "__main__":
    app.run()
