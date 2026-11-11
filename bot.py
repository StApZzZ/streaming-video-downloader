"""Telegram-бот: присылаешь ссылку на видео — получаешь файл.

Скачивание идёт через те же функции, что и CLI/GUI (downloader.py).

Переменные окружения:
  BOT_TOKEN          токен от @BotFather (обязательно)
  ALLOWED_USER_IDS   Telegram id через запятую, кому можно пользоваться ботом.
                     Пусто — доступа нет ни у кого (бот ответит id, который нужно добавить).
  BOT_SETTINGS       необязательный путь до settings.toml (cookie, заголовки, ретраи);
                     папка выгрузки и archive_file из него игнорируются.
  YTDLP_FORMAT       формат yt-dlp (по умолчанию до 720p, чтобы влезть в лимит Telegram)
  MAX_FILE_MB        предел размера файла, по умолчанию 50 (лимит Bot API на отправку)
  MAX_PARALLEL       сколько ссылок качать одновременно, по умолчанию 2
  DOWNLOAD_DIR       где держать временные файлы, по умолчанию системный tmp
"""

import asyncio
import logging
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import FSInputFile, Message

from downloader import (
    build_ydl_options,
    download_url_files,
    get_settings_with_defaults,
    load_settings,
)

URL_RE = re.compile(r"https?://[^\s<>\"']+")
VIDEO_SUFFIXES = {".mp4", ".m4v", ".mov"}
MAX_URLS_PER_MESSAGE = 5
DEFAULT_FORMAT = "bv*[height<=720]+ba/b[height<=720]/bv*+ba/b"

log = logging.getLogger("dw-bot")


def env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    return int(raw) if raw else default


def parse_ids(raw: str) -> set[int]:
    return {int(part) for part in re.split(r"[,\s]+", raw.strip()) if part}


BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
ALLOWED_USER_IDS = parse_ids(os.environ.get("ALLOWED_USER_IDS", ""))
SETTINGS_PATH = os.environ.get("BOT_SETTINGS", "").strip()
YTDLP_FORMAT = os.environ.get("YTDLP_FORMAT", "").strip() or DEFAULT_FORMAT
MAX_FILE_BYTES = env_int("MAX_FILE_MB", 50) * 1024 * 1024
DOWNLOAD_DIR = Path(os.environ.get("DOWNLOAD_DIR", "").strip() or tempfile.gettempdir())

semaphore = asyncio.Semaphore(env_int("MAX_PARALLEL", 2))
dp = Dispatcher()


def make_ydl_options(workdir: Path) -> dict[str, Any]:
    if SETTINGS_PATH:
        config_path = Path(SETTINGS_PATH).expanduser().resolve()
        base, config_dir = load_settings(config_path), config_path.parent
    else:
        base, config_dir = {}, workdir

    settings = get_settings_with_defaults(base)
    settings["general"]["output_dir"] = str(workdir)
    settings["general"]["archive_file"] = ""      # бот может отдавать одно видео много раз
    settings["download"]["format"] = YTDLP_FORMAT
    settings["download"]["noplaylist"] = True

    ydl_opts, _, _ = build_ydl_options(settings, config_dir)
    ydl_opts.update(
        noprogress=True,
        no_color=True,
        max_filesize=MAX_FILE_BYTES,
        restrictfilenames=True,
    )
    return ydl_opts


def download(url: str, workdir: Path) -> list[Path]:
    return download_url_files(url, make_ydl_options(workdir), log=log.info)


def short_error(error: Exception) -> str:
    text = re.sub(r"\x1b\[[0-9;]*m", "", str(error)).strip() or type(error).__name__
    return text if len(text) <= 500 else text[:500] + "…"


def is_allowed(message: Message) -> bool:
    return message.from_user is not None and message.from_user.id in ALLOWED_USER_IDS


async def deny(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else "?"
    log.warning("access denied for user %s", user_id)
    await message.answer(f"Нет доступа. Ваш Telegram id: {user_id}")


async def send_file(message: Message, path: Path) -> None:
    media = FSInputFile(path)
    if path.suffix.lower() in VIDEO_SUFFIXES:
        await message.answer_video(media, supports_streaming=True, request_timeout=600)
    else:
        await message.answer_document(media, request_timeout=600)


async def process_url(message: Message, url: str) -> None:
    status = await message.reply("В очереди…", disable_web_page_preview=True)
    async with semaphore:
        await status.edit_text("Скачиваю…")
        workdir = Path(tempfile.mkdtemp(prefix="dw-", dir=DOWNLOAD_DIR))
        try:
            files = await asyncio.to_thread(download, url, workdir)
            if not files:
                limit_mb = MAX_FILE_BYTES // (1024 * 1024)
                await status.edit_text(
                    f"Файл не скачан: возможно, он больше {limit_mb} МБ "
                    "или по ссылке нет видео.",
                )
                return

            too_big = [p for p in files if p.stat().st_size > MAX_FILE_BYTES]
            if too_big:
                size_mb = max(p.stat().st_size for p in too_big) / (1024 * 1024)
                await status.edit_text(
                    f"Видео весит {size_mb:.0f} МБ — Telegram не даст боту отправить больше "
                    f"{MAX_FILE_BYTES // (1024 * 1024)} МБ.",
                )
                return

            await status.edit_text("Отправляю…")
            for path in files:
                await send_file(message, path)
            await status.delete()
        except Exception as error:  # noqa: BLE001
            log.exception("download failed: %s", url)
            await status.edit_text(f"Ошибка: {short_error(error)}", disable_web_page_preview=True)
        finally:
            shutil.rmtree(workdir, ignore_errors=True)


@dp.message(CommandStart())
@dp.message(Command("help"))
async def on_start(message: Message) -> None:
    if not is_allowed(message):
        await deny(message)
        return
    await message.answer(
        "Пришлите ссылку на страницу с видео — я скачаю его через yt-dlp и отправлю сюда.\n"
        f"Можно до {MAX_URLS_PER_MESSAGE} ссылок в одном сообщении. "
        f"Лимит размера — {MAX_FILE_BYTES // (1024 * 1024)} МБ.",
    )


@dp.message(F.text)
async def on_text(message: Message) -> None:
    if not is_allowed(message):
        await deny(message)
        return

    urls = list(dict.fromkeys(URL_RE.findall(message.text or "")))
    if not urls:
        await message.answer("Не вижу ссылки. Пришлите URL, начинающийся с http:// или https://.")
        return

    if len(urls) > MAX_URLS_PER_MESSAGE:
        await message.answer(f"Беру первые {MAX_URLS_PER_MESSAGE} ссылок.")
    await asyncio.gather(*(process_url(message, url) for url in urls[:MAX_URLS_PER_MESSAGE]))


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN не задан")
    if not ALLOWED_USER_IDS:
        log.warning("ALLOWED_USER_IDS пуст: бот никому не будет отвечать по делу")

    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    bot = Bot(BOT_TOKEN)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
