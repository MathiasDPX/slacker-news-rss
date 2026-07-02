from rss_parser import RSSParser
from dotenv import load_dotenv
from os import getenv, path
import requests
import logging
import json
import xmltodict

load_dotenv()
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


RSS_FEED = getenv("RSS_FEED")
SLACK_WEBHOOK = getenv("SLACK_WEBHOOK")
DATABASE_PATH = getenv("DATABASE_PATH", "database.json")

if not path.exists(DATABASE_PATH):
    with open(DATABASE_PATH, "w+", encoding="utf-8") as f:
        json.dump([], f)

database = json.load(open(DATABASE_PATH, "r", encoding="utf-8"))

if RSS_FEED == None:
    logging.error("Missing RSS_FEED environment variable")
if SLACK_WEBHOOK == None:
    logging.error("Missing SLACK_WEBHOOK environment variable")

if RSS_FEED == None or SLACK_WEBHOOK == None:
    exit()


def send_message(entry, raw_entry):
    title = entry.title.content
    description = entry.description.content
    link = entry.links[0].content

    mc = raw_entry.get("media:content", {}) or {}
    mt = raw_entry.get("media:title", {}) or {}

    ogSrc = mc.get("@url", "") if isinstance(mc, dict) else ""
    alt_text = (
        mt.get("#text", f"'{title}' social preview")
        if isinstance(mt, dict)
        else f"'{title}' social preview"
    )

    data = {
        "text": f"{title}\n> {description}",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"<{link}|{title}>\n{description}",
                },
            },
            {
                "type": "image",
                "image_url": ogSrc,
                "alt_text": alt_text,
                "title": {"type": "plain_text", "text": alt_text, "emoji": True},
            },
        ],
    }

    r = requests.post(SLACK_WEBHOOK, json=data)

    return r


def main():
    try:
        r = requests.get(RSS_FEED)
        r.raise_for_status()
        data = r.content.decode("utf-8")
    except:
        logging.error(f"Failed to fetch RSS feed (status code {r.status_code})")
        return

    feed = RSSParser().parse(data)
    raw = xmltodict.parse(data)
    raw_items = raw.get("rss", {}).get("channel", {}).get("item", [])
    if not isinstance(raw_items, list):
        raw_items = [raw_items]

    for i, entry in enumerate(feed.channel.items):
        guid = entry.guid.content

        if guid not in database:
            raw_entry = raw_items[i] if i < len(raw_items) else {}
            resp = send_message(entry, raw_entry)

            if resp.status_code != 200:
                logging.error(f"Failed to send notification ({resp.status_code})")
                logging.info(resp.content)
            else:
                logging.info(f"New article -> {entry.title}")
                database.append(guid)

    with open(DATABASE_PATH, "w+", encoding="utf-8") as f:
        json.dump(database, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
