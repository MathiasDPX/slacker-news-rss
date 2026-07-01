#!/bin/sh
set -e

INTERVAL="${INTERVAL_SECONDS:-1800}"

while true; do
    echo "Running main.py..."
    python main.py || echo "main.py exited with an error"
    echo "Sleeping for ${INTERVAL}s..."
    sleep "${INTERVAL}"
done
