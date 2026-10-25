FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/pyproject.toml ./
COPY backend/sahifa ./sahifa
RUN pip install --no-cache-dir .

RUN useradd --create-home sahifa && mkdir -p /app/data && chown sahifa /app/data
USER sahifa

ENV SAHIFA_API_HOST=0.0.0.0 \
    SAHIFA_DATABASE_URL=sqlite+aiosqlite:////app/data/sahifa.db \
    SAHIFA_MEDIA_DIR=/app/data/media

EXPOSE 8000
CMD ["python", "-m", "sahifa.main"]
