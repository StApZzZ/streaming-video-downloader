# Universal Stream Video Downloader

Скрипт скачивает видео с любых сайтов и потоков, которые умеет обрабатывать `yt-dlp`:

- страницы с видео;
- прямые ссылки на `m3u8` и `mpd`;
- защищенные страницы, если передать нужные заголовки, куки или `cookie_file`.

Все настройки вынесены в `settings.toml`, а ссылки можно задавать как прямо в конфиге, так и через отдельный файл.

## Возможности

- пакетная загрузка нескольких видео;
- единые настройки для всех ссылок;
- поддержка заголовков `Cookie`, `User-Agent`, `Referer` и произвольных HTTP-заголовков;
- архив скачанных видео, чтобы не качать повторно одно и то же;
- продолжение очереди при ошибках на отдельных ссылках.

## Требования

- Python 3.10+;
- `ffmpeg`, если сайт отдает раздельные аудио и видео дорожки и их нужно склеить в `mp4`.

## Установка на Windows

### Создание и активация venv

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

Если PowerShell блокирует активацию, можно временно разрешить локальные скрипты для текущего пользователя:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

### Установка зависимостей

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### Установка ffmpeg

Установите `ffmpeg` любым удобным способом и убедитесь, что команда `ffmpeg` доступна в `PATH`.

## Установка на Linux

### Создание и активация venv

```bash
python3 -m venv venv
source venv/bin/activate
```

### Установка зависимостей

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### Установка ffmpeg

Установите `ffmpeg` через пакетный менеджер вашего дистрибутива.

Пример для Ubuntu/Debian:

```bash
sudo apt update
sudo apt install ffmpeg
```

## Настройка

Отредактируйте `settings.toml`:

```toml
[general]
output_dir = "downloads"
continue_on_error = true
archive_file = "downloaded.txt"

[download]
format = "bestvideo*+bestaudio/best"
merge_output_format = "mp4"
filename_template = "%(title)s [%(id)s].%(ext)s"

[http]
cookie = ""
cookie_file = ""
user_agent = ""
referer = ""

[http.headers]
# Authorization = "Bearer your-token"

[targets]
# Можно перечислить ссылки прямо здесь
urls = []
urls_file = ""
```

### Что где задается

- `[general]`:
  - `output_dir` - папка для выгрузки;
  - `continue_on_error` - продолжать ли очередь, если одна из ссылок упала;
  - `archive_file` - файл истории, чтобы пропускать уже скачанные видео.
- `[download]`:
  - `format` - формат `yt-dlp`;
  - `merge_output_format` - формат после склейки;
  - `filename_template` - шаблон имени файла;
  - остальные параметры отвечают за ретраи и работу с фрагментами потока.
- `[http]`:
  - `cookie` - строка из заголовка `Cookie`;
  - `cookie_file` - путь к файлу cookies в формате Netscape;
  - `user_agent` и `referer` - полезны для сайтов с защитой.
- `[http.headers]`:
  - любые дополнительные заголовки, например `Authorization`.
- `[targets]`:
  - `urls` - список ссылок прямо в TOML;
  - `urls_file` - путь к текстовому файлу со ссылками.

## Пул ссылок через файл

Если ссылок много, удобнее вынести их в отдельный файл, например `urls.txt`:

```text
https://example.com/video/1
https://example.com/video/2
# комментарии разрешены
https://example.com/stream/master.m3u8
```

Тогда в `settings.toml`:

```toml
[targets]
urls = []
urls_file = "urls.txt"
```

## Использование на Windows

### Активация venv

```powershell
.\venv\Scripts\Activate.ps1
```

### Запуск с `settings.toml` по умолчанию

```powershell
python downloader.py
```

### Запуск со своим конфигом

```powershell
python downloader.py --config custom-settings.toml
```

### Выход из venv

```powershell
deactivate
```

## Использование на Linux

### Активация venv

```bash
source venv/bin/activate
```

### Запуск с `settings.toml` по умолчанию

```bash
python downloader.py
```

### Запуск со своим конфигом

```bash
python downloader.py --config custom-settings.toml
```

### Выход из venv

```bash
deactivate
```

## Как использовать для защищенных страниц

1. Откройте страницу с видео в браузере.
2. В DevTools найдите запрос к странице или потоку.
3. Скопируйте при необходимости `Cookie`, `User-Agent`, `Referer` или `Authorization`.
4. Запишите их в `settings.toml`.
5. Добавьте URL страницы видео или прямой URL потока в список ссылок.

## Примечания

- Повторяющиеся ссылки автоматически убираются.
- Уже скачанные элементы пропускаются через `downloaded.txt`.
- Если конкретный сайт не поддерживается `yt-dlp`, скрипт тоже не сможет его скачать без дополнительной доработки.
