# Stage 1: Build Vue frontend
FROM node:20-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# Stage 2: Python app with Django
FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements-new.txt ./
RUN pip install --no-cache-dir -r requirements-new.txt

COPY . .
COPY --from=frontend /app/frontend/dist /app/frontend/dist

RUN mkdir -p /app/data/db /app/data/stories /app/data/sfx_cache \
    /app/data/voice_previews /app/data/segment_cache /app/data/reddit_cache /app/data/tmp

RUN chmod +x /app/docker-entrypoint.sh

EXPOSE 8000

ENV DJANGO_ENV=production
ENV DJANGO_SETTINGS_MODULE=config.settings

ENTRYPOINT ["/app/docker-entrypoint.sh"]
