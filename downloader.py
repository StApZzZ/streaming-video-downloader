import argparse
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

import yt_dlp

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib


DEFAULT_CONFIG_NAME = "settings.toml"
EXAMPLE_CONFIG_NAME = "settings.example.toml"
MIN_PYTHON_VERSION = (3, 10)
DEFAULT_SETTINGS: dict[str, Any] = {
    "general": {
        "output_dir": "downloads",
        "continue_on_error": True,
        "archive_file": "downloaded.txt",
    },
    "download": {
        "format": "bestvideo*+bestaudio/best",
        "merge_output_format": "mp4",
        "filename_template": "%(title)s [%(id)s].%(ext)s",
        "retries": 30,
        "fragment_retries": 30,
        "extractor_retries": 3,
        "fragment_retry_sleep_sec": 5,
        "socket_timeout_sec": 30,
        "concurrent_fragment_downloads": 1,
        "noplaylist": True,
        "quiet": False,
        "write_thumbnail": False,
        "write_info_json": False,
    },
    "http": {
        "cookie": "",
        "cookie_file": "",
        "user_agent": "",
        "referer": "",
        "headers": {},
    },
    "targets": {
        "urls": [],
        "urls_file": "",
    },
}
TOML_BARE_KEY_RE = re.compile(r"^[A-Za-z0-9_-]+$")
LogCallback = Callable[[str], None]


class YDLLogProxy:
    def __init__(self, log: LogCallback) -> None:
        self.log = log

    def debug(self, message: str) -> None:
        self.log(str(message))

    def info(self, message: str) -> None:
        self.log(str(message))

    def warning(self, message: str) -> None:
        self.log(f"WARNING: {message}")

    def error(self, message: str) -> None:
        self.log(f"ERROR: {message}")


def ensure_supported_python() -> None:
    if sys.version_info >= MIN_PYTHON_VERSION:
        return

    required = ".".join(str(part) for part in MIN_PYTHON_VERSION)
    current = ".".join(str(part) for part in sys.version_info[:3])
    raise RuntimeError(
        f"Требуется Python {required}+; сейчас используется Python {current}.",
    )


def get_app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def get_default_config_path() -> Path:
    return get_app_dir() / DEFAULT_CONFIG_NAME


def get_example_config_path() -> Path:
    return get_app_dir() / EXAMPLE_CONFIG_NAME


def make_default_settings() -> dict[str, Any]:
    return deepcopy(DEFAULT_SETTINGS)


def merge_nested_dicts(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        current = merged.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            merged[key] = merge_nested_dicts(current, value)
        else:
            merged[key] = deepcopy(value)
    return merged


def get_settings_with_defaults(settings: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(settings, dict):
        raise TypeError("Корень settings.toml должен быть TOML-таблицей.")
    return merge_nested_dicts(make_default_settings(), settings)


def format_toml_key(key: Any) -> str:
    key_text = str(key)
    if TOML_BARE_KEY_RE.fullmatch(key_text):
        return key_text
    return format_toml_string(key_text)


def format_toml_string(value: str) -> str:
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\b", "\\b")
        .replace("\t", "\\t")
        .replace("\n", "\\n")
        .replace("\f", "\\f")
        .replace("\r", "\\r")
    )
    return f'"{escaped}"'


def format_toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if value != value or value in {float("inf"), float("-inf")}:
            raise TypeError("TOML не поддерживает NaN и Infinity.")
        return str(value)
    if isinstance(value, Path):
        return format_toml_string(str(value))
    if isinstance(value, str):
        return format_toml_string(value)
    if isinstance(value, list):
        return f"[{', '.join(format_toml_value(item) for item in value)}]"
    raise TypeError(f"Неподдерживаемый тип для TOML: {type(value)!r}")


def serialize_toml_table(
    lines: list[str],
    table: dict[str, Any],
    path: tuple[str, ...] = (),
) -> None:
    if path:
        if lines:
            lines.append("")
        section = ".".join(format_toml_key(part) for part in path)
        lines.append(f"[{section}]")

    plain_items: list[tuple[str, Any]] = []
    nested_tables: list[tuple[str, dict[str, Any]]] = []

    for key, value in table.items():
        if isinstance(value, dict):
            nested_tables.append((str(key), value))
        else:
            plain_items.append((str(key), value))

    for key, value in plain_items:
        lines.append(f"{format_toml_key(key)} = {format_toml_value(value)}")

    for key, value in nested_tables:
        serialize_toml_table(lines, value, (*path, key))


def serialize_settings(settings: dict[str, Any]) -> str:
    normalized = get_settings_with_defaults(settings)
    lines: list[str] = []
    serialize_toml_table(lines, normalized)
    return "\n".join(lines).rstrip() + "\n"


def save_settings(config_path: Path, settings: dict[str, Any]) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(serialize_settings(settings), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Универсальный загрузчик видео из потока через yt-dlp.",
    )
    parser.add_argument(
        "-c",
        "--config",
        default=str(get_default_config_path()),
        help=(
            "Путь до TOML-конфига. По умолчанию используется settings.toml рядом со "
            "скриптом или exe. Если файла нет, создайте его из settings.example.toml."
        ),
    )
    return parser.parse_args(argv)


def load_settings(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        message = f"Файл настроек не найден: {config_path}"
        sibling_example = config_path.with_name(EXAMPLE_CONFIG_NAME)
        default_example = get_example_config_path()

        if sibling_example.exists():
            message += f". Создайте {config_path.name} на основе {sibling_example.name}."
        elif default_example.exists():
            message += f". Создайте {config_path.name} на основе {default_example.name}."

        raise FileNotFoundError(message)

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


def emit_log(message: str, log: LogCallback | None = None) -> None:
    if log is None:
        print(message)
        return
    log(message)


def download_urls(
    urls: list[str],
    ydl_opts: dict[str, Any],
    continue_on_error: bool,
    log: LogCallback | None = None,
) -> int:
    success_count = 0
    failed_urls: list[tuple[str, str]] = []
    effective_opts = dict(ydl_opts)

    if log is not None:
        effective_opts["logger"] = YDLLogProxy(log)

    with yt_dlp.YoutubeDL(effective_opts) as ydl:
        for index, url in enumerate(urls, start=1):
            emit_log("", log)
            emit_log(f"[{index}/{len(urls)}] Скачивание: {url}", log)
            try:
                exit_code = ydl.download([url])
                if exit_code not in (0, None):
                    raise RuntimeError(f"yt-dlp завершился с кодом {exit_code}")
                success_count += 1
            except Exception as error:  # noqa: BLE001
                failed_urls.append((url, str(error)))
                emit_log(f"[Ошибка] {error}", log)
                if not continue_on_error:
                    break

    emit_log("", log)
    emit_log("--- Итог ---", log)
    emit_log(f"Успешно: {success_count}", log)
    emit_log(f"С ошибкой: {len(failed_urls)}", log)

    if failed_urls:
        emit_log("Проблемные ссылки:", log)
        for url, reason in failed_urls:
            emit_log(f"- {url}", log)
            emit_log(f"  причина: {reason}", log)

    return 0 if not failed_urls else 1


def run_download(
    settings: dict[str, Any],
    config_dir: Path,
    log: LogCallback | None = None,
) -> int:
    urls = collect_urls(settings, config_dir)
    if not urls:
        raise ValueError("Список ссылок пуст. Заполните [targets].urls или targets.urls_file.")

    ydl_opts, output_dir, continue_on_error = build_ydl_options(settings, config_dir)

    emit_log(f"[Настройки] Папка выгрузки: {output_dir}", log)
    emit_log(f"[Настройки] Ссылок в очереди: {len(urls)}", log)

    return download_urls(urls, ydl_opts, continue_on_error, log=log)


def run_from_config(config_path: Path, log: LogCallback | None = None) -> int:
    settings = load_settings(config_path)
    emit_log(f"[Настройки] Конфиг: {config_path}", log)
    return run_download(settings, config_path.parent, log=log)


def main(argv: list[str] | None = None) -> int:
    ensure_supported_python()
    args = parse_args(argv)
    config_path = Path(args.config).expanduser().resolve()

    try:
        return run_from_config(config_path)
    except Exception as error:  # noqa: BLE001
        print(f"[Ошибка] {error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
