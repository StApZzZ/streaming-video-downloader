# Telegram-бот (bot.py) поверх downloader.py. ffmpeg нужен yt-dlp для склейки видео и аудио,
# deno (из extra yt-dlp[deno]) — для YouTube.
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1
RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg ca-certificates \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements-bot.txt ./
RUN pip install -r requirements-bot.txt
COPY downloader.py bot.py ./
RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin bot
USER 10001
ENV HOME=/tmp DOWNLOAD_DIR=/tmp/downloads
CMD ["python", "bot.py"]
