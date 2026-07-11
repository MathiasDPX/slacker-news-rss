import re
import logging
import requests
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse, urljoin

from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "slacker-news-bot"
}


def smart_cut(text, limit):
    if len(text) > limit:
        cut = text[:limit - 3]
        if " " in cut:
            cut = cut.rsplit(" ", 1)[0]
        text = cut + "..."

    return text


def get_authors(link):
    try:
        r = requests.get(link, headers=HEADERS)
        soup = BeautifulSoup(r.text, "html.parser")

        # Follow meta-refresh redirects
        meta = soup.find("meta", attrs={"http-equiv": "refresh"})
        if meta:
            content = meta.get("content", "")
            match = re.search(r"url=(.+)", content, re.IGNORECASE)
            if match:
                target = match.group(1).strip()
                if target.startswith("/"):
                    target = urljoin(r.url, target)
                r = requests.get(target, headers=HEADERS)
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


def add_parameter(url, params):
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    query.update(params)
    return urlunparse(parsed._replace(query=urlencode(query, doseq=True)))


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
    link = add_parameter(link, {"ref": "slack-bot"})

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
