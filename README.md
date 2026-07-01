# Slacker News RSS

Small program to send webhooks to [#slacker-news](https://hackclub.enterprise.slack.com/archives/C0ALDCF90K1) when a new post comes out

## How it work

<!-- fancy ass diagram that took too long for what it's worth -->
```mermaid
flowchart TB
    n1["Wake up"] --> n2["Check for new posts"]
    n2 -- Nothing happened --> n3["Wait 30 minutes"]
    n3 --> n1
    n2 --> n4["Post article to Slack<br>Add to database.json"]
    n4 --> n3

    n1@{ shape: rect}
    n3@{ shape: rect}
    n4@{ shape: rect}
```

## Installation

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
SLACK_WEBHOOK="https://hooks.slack.com/services/_________/___________/________________________"
```
