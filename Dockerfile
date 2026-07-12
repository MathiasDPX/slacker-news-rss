FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py .

ENV DATABASE_PATH=/data/database.json
VOLUME ["/data"]

CMD ["python", "main.py"]
