from dotenv import load_dotenv
from os import getenv, path
import feedparser
import requests
import logging
import json

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


def send_message(entry):
    title = entry.title
    description = entry.description
    ogSrc = entry.get("media_thumbnail", [{}])[0].get(
        "url",
        "https://cdn.hackclub.com/019dbae9-5242-745b-acd2-3476ab3c52a3/og-default.png",
    )

    data = {
        "text": f"{title}\n> {description}",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"<{entry.link}|{title}>\n{description}",
                },
            },
            {
                "type": "image",
                "image_url": ogSrc,
                "alt_text": f"'{title}' social preview",
            },
        ],
    }

    r = requests.post(SLACK_WEBHOOK, json=data)

    return r


def main():
    feed = feedparser.parse(RSS_FEED, resolve_relative_uris=True)

    if feed.status != 200:
        logging.error(f"RSS feed returned an invalid status code ({feed.status})")
        return

    for entry in feed.entries:
        guid = entry.guid

        if guid not in database:
            resp = send_message(entry)

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
