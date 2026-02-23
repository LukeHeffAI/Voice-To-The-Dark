FROM python:3.11-slim

# ffmpeg is required by pydub for audio mixing
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create data directories inside the container (volume-mounted at runtime)
RUN mkdir -p /app/data/db /app/data/stories /app/data/sfx_cache /app/tmp

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
