import queue
import threading
from copy import deepcopy
from pathlib import Path
from typing import Any

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from downloader import (
    ensure_supported_python,
    get_app_dir,
    get_bool,
    get_default_config_path,
    get_example_config_path,
    get_int,
    get_str,
    get_table,
    load_settings,
    make_default_settings,
    run_download,
    save_settings,
)


KNOWN_SECTION_FIELDS: dict[str, set[str]] = {
    "general": {"output_dir", "continue_on_error", "archive_file"},
    "download": {
        "format",
        "merge_output_format",
        "filename_template",
        "retries",
        "fragment_retries",
        "extractor_retries",
        "fragment_retry_sleep_sec",
        "socket_timeout_sec",
        "concurrent_fragment_downloads",
        "noplaylist",
        "quiet",
        "write_thumbnail",
        "write_info_json",
    },
    "http": {"cookie", "cookie_file", "user_agent", "referer", "headers"},
    "targets": {"urls", "urls_file"},
}


class DownloaderGUI(tk.Tk):
    def __init__(self) -> None:
        super().__init__()

        self.title("Universal Stream Video Downloader GUI")
        self.geometry("1120x860")
        self.minsize(980, 720)

        self.default_settings = make_default_settings()
        self.extra_settings: dict[str, Any] = {}
        self.event_queue: queue.Queue[tuple[str, Any]] = queue.Queue()
        self.download_thread: threading.Thread | None = None
        self.is_running = False
        self.is_closed = False
        self.config_buttons: list[ttk.Button] = []

        self.config_path_var = tk.StringVar(value=str(get_default_config_path()))
        self.output_dir_var = tk.StringVar()
        self.archive_file_var = tk.StringVar()
        self.continue_on_error_var = tk.BooleanVar()

        self.format_var = tk.StringVar()
        self.merge_output_format_var = tk.StringVar()
        self.filename_template_var = tk.StringVar()
        self.retries_var = tk.StringVar()
        self.fragment_retries_var = tk.StringVar()
        self.extractor_retries_var = tk.StringVar()
        self.fragment_retry_sleep_sec_var = tk.StringVar()
        self.socket_timeout_sec_var = tk.StringVar()
        self.concurrent_fragment_downloads_var = tk.StringVar()
        self.noplaylist_var = tk.BooleanVar()
        self.quiet_var = tk.BooleanVar()
        self.write_thumbnail_var = tk.BooleanVar()
        self.write_info_json_var = tk.BooleanVar()

        self.cookie_file_var = tk.StringVar()
        self.user_agent_var = tk.StringVar()
        self.referer_var = tk.StringVar()
        self.urls_file_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Готово к работе.")

        self._build_layout()
        self._load_initial_settings()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._process_events)

    def _build_layout(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=3)
        self.rowconfigure(3, weight=2)

        self._build_config_bar()
        self._build_tabs()
        self._build_actions()
        self._build_log_panel()

    def _build_config_bar(self) -> None:
        frame = ttk.LabelFrame(self, text="Конфиг")
        frame.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 8))
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Файл настроек:").grid(
            row=0,
            column=0,
            sticky="w",
            padx=(12, 8),
            pady=10,
        )
        ttk.Entry(frame, textvariable=self.config_path_var).grid(
            row=0,
            column=1,
            sticky="ew",
            padx=(0, 8),
            pady=10,
        )

        self.choose_config_button = ttk.Button(
            frame,
            text="Выбрать...",
            command=self._choose_config_file,
        )
        self.choose_config_button.grid(row=0, column=2, padx=(0, 8), pady=10)
        self.config_buttons.append(self.choose_config_button)

        self.load_button = ttk.Button(frame, text="Загрузить", command=self._load_selected_config)
        self.load_button.grid(row=0, column=3, padx=(0, 8), pady=10)
        self.config_buttons.append(self.load_button)

        self.save_button = ttk.Button(frame, text="Сохранить", command=self._save_config)
        self.save_button.grid(row=0, column=4, padx=(0, 8), pady=10)
        self.config_buttons.append(self.save_button)

        self.save_as_button = ttk.Button(
            frame,
            text="Сохранить как",
            command=lambda: self._save_config(save_as=True),
        )
        self.save_as_button.grid(row=0, column=5, padx=(0, 8), pady=10)
        self.config_buttons.append(self.save_as_button)

        self.reset_button = ttk.Button(frame, text="По умолчанию", command=self._reset_to_defaults)
        self.reset_button.grid(row=0, column=6, padx=(0, 12), pady=10)
        self.config_buttons.append(self.reset_button)

    def _build_tabs(self) -> None:
        self.notebook = ttk.Notebook(self)
        self.notebook.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 8))

        self.general_tab = ttk.Frame(self.notebook, padding=12)
        self.download_tab = ttk.Frame(self.notebook, padding=12)
        self.http_tab = ttk.Frame(self.notebook, padding=12)
        self.targets_tab = ttk.Frame(self.notebook, padding=12)

        self.notebook.add(self.general_tab, text="Общие")
        self.notebook.add(self.download_tab, text="Скачивание")
        self.notebook.add(self.http_tab, text="HTTP")
        self.notebook.add(self.targets_tab, text="Ссылки")

        self._build_general_tab()
        self._build_download_tab()
        self._build_http_tab()
        self._build_targets_tab()

    def _build_general_tab(self) -> None:
        self.general_tab.columnconfigure(1, weight=1)

        self._add_entry_row(
            self.general_tab,
            0,
            "Папка выгрузки:",
            self.output_dir_var,
            self._choose_output_dir,
            "Папка...",
        )
        self._add_entry_row(
            self.general_tab,
            1,
            "Файл архива:",
            self.archive_file_var,
            self._choose_archive_file,
            "Файл...",
        )
        ttk.Checkbutton(
            self.general_tab,
            text="Продолжать очередь, если одна из ссылок завершилась ошибкой",
            variable=self.continue_on_error_var,
        ).grid(row=2, column=0, columnspan=3, sticky="w", pady=(8, 0))

    def _build_download_tab(self) -> None:
        self.download_tab.columnconfigure(1, weight=1)

        self._add_entry_row(self.download_tab, 0, "Формат yt-dlp:", self.format_var)
        self._add_entry_row(
            self.download_tab,
            1,
            "Формат после склейки:",
            self.merge_output_format_var,
        )
        self._add_entry_row(
            self.download_tab,
            2,
            "Шаблон имени файла:",
            self.filename_template_var,
        )
        self._add_entry_row(self.download_tab, 3, "retries:", self.retries_var)
        self._add_entry_row(
            self.download_tab,
            4,
            "fragment_retries:",
            self.fragment_retries_var,
        )
        self._add_entry_row(
            self.download_tab,
            5,
            "extractor_retries:",
            self.extractor_retries_var,
        )
        self._add_entry_row(
            self.download_tab,
            6,
            "fragment_retry_sleep_sec:",
            self.fragment_retry_sleep_sec_var,
        )
        self._add_entry_row(
            self.download_tab,
            7,
            "socket_timeout_sec:",
            self.socket_timeout_sec_var,
        )
        self._add_entry_row(
            self.download_tab,
            8,
            "concurrent_fragment_downloads:",
            self.concurrent_fragment_downloads_var,
        )

        flags = ttk.LabelFrame(self.download_tab, text="Флаги", padding=12)
        flags.grid(row=9, column=0, columnspan=3, sticky="ew", pady=(12, 0))

        ttk.Checkbutton(flags, text="Не скачивать плейлисты", variable=self.noplaylist_var).grid(
            row=0,
            column=0,
            sticky="w",
            padx=(0, 16),
            pady=(0, 8),
        )
        ttk.Checkbutton(flags, text="quiet", variable=self.quiet_var).grid(
            row=0,
            column=1,
            sticky="w",
            padx=(0, 16),
            pady=(0, 8),
        )
        ttk.Checkbutton(
            flags,
            text="Сохранять thumbnail",
            variable=self.write_thumbnail_var,
        ).grid(row=1, column=0, sticky="w", padx=(0, 16))
        ttk.Checkbutton(
            flags,
            text="Сохранять info.json",
            variable=self.write_info_json_var,
        ).grid(row=1, column=1, sticky="w", padx=(0, 16))

    def _build_http_tab(self) -> None:
        self.http_tab.columnconfigure(0, weight=1)
        self.http_tab.rowconfigure(2, weight=1)

        cookie_frame = ttk.LabelFrame(self.http_tab, text="Cookie", padding=12)
        cookie_frame.grid(row=0, column=0, sticky="nsew")
        cookie_frame.columnconfigure(0, weight=1)
        cookie_frame.rowconfigure(0, weight=1)
        cookie_box, self.cookie_text = self._create_text_box(cookie_frame, height=4)
        cookie_box.grid(row=0, column=0, sticky="nsew")

        meta_frame = ttk.Frame(self.http_tab)
        meta_frame.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        meta_frame.columnconfigure(1, weight=1)

        self._add_entry_row(
            meta_frame,
            0,
            "Файл cookies:",
            self.cookie_file_var,
            self._choose_cookie_file,
            "Файл...",
        )
        self._add_entry_row(meta_frame, 1, "User-Agent:", self.user_agent_var)
        self._add_entry_row(meta_frame, 2, "Referer:", self.referer_var)

        headers_frame = ttk.LabelFrame(
            self.http_tab,
            text="Дополнительные заголовки (по одному на строку, формат Header: Value)",
            padding=12,
        )
        headers_frame.grid(row=2, column=0, sticky="nsew", pady=(12, 0))
        headers_frame.columnconfigure(0, weight=1)
        headers_frame.rowconfigure(0, weight=1)
        headers_box, self.headers_text = self._create_text_box(headers_frame, height=10)
        headers_box.grid(row=0, column=0, sticky="nsew")

    def _build_targets_tab(self) -> None:
        self.targets_tab.columnconfigure(0, weight=1)
        self.targets_tab.rowconfigure(0, weight=1)

        urls_frame = ttk.LabelFrame(
            self.targets_tab,
            text="Ссылки (по одной на строку, строки с # считаются комментариями)",
            padding=12,
        )
        urls_frame.grid(row=0, column=0, sticky="nsew")
        urls_frame.columnconfigure(0, weight=1)
        urls_frame.rowconfigure(0, weight=1)
        urls_box, self.urls_text = self._create_text_box(urls_frame, height=14)
        urls_box.grid(row=0, column=0, sticky="nsew")

        file_frame = ttk.Frame(self.targets_tab)
        file_frame.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        file_frame.columnconfigure(1, weight=1)
        self._add_entry_row(
            file_frame,
            0,
            "Файл со ссылками:",
            self.urls_file_var,
            self._choose_urls_file,
            "Файл...",
        )

        ttk.Label(
            self.targets_tab,
            text="GUI объединяет ссылки из поля выше и из файла, затем убирает дубликаты.",
        ).grid(row=2, column=0, sticky="w", pady=(8, 0))

    def _build_actions(self) -> None:
        frame = ttk.Frame(self)
        frame.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 8))
        frame.columnconfigure(2, weight=1)

        self.start_button = ttk.Button(frame, text="Запустить скачивание", command=self._start_download)
        self.start_button.grid(row=0, column=0, sticky="w", padx=(0, 8))

        self.clear_log_button = ttk.Button(frame, text="Очистить лог", command=self._clear_log)
        self.clear_log_button.grid(row=0, column=1, sticky="w")

        ttk.Label(frame, textvariable=self.status_var).grid(row=0, column=2, sticky="e")

    def _build_log_panel(self) -> None:
        frame = ttk.LabelFrame(self, text="Лог", padding=12)
        frame.grid(row=3, column=0, sticky="nsew", padx=12, pady=(0, 12))
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        log_box, self.log_text = self._create_text_box(frame, height=14)
        log_box.grid(row=0, column=0, sticky="nsew")
        self.log_text.configure(state="disabled")

    def _create_text_box(self, parent: ttk.Frame, height: int) -> tuple[ttk.Frame, tk.Text]:
        frame = ttk.Frame(parent)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(0, weight=1)

        text = tk.Text(frame, height=height, wrap="word", font=("Consolas", 10))
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)

        text.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        return frame, text

    def _add_entry_row(
        self,
        parent: ttk.Frame,
        row: int,
        label: str,
        variable: tk.StringVar,
        browse_command: Any | None = None,
        button_text: str = "Выбрать...",
    ) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=6, padx=(0, 8))
        ttk.Entry(parent, textvariable=variable).grid(row=row, column=1, sticky="ew", pady=6)

        if browse_command is not None:
            ttk.Button(parent, text=button_text, command=browse_command).grid(
                row=row,
                column=2,
                sticky="w",
                pady=6,
                padx=(8, 0),
            )

    def _load_initial_settings(self) -> None:
        default_config = get_default_config_path()
        default_example = get_example_config_path()
        self.config_path_var.set(str(default_config))

        if default_config.exists():
            self._load_selected_config(show_message=False)
            return

        if default_example.exists():
            try:
                raw_settings = load_settings(default_example)
                self.extra_settings = self._extract_unknown_settings(raw_settings)
                self._apply_settings(raw_settings)
            except Exception as error:  # noqa: BLE001
                self._append_log(f"[GUI] Не удалось загрузить settings.example.toml: {error}")
            else:
                self._append_log(
                    "[GUI] settings.toml не найден. В форму загружен settings.example.toml."
                )
                self.status_var.set("Загружен settings.example.toml.")
                return

        self.extra_settings = {}
        self._apply_settings(self.default_settings)
        self._append_log(
            f"[GUI] {default_config.name} рядом с приложением не найден. Загружены значения по умолчанию."
        )
        self.status_var.set("Загружены значения по умолчанию.")

    def _choose_config_file(self) -> None:
        file_path = filedialog.askopenfilename(
            title="Выберите TOML-конфиг",
            filetypes=[("TOML files", "*.toml"), ("All files", "*.*")],
        )
        if file_path:
            self.config_path_var.set(file_path)

    def _choose_output_dir(self) -> None:
        directory = filedialog.askdirectory(title="Выберите папку для выгрузки")
        if directory:
            self.output_dir_var.set(directory)

    def _choose_archive_file(self) -> None:
        initial = self._safe_parent_dir(self.archive_file_var.get())
        file_path = filedialog.asksaveasfilename(
            title="Файл архива скачанных видео",
            initialdir=initial,
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if file_path:
            self.archive_file_var.set(file_path)

    def _choose_cookie_file(self) -> None:
        file_path = filedialog.askopenfilename(
            title="Выберите файл cookies",
            filetypes=[
                ("Text files", "*.txt"),
                ("Cookies files", "*.cookies"),
                ("All files", "*.*"),
            ],
        )
        if file_path:
            self.cookie_file_var.set(file_path)

    def _choose_urls_file(self) -> None:
        file_path = filedialog.askopenfilename(
            title="Выберите файл со ссылками",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if file_path:
            self.urls_file_var.set(file_path)

    def _safe_parent_dir(self, raw_path: str) -> str:
        if raw_path.strip():
            return str(Path(raw_path).expanduser().resolve().parent)
        return str(get_app_dir())

    def _current_config_path(self) -> Path:
        raw_value = self.config_path_var.get().strip()
        if not raw_value:
            return get_default_config_path()
        return Path(raw_value).expanduser().resolve()

    def _load_selected_config(self, show_message: bool = True) -> None:
        config_path = self._current_config_path()
        try:
            raw_settings = load_settings(config_path)
            self.extra_settings = self._extract_unknown_settings(raw_settings)
            self._apply_settings(raw_settings)
        except Exception as error:  # noqa: BLE001
            messagebox.showerror("Ошибка загрузки", str(error))
            self.status_var.set("Не удалось загрузить конфиг.")
            return

        self._append_log(f"[GUI] Конфиг загружен: {config_path}")
        self.status_var.set(f"Конфиг загружен: {config_path.name}")
        if show_message:
            messagebox.showinfo("Конфиг загружен", f"Файл успешно загружен:\n{config_path}")

    def _save_config(self, save_as: bool = False) -> None:
        config_path = self._current_config_path()
        if save_as:
            selected = filedialog.asksaveasfilename(
                title="Сохранить конфиг как",
                defaultextension=".toml",
                initialfile=config_path.name,
                initialdir=str(config_path.parent),
                filetypes=[("TOML files", "*.toml"), ("All files", "*.*")],
            )
            if not selected:
                return
            config_path = Path(selected).expanduser().resolve()
            self.config_path_var.set(str(config_path))

        try:
            settings = self._collect_settings()
            save_settings(config_path, settings)
            self.extra_settings = self._extract_unknown_settings(settings)
        except Exception as error:  # noqa: BLE001
            messagebox.showerror("Ошибка сохранения", str(error))
            self.status_var.set("Не удалось сохранить конфиг.")
            return

        self._append_log(f"[GUI] Конфиг сохранен: {config_path}")
        self.status_var.set(f"Конфиг сохранен: {config_path.name}")

    def _reset_to_defaults(self) -> None:
        self.extra_settings = {}
        self._apply_settings(self.default_settings)
        self._append_log("[GUI] В форму подставлены значения по умолчанию.")
        self.status_var.set("Загружены значения по умолчанию.")

    def _extract_unknown_settings(self, settings: dict[str, Any]) -> dict[str, Any]:
        unknown: dict[str, Any] = {}

        for section, value in settings.items():
            if section not in KNOWN_SECTION_FIELDS:
                unknown[section] = deepcopy(value)
                continue
            if not isinstance(value, dict):
                continue

            section_unknown: dict[str, Any] = {}
            for key, nested_value in value.items():
                if key not in KNOWN_SECTION_FIELDS[section]:
                    section_unknown[key] = deepcopy(nested_value)
            if section_unknown:
                unknown[section] = section_unknown

        return unknown

    def _apply_settings(self, settings: dict[str, Any]) -> None:
        general = get_table(settings, "general")
        download = get_table(settings, "download")
        http_settings = get_table(settings, "http")
        targets = get_table(settings, "targets")

        self.output_dir_var.set(get_str(general, "output_dir", "downloads"))
        self.archive_file_var.set(get_str(general, "archive_file", "downloaded.txt"))
        self.continue_on_error_var.set(get_bool(general, "continue_on_error", True))

        self.format_var.set(get_str(download, "format", "bestvideo*+bestaudio/best"))
        self.merge_output_format_var.set(get_str(download, "merge_output_format", "mp4"))
        self.filename_template_var.set(
            get_str(download, "filename_template", "%(title)s [%(id)s].%(ext)s")
        )
        self.retries_var.set(str(get_int(download, "retries", 30)))
        self.fragment_retries_var.set(str(get_int(download, "fragment_retries", 30)))
        self.extractor_retries_var.set(str(get_int(download, "extractor_retries", 3)))
        self.fragment_retry_sleep_sec_var.set(str(get_int(download, "fragment_retry_sleep_sec", 5)))
        self.socket_timeout_sec_var.set(str(get_int(download, "socket_timeout_sec", 30)))
        self.concurrent_fragment_downloads_var.set(
            str(get_int(download, "concurrent_fragment_downloads", 1))
        )
        self.noplaylist_var.set(get_bool(download, "noplaylist", True))
        self.quiet_var.set(get_bool(download, "quiet", False))
        self.write_thumbnail_var.set(get_bool(download, "write_thumbnail", False))
        self.write_info_json_var.set(get_bool(download, "write_info_json", False))

        self.cookie_file_var.set(get_str(http_settings, "cookie_file"))
        self.user_agent_var.set(get_str(http_settings, "user_agent"))
        self.referer_var.set(get_str(http_settings, "referer"))

        headers = http_settings.get("headers", {})
        if headers and not isinstance(headers, dict):
            raise TypeError("Секция [http.headers] должна быть таблицей.")

        urls = targets.get("urls", [])
        if urls and not isinstance(urls, list):
            raise TypeError("Параметр 'targets.urls' должен быть списком.")

        self._set_text(self.cookie_text, get_str(http_settings, "cookie"))
        self._set_text(self.headers_text, self._format_headers(headers))
        self._set_text(self.urls_text, self._format_urls(urls))
        self.urls_file_var.set(get_str(targets, "urls_file"))

    def _format_headers(self, headers: dict[str, Any]) -> str:
        return "\n".join(f"{key}: {value}" for key, value in headers.items())

    def _format_urls(self, urls: list[Any]) -> str:
        return "\n".join(str(url).strip() for url in urls if str(url).strip())

    def _set_text(self, widget: tk.Text, value: str) -> None:
        widget.delete("1.0", tk.END)
        widget.insert("1.0", value)

    def _get_text(self, widget: tk.Text) -> str:
        return widget.get("1.0", tk.END).strip()

    def _parse_int(self, raw_value: str, label: str, default: int) -> int:
        prepared = raw_value.strip()
        if not prepared:
            return default
        try:
            return int(prepared)
        except ValueError as error:
            raise ValueError(f"Поле '{label}' должно быть целым числом.") from error

    def _parse_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        for line_number, raw_line in enumerate(self._get_text(self.headers_text).splitlines(), start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            separator = ":" if ":" in line else "=" if "=" in line else None
            if separator is None:
                raise ValueError(
                    f"Строка {line_number} в дополнительных заголовках должна быть в формате Header: Value."
                )

            key, value = line.split(separator, 1)
            prepared_key = key.strip()
            prepared_value = value.strip()
            if not prepared_key or not prepared_value:
                raise ValueError(
                    f"Строка {line_number} в дополнительных заголовках заполнена не полностью."
                )
            headers[prepared_key] = prepared_value

        return headers

    def _parse_urls(self) -> list[str]:
        urls: list[str] = []
        for raw_line in self._get_text(self.urls_text).splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            urls.append(line)
        return urls

    def _collect_settings(self) -> dict[str, Any]:
        settings = deepcopy(self.extra_settings)

        general = {
            "output_dir": self.output_dir_var.get().strip() or "downloads",
            "continue_on_error": bool(self.continue_on_error_var.get()),
            "archive_file": self.archive_file_var.get().strip(),
        }
        download = {
            "format": self.format_var.get().strip() or "bestvideo*+bestaudio/best",
            "merge_output_format": self.merge_output_format_var.get().strip() or "mp4",
            "filename_template": self.filename_template_var.get().strip()
            or "%(title)s [%(id)s].%(ext)s",
            "retries": self._parse_int(self.retries_var.get(), "retries", 30),
            "fragment_retries": self._parse_int(
                self.fragment_retries_var.get(),
                "fragment_retries",
                30,
            ),
            "extractor_retries": self._parse_int(
                self.extractor_retries_var.get(),
                "extractor_retries",
                3,
            ),
            "fragment_retry_sleep_sec": self._parse_int(
                self.fragment_retry_sleep_sec_var.get(),
                "fragment_retry_sleep_sec",
                5,
            ),
            "socket_timeout_sec": self._parse_int(
                self.socket_timeout_sec_var.get(),
                "socket_timeout_sec",
                30,
            ),
            "concurrent_fragment_downloads": self._parse_int(
                self.concurrent_fragment_downloads_var.get(),
                "concurrent_fragment_downloads",
                1,
            ),
            "noplaylist": bool(self.noplaylist_var.get()),
            "quiet": bool(self.quiet_var.get()),
            "write_thumbnail": bool(self.write_thumbnail_var.get()),
            "write_info_json": bool(self.write_info_json_var.get()),
        }
        http_settings = {
            "cookie": self._get_text(self.cookie_text),
            "cookie_file": self.cookie_file_var.get().strip(),
            "user_agent": self.user_agent_var.get().strip(),
            "referer": self.referer_var.get().strip(),
            "headers": self._parse_headers(),
        }
        targets = {
            "urls": self._parse_urls(),
            "urls_file": self.urls_file_var.get().strip(),
        }

        self._merge_section(settings, "general", general)
        self._merge_section(settings, "download", download)
        self._merge_section(settings, "http", http_settings)
        self._merge_section(settings, "targets", targets)
        return settings

    def _merge_section(
        self,
        settings: dict[str, Any],
        section_name: str,
        section_values: dict[str, Any],
    ) -> None:
        current = settings.get(section_name, {})
        merged_section = deepcopy(current) if isinstance(current, dict) else {}
        merged_section.update(section_values)
        settings[section_name] = merged_section

    def _start_download(self) -> None:
        if self.is_running:
            return

        try:
            settings = self._collect_settings()
        except Exception as error:  # noqa: BLE001
            messagebox.showerror("Некорректные настройки", str(error))
            return

        config_dir = self._current_config_path().parent
        self._set_running(True)
        self._append_log("[GUI] Запуск скачивания из текущих значений формы.")

        self.download_thread = threading.Thread(
            target=self._download_worker,
            args=(settings, config_dir),
            daemon=True,
        )
        self.download_thread.start()

    def _download_worker(self, settings: dict[str, Any], config_dir: Path) -> None:
        exit_code = 1
        try:
            exit_code = run_download(settings, config_dir, log=self._enqueue_log)
        except Exception as error:  # noqa: BLE001
            self._enqueue_log(f"[Ошибка] {error}")
        finally:
            self.event_queue.put(("done", exit_code))

    def _enqueue_log(self, message: str) -> None:
        self.event_queue.put(("log", message))

    def _process_events(self) -> None:
        while True:
            try:
                event_type, payload = self.event_queue.get_nowait()
            except queue.Empty:
                break

            if event_type == "log":
                self._append_log(str(payload))
                continue

            if event_type == "done":
                exit_code = int(payload)
                self._set_running(False)
                if exit_code == 0:
                    self.status_var.set("Скачивание завершено без ошибок.")
                    messagebox.showinfo("Готово", "Скачивание завершено без ошибок.")
                else:
                    self.status_var.set("Скачивание завершено с ошибками.")
                    messagebox.showwarning(
                        "Скачивание завершено",
                        "Скачивание завершено с ошибками. Подробности есть в логе.",
                    )

        if not self.is_closed:
            self.after(100, self._process_events)

    def _set_running(self, running: bool) -> None:
        self.is_running = running
        self.start_button.configure(state="disabled" if running else "normal")

        state = "disabled" if running else "normal"
        for button in self.config_buttons:
            button.configure(state=state)

        if running:
            self.status_var.set("Идет скачивание...")

    def _append_log(self, message: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state="disabled")

    def _clear_log(self) -> None:
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state="disabled")

    def _on_close(self) -> None:
        if self.is_running:
            should_close = messagebox.askyesno(
                "Закрыть окно",
                "Скачивание еще идет. Закрыть окно и прервать отображение лога?",
            )
            if not should_close:
                return

        self.is_closed = True
        self.destroy()


def main() -> int:
    ensure_supported_python()
    app = DownloaderGUI()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
