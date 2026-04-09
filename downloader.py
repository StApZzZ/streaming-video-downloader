from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yt_dlp

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib


DEFAULT_CONFIG_NAME = "settings.toml"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    default_config = Path(__file__).resolve().with_name(DEFAULT_CONFIG_NAME)
    parser = argparse.ArgumentParser(
        description="Универсальный загрузчик видео из потока через yt-dlp.",
    )
    parser.add_argument(
        "-c",
        "--config",
        default=str(default_config),
        help="Путь до TOML-конфига. По умолчанию используется settings.toml рядом со скриптом.",
    )
    return parser.parse_args(argv)


def load_settings(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        raise FileNotFoundError(f"Файл настроек не найден: {config_path}")

    with config_path.open("rb") as file:
        data = tomllib.load(file)

    if not isinstance(data, dict):
        raise TypeError("Корень settings.toml должен быть TOML-таблицей.")

    return data


def get_table(settings: dict[str, Any], name: str) -> dict[str, Any]:
    value = settings.get(name, {})
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise TypeError(f"Секция [{name}] должна быть таблицей.")
    return value


def get_str(section: dict[str, Any], key: str, default: str = "") -> str:
    value = section.get(key, default)
    if value is None:
        return default
    return str(value).strip()


def get_int(section: dict[str, Any], key: str, default: int) -> int:
    value = section.get(key, default)
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise TypeError(f"Параметр '{key}' должен быть числом.") from error


def get_bool(section: dict[str, Any], key: str, default: bool) -> bool:
    value = section.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    raise TypeError(f"Параметр '{key}' должен быть boolean-значением.")


def resolve_path(base_dir: Path, raw_path: str) -> Path:
    candidate = Path(raw_path).expanduser()
    if candidate.is_absolute():
        return candidate
    return (base_dir / candidate).resolve()


def read_urls_from_file(urls_file: Path) -> list[str]:
    if not urls_file.exists():
        raise FileNotFoundError(f"Файл со ссылками не найден: {urls_file}")

    urls: list[str] = []
    for line in urls_file.read_text(encoding="utf-8").splitlines():
        prepared = line.strip()
        if not prepared or prepared.startswith("#"):
            continue
        urls.append(prepared)
    return urls


def deduplicate(items: list[str]) -> list[str]:
    seen: set[str] = set()
    unique_items: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        unique_items.append(item)
    return unique_items


def collect_urls(settings: dict[str, Any], config_dir: Path) -> list[str]:
    targets = get_table(settings, "targets")

    urls: list[str] = []
    inline_urls = targets.get("urls", [])
    if inline_urls:
        if not isinstance(inline_urls, list):
            raise TypeError("Параметр 'targets.urls' должен быть списком.")
        for item in inline_urls:
            prepared = str(item).strip()
            if prepared:
                urls.append(prepared)

    urls_file = get_str(targets, "urls_file")
    if urls_file:
        urls.extend(read_urls_from_file(resolve_path(config_dir, urls_file)))

    return deduplicate(urls)


def build_headers(http_settings: dict[str, Any]) -> dict[str, str]:
    headers: dict[str, str] = {}

    cookie = get_str(http_settings, "cookie")
    user_agent = get_str(http_settings, "user_agent")
    referer = get_str(http_settings, "referer")

    if cookie:
        headers["Cookie"] = cookie
    if user_agent:
        headers["User-Agent"] = user_agent
    if referer:
        headers["Referer"] = referer

    extra_headers = http_settings.get("headers", {})
    if extra_headers:
        if not isinstance(extra_headers, dict):
            raise TypeError("Секция [http.headers] должна быть таблицей.")
        for key, value in extra_headers.items():
            prepared_key = str(key).strip()
            prepared_value = str(value).strip()
            if prepared_key and prepared_value:
                headers[prepared_key] = prepared_value

    return headers


def build_ydl_options(
    settings: dict[str, Any],
    config_dir: Path,
) -> tuple[dict[str, Any], Path, bool]:
    general = get_table(settings, "general")
    download = get_table(settings, "download")
    http_settings = get_table(settings, "http")

    output_dir = resolve_path(config_dir, get_str(general, "output_dir", "downloads"))
    output_dir.mkdir(parents=True, exist_ok=True)

    filename_template = get_str(
        download,
        "filename_template",
        "%(title)s [%(id)s].%(ext)s",
    )
    archive_file = get_str(general, "archive_file", "downloaded.txt")
    fragment_retry_sleep_sec = get_int(download, "fragment_retry_sleep_sec", 5)

    ydl_opts: dict[str, Any] = {
        "format": get_str(download, "format", "bestvideo*+bestaudio/best"),
        "merge_output_format": get_str(download, "merge_output_format", "mp4"),
        "outtmpl": str(output_dir / filename_template),
        "retries": get_int(download, "retries", 30),
        "fragment_retries": get_int(download, "fragment_retries", 30),
        "extractor_retries": get_int(download, "extractor_retries", 3),
        "socket_timeout": get_int(download, "socket_timeout_sec", 30),
        "concurrent_fragment_downloads": get_int(
            download,
            "concurrent_fragment_downloads",
            1,
        ),
        "noplaylist": get_bool(download, "noplaylist", True),
        "quiet": get_bool(download, "quiet", False),
        "http_headers": build_headers(http_settings),
        "retry_sleep_functions": {
            "fragment": lambda _attempt: fragment_retry_sleep_sec,
        },
    }

    if archive_file:
        ydl_opts["download_archive"] = str(resolve_path(config_dir, archive_file))

    cookie_file = get_str(http_settings, "cookie_file")
    if cookie_file:
        ydl_opts["cookiefile"] = str(resolve_path(config_dir, cookie_file))

    if get_bool(download, "write_thumbnail", False):
        ydl_opts["writethumbnail"] = True

    if get_bool(download, "write_info_json", False):
        ydl_opts["writeinfojson"] = True

    return ydl_opts, output_dir, get_bool(general, "continue_on_error", True)


def download_urls(urls: list[str], ydl_opts: dict[str, Any], continue_on_error: bool) -> int:
    success_count = 0
    failed_urls: list[tuple[str, str]] = []

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        for index, url in enumerate(urls, start=1):
            print(f"\n[{index}/{len(urls)}] Скачивание: {url}")
            try:
                exit_code = ydl.download([url])
                if exit_code not in (0, None):
                    raise RuntimeError(f"yt-dlp завершился с кодом {exit_code}")
                success_count += 1
            except Exception as error:  # noqa: BLE001
                failed_urls.append((url, str(error)))
                print(f"[Ошибка] {error}")
                if not continue_on_error:
                    break

    print("\n--- Итог ---")
    print(f"Успешно: {success_count}")
    print(f"С ошибкой: {len(failed_urls)}")

    if failed_urls:
        print("Проблемные ссылки:")
        for url, reason in failed_urls:
            print(f"- {url}")
            print(f"  причина: {reason}")

    return 0 if not failed_urls else 1


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config_path = Path(args.config).expanduser().resolve()

    try:
        settings = load_settings(config_path)
        urls = collect_urls(settings, config_path.parent)
        if not urls:
            raise ValueError("Список ссылок пуст. Заполните [targets].urls или targets.urls_file.")

        ydl_opts, output_dir, continue_on_error = build_ydl_options(
            settings,
            config_path.parent,
        )

        print(f"[Настройки] Конфиг: {config_path}")
        print(f"[Настройки] Папка выгрузки: {output_dir}")
        print(f"[Настройки] Ссылок в очереди: {len(urls)}")

        return download_urls(urls, ydl_opts, continue_on_error)
    except Exception as error:  # noqa: BLE001
        print(f"[Ошибка] {error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
