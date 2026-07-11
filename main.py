from rss_parser import RSSParser
from dotenv import load_dotenv
from os import getenv, path
from email.utils import parsedate_to_datetime
from threading import Thread, Lock
import re
import time
import requests
import logging
import json
import xmltodict

from bs4 import BeautifulSoup
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

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


def smart_cut(text, limit):
    if len(text) > limit:
        cut = text[:limit - 3]
        if " " in cut:
            cut = cut.rsplit(" ", 1)[0]
        text = cut + "..."

    return text


def get_authors(link):
    try:
        r = requests.get(link)
        soup = BeautifulSoup(r.text, "html.parser")

        # Follow meta-refresh redirects
        meta = soup.find("meta", attrs={"http-equiv": "refresh"})
        if meta:
            content = meta.get("content", "")
            match = re.search(r"url=(.+)", content, re.IGNORECASE)
            if match:
                from urllib.parse import urljoin
                target = match.group(1).strip()
                if target.startswith("/"):
                    target = urljoin(r.url, target)
                r = requests.get(target)
                soup = BeautifulSoup(r.text, "html.parser")

        span = soup.find("span", class_="story-author")
        if not span:
            return None

        for a in span.find_all("a"):
            href = a.get("href", "")
            text = a.get_text(strip=True)
            match = re.search(r"/team/([A-Za-z0-9]+)", href)
            if match:
                a.replace_with(f"<@{match.group(1)}>")
            else:
                a.replace_with(text)

        text = span.get_text().strip()
        if text.startswith("By "):
            text = text[3:].strip()
        if not text:
            return None

        parts = re.split(r',\s*|\s*&\s*', text)
        authors = [p.strip() for p in parts if p.strip()]
        if not authors:
            return None
        if len(authors) == 1:
            return authors[0]
        return ", ".join(authors[:-1]) + " & " + authors[-1]
    except Exception as e:
        logging.error(f"Failed to get authors from {link}: {e}")
        return None


def build_blocks(entry, raw_entry):
    title = entry.title.content
    description = entry.description.content
    link = entry.links[0].content
    
    try:
        pubdate = int(parsedate_to_datetime(entry.pub_date.content).timestamp())
    except:
        pubdate = 0

    mc = raw_entry.get("media:content", {}) or {}
    mt = raw_entry.get("media:title", {}) or {}

    ogSrc = mc.get("@url", None) if isinstance(mc, dict) else None
    alt_text = (
        mt.get("#text", f"'{title}' social preview")
        if isinstance(mt, dict)
        else f"'{title}' social preview"
    )

    # Cut title to 150 minus the size taken by the mrkdwn link
    title_mrkdwn = smart_cut(title, 150-len(f"<{link}|>"))
    description = smart_cut(description, 200)

    authors = get_authors(link) or "unknown"

    card = {
        "type": "card",
        "title": {
            "type": "mrkdwn",
            "text": f"<{link}|{title_mrkdwn}>"
        },
    }

    card["subtitle"] = {
        "type": "mrkdwn",
        "text": f"by {authors}"
    }
    card["hero_image"] = {
        "type": "image",
        "image_url": ogSrc or "https://cdn.hackclub.com/019dbae9-5242-745b-acd2-3476ab3c52a3/og-default.png",
        "alt_text": alt_text
    }
    card["body"] = {
        "type": "plain_text",
        "text": description
    }

    if pubdate != 0:
        card["subtext"] = {
            "type": "mrkdwn",
            "text": "Published <!date^"+ str(pubdate) +"^{date_pretty}|???>"
        }

    return title, description, [card]


def send_message(channel, entry, raw_entry):
    title, description, blocks = build_blocks(entry, raw_entry)
    return app.client.chat_postMessage(
        channel=channel,
        text=f"{title}\n> {description}",
        blocks=blocks,
        unfurl_links=False,
        unfurl_media=False
    )


def check_feed():
    try:
        r = requests.get(RSS_FEED)
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
