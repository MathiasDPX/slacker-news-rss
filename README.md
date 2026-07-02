# Slacker News RSS

Small program to send to Slack channels when a new [HackClub News](https://news.hackclub.com) post comes out

## How it work

<!-- fancy ass diagram that took too long for what it's worth -->
```mermaid
flowchart TB
    n1["Wake up"] --> n2["Check for new posts"]
    n2 -- Nothing happened --> n3["Wait 30 minutes"]
    n3 --> n1
    n4["Post article to Slack<br>Add to database.json"] --> n3
    n2 --> n5@{ label: "List channels it's in" }
    n5 --> n4

    n1@{ shape: rect}
    n3@{ shape: rect}
    n4@{ shape: rect}
    n5@{ shape: rect}
```

## Installation

After installing the Docker compose and environment variable, make sure the bot isn't in any channels to don't bomb your channels with 10**67 messages (as the database is empty)

### docker-compose.yml

```yaml
services:
  slacker-news-rss:
    build: .
    restart: unless-stopped
    container_name: slacker-news-rss
    env_file:
      - .env
    environment:
      DATABASE_PATH: /data/database.json
      INTERVAL_SECONDS: 1800
    volumes:
      - ./data:/data
```

### Environment variable

```toml
RSS_FEED="https://news.hackclub.com/feed.xml"
SLACK_BOT_TOKEN="xoxb-_____"
SLACK_APP_TOKEN="xapp-_____"
```
