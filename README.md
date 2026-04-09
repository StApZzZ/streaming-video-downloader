# Universal Stream Video Downloader

Скрипт скачивает видео с любых сайтов и потоков, которые умеет обрабатывать `yt-dlp`:

- страницы с видео;
- прямые ссылки на `m3u8` и `mpd`;
- защищенные страницы, если передать нужные заголовки, куки или `cookie_file`.

Предварительно работает на (список будет пополняться):
https://boosty.to/
https://www.youtube.com/

Шаблон настроек хранится в `settings.example.toml`, а локальная рабочая копия - в `settings.toml`. Для остальных полезных файлов тоже есть шаблоны: `urls.example.txt` и `cookies.example.txt`.

## GUI

Для графического интерфейса см. [README_GUI.md](README_GUI.md).

Быстрый запуск GUI:

```powershell
python gui.py
```

Если `settings.toml` отсутствует, GUI сначала попробует подхватить `settings.example.toml`, а затем уже встроенные значения по умолчанию.

## Шаблоны файлов

В репозитории лежат готовые примеры файлов, которые обычно нужны рядом с приложением:

- `settings.example.toml` - шаблон основного конфига;
- `urls.example.txt` - пример файла со списком URL для `targets.urls_file`;
- `cookies.example.txt` - пример Netscape cookie file для `http.cookie_file`.

Локальные рабочие копии вроде `settings.toml`, `urls.txt`, `cookies.txt`, `cookies.cookies` и `downloaded.txt` добавлены в `.gitignore`, чтобы их не залить случайно.


## Возможности

- пакетная загрузка нескольких видео;
- единые настройки для всех ссылок;
- поддержка заголовков `Cookie`, `User-Agent`, `Referer` и произвольных HTTP-заголовков;
- архив скачанных видео, чтобы не качать повторно одно и то же;
- продолжение очереди при ошибках на отдельных ссылках;
- отдельный GUI для загрузки, редактирования и сохранения конфигурации.

## Требования

- Python 3.10+;
- `ffmpeg`, если сайт отдает раздельные аудио и видео дорожки и их нужно склеить в `mp4`;
- для GUI нужен `tkinter` (на Windows обычно уже есть в поставке Python).

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

На Python 3.11+ используется стандартный `tomllib`, а на Python 3.10 зависимость `tomli` ставится автоматически из `requirements.txt`.

### Установка ffmpeg

Установите `ffmpeg` через пакетный менеджер вашего дистрибутива.

Пример для Ubuntu/Debian:

```bash
sudo apt update
sudo apt install ffmpeg
```

## Настройка

Скопируйте `settings.example.toml` в `settings.toml` и затем отредактируйте локальный файл:

```powershell
Copy-Item settings.example.toml settings.toml
```

или на Linux:

```bash
cp settings.example.toml settings.toml
```

После этого откройте `settings.toml`:

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

Если ссылок много, удобнее вынести их в отдельный файл, например `urls.txt`. За основу можно взять `urls.example.txt`:

```powershell
Copy-Item urls.example.txt urls.txt
```

или на Linux:

```bash
cp urls.example.txt urls.txt
```

Пример содержимого:

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

## Файл cookies

Если нужен `cookie_file`, можно создать локальный файл на основе `cookies.example.txt`:

```powershell
Copy-Item cookies.example.txt cookies.txt
```

или на Linux:

```bash
cp cookies.example.txt cookies.txt
```

После этого укажите его в конфиге:

```toml
[http]
cookie = ""
cookie_file = "cookies.txt"
```

Обычно реальный cookie-файл удобнее экспортировать из браузера в формате Netscape и просто подложить вместо шаблона.

## Использование на Windows

### Активация venv

```powershell
.\venv\Scripts\Activate.ps1
```

### Запуск GUI

```powershell
python gui.py
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

### Запуск GUI

```bash
python gui.py
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

## Сборка в EXE

Ниже пример сборки GUI-версии приложения в один `.exe` через `PyInstaller` на Windows.

### 1. Активируйте окружение и установите зависимости

```powershell
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pyinstaller
```

### 2. Соберите GUI-приложение

```powershell
pyinstaller --noconfirm --clean --onefile --windowed --name stream-video-downloader-gui gui.py
```

Готовый файл появится в `dist\stream-video-downloader-gui.exe`.

### 3. Что положить рядом с exe

- `settings.example.toml` как шаблон;
- `urls.example.txt` как шаблон списка ссылок;
- `cookies.example.txt` как шаблон cookie-файла;
- при необходимости локальный `settings.toml`;
- `urls.txt`, если используете файл со ссылками;
- файл cookies, если используете `cookie_file`;
- `ffmpeg` должен быть установлен в системе и доступен в `PATH`.

Если рядом с `exe` нет `settings.toml`, GUI попробует загрузить `settings.example.toml`, а если и его нет, стартует со значениями по умолчанию.

### 4. Опционально: сборка консольной версии

```powershell
pyinstaller --noconfirm --clean --onefile --name stream-video-downloader downloader.py
```

## Как использовать для защищенных страниц

1. Откройте страницу с видео в браузере.
2. В DevTools найдите запрос к странице или потоку.
3. Скопируйте при необходимости `Cookie`, `User-Agent`, `Referer` или `Authorization`.
4. Запишите их в локальный `settings.toml` или в GUI.
5. Добавьте URL страницы видео или прямой URL потока в список ссылок.

## Примечания

- Повторяющиеся ссылки автоматически убираются.
- Уже скачанные элементы пропускаются через `downloaded.txt`.
- Если конкретный сайт не поддерживается `yt-dlp`, скрипт тоже не сможет его скачать без дополнительной доработки.
