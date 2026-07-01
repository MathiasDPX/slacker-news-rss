FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

ENV DATABASE_PATH=/data/database.json
VOLUME ["/data"]

ENTRYPOINT ["./entrypoint.sh"]
