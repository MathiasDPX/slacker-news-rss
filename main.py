from rss_parser import RSSParser
from dotenv import load_dotenv
from os import getenv, path
from threading import Thread, Lock
import random
import time
import requests
import logging
import json
import xmltodict

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from utils import HEADERS, build_blocks

load_dotenv()
logging.basicConfig(
    level=getenv("LOG_LEVEL", "INFO"), format="%(asctime)s - %(levelname)s - %(message)s"
)


RSS_FEED = getenv("RSS_FEED")
SLACK_BOT_TOKEN = getenv("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = getenv("SLACK_APP_TOKEN")
SLACK_CHANNELS = getenv("SLACK_CHANNELS")
DATABASE_PATH = getenv("DATABASE_PATH", "database.json")
INTERVAL_SECONDS = int(getenv("INTERVAL_SECONDS", "1800"))

missing = [
    name
    for name, value in {
        "RSS_FEED": RSS_FEED,
        "SLACK_BOT_TOKEN": SLACK_BOT_TOKEN,
        "SLACK_APP_TOKEN": SLACK_APP_TOKEN
    }.items()
    if not value
]
if missing:
    for name in missing:
        logging.error(f"Missing {name} environment variable")
    exit(1)


if not path.exists(DATABASE_PATH):
    with open(DATABASE_PATH, "w+", encoding="utf-8") as f:
        json.dump([], f)

with open(DATABASE_PATH, "r", encoding="utf-8") as f:
    database = json.load(f)

db_lock = Lock()

app = App(token=SLACK_BOT_TOKEN)


def save_database():
    with open(DATABASE_PATH, "w+", encoding="utf-8") as f:
        json.dump(database, f, ensure_ascii=False, indent=2)


def send_message(channel, entry, raw_entry):
    title, description, blocks = build_blocks(entry, raw_entry)
    return app.client.chat_postMessage(
        channel=channel,
        text=f"{title}\n> {description}",
        blocks=blocks,
        unfurl_links=False,
        unfurl_media=False
    )


@app.command("/news-test")
def test_command(ack, respond, command):
    ack()

    guid = command.get("text", "").strip()

    r = requests.get(RSS_FEED, headers=HEADERS)
    r.raise_for_status()
    data = r.content.decode("utf-8")

    raw = xmltodict.parse(data)
    feed = RSSParser().parse(data)
    raw_items = raw.get("rss", {}).get("channel", {}).get("item", [])
    if not isinstance(raw_items, list):
        raw_items = [raw_items]

    if guid == "":
        entry = random.choice(feed.channel.items)
    else:
        mapped_entries = {entry.guid.content.strip(): entry for entry in feed.channel.items}
        if guid not in mapped_entries.keys():
            respond("Post not found")
            return

        entry = mapped_entries[guid]

    idx = feed.channel.items.index(entry)
    title, description, blocks = build_blocks(entry, raw_items[idx])
    respond(
        text=f"{title}\n> {description}",
        blocks=blocks,
        unfurl_links=False,
        unfurl_media=False
    )


def check_feed():
    try:
        r = requests.get(RSS_FEED, headers=HEADERS)
        r.raise_for_status()
        data = r.content.decode("utf-8")
    except Exception as e:
        logging.error(f"Failed to fetch RSS feed: {e}")
        return 0

    feed = RSSParser().parse(data)
    raw = xmltodict.parse(data)
    raw_items = raw.get("rss", {}).get("channel", {}).get("item", [])
    if not isinstance(raw_items, list):
        raw_items = [raw_items]

    channels = get_bot_channels()

    new_count = 0
    with db_lock:
        for i, entry in enumerate(feed.channel.items):
            guid = entry.guid.content

            if guid not in database:
                raw_entry = raw_items[i] if i < len(raw_items) else {}
                for channel in channels:
                    try:
                        send_message(channel, entry, raw_entry)
                    except Exception as e:
                        logging.error(
                            f"Failed to send {guid} notification to {channel}: {e}")

                logging.info(f"New article -> {entry.title.content}")
                database.append(guid)
                new_count += 1

        if new_count:
            logging.info(
                f"Sent posts to {len(channels)} channels: {', '.join(channels)}")
            save_database()

    return new_count


def get_bot_channels():
    if SLACK_CHANNELS != None:
        return SLACK_CHANNELS.split(",")

    channels = app.client.users_conversations(
        types="public_channel,private_channel",
        limit=1000
    )["channels"]

    return [c["id"] for c in channels]


def poll_loop():
    while True:
        logging.info("Checking RSS feed...")
        check_feed()
        logging.info(f"Sleeping for {INTERVAL_SECONDS}s...")
        time.sleep(INTERVAL_SECONDS)


def main():
    Thread(target=poll_loop, daemon=True).start()
    SocketModeHandler(app, SLACK_APP_TOKEN).start()


if __name__ == "__main__":
    main()
