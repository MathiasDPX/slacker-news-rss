from dotenv import load_dotenv
from os import getenv
import feedparser
import requests
import json

load_dotenv()

RSS_FEED = getenv("RSS_FEED")
SLACK_WEBHOOK = getenv("SLACK_WEBHOOK")

database = json.load(open("database.json", "r", encoding="utf-8"))

if RSS_FEED == None:
    print("Missing RSS_FEED environment variable")
if SLACK_WEBHOOK == None:
    print("Missing SLACK_WEBHOOK environment variable")

if RSS_FEED == None or SLACK_WEBHOOK == None:
    exit()


def send_message(entry):
    data = {
        "text": f"{entry.title}\n> {entry.description}",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"<{entry.link}|{entry.title}>\n{entry.description}",
                },
            }
        ],
    }

    r = requests.post(SLACK_WEBHOOK, json=data)

    return r


def main():
    feed = feedparser.parse(RSS_FEED)

    if feed.status != 200:
        print(f"RSS feed returned an invalid status code ({feed.status})")
        return

    for entry in feed.entries:
        guid = entry.guid

        if guid not in database:
            resp = send_message(entry)

            if resp.status_code != 200:
                print("Failed to send notification")
                print(resp.status_code)
                print(resp.content)
                print(resp.headers)

            print(f"New article -> {entry.title}")
            database.append(guid)

    with open("database.json", "w+", encoding="utf-8") as f:
        json.dump(database, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
