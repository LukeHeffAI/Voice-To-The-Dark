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
    apt-get install -y --no-install-recommends ffmpeg curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt requirements-new.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-new.txt

COPY . .
COPY --from=frontend /app/frontend/dist /app/frontend/dist

RUN mkdir -p /app/data/db /app/data/stories /app/data/sfx_cache \
    /app/data/voice_previews /app/data/segment_cache /app/data/reddit_cache /app/tmp

RUN chmod +x /app/docker-entrypoint.sh

ENV DJANGO_ENV=production
ENV DJANGO_SETTINGS_MODULE=config.settings

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/ || exit 1

CMD ["/app/docker-entrypoint.sh"]
