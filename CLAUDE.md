# CLAUDE.md — Stitcher Project

## Что это

**Stitcher** — локальный автоматизированный пайплайн склейки видео.
По набору YouTube-ссылок из Google Sheet выполняет скачивание, нормализацию
и финальную склейку видео в один MP4-файл.

```
Google Sheet → SheetClient (raw) → RowEnricher (metadata+lang) → SlotLoader → StitchJob → StitchPipeline → MP4
                                                                                                ↑
                                                                                    Telegram bot (bot.py, отдельная точка входа)
```

## Структура проекта

```
stitcher/
  main.py                    # CLI entry point (argparse: --dry-run, --debug)
  bot.py                     # Telegram bot entry point (aiogram 3.x)
  build_cli.bat              # Сборка CLI EXE через PyInstaller
  stitcher.spec              # PyInstaller spec (onedir, CLI-only)
  dist_layout.md             # Описание portable-структуры дистрибутива
  config.toml                # TOML-конфигурация
  requirements.txt           # Python-зависимости
  profiles/
    gpu_nvenc.txt            # ffmpeg GPU профиль (h264_nvenc)
    cpu_libx264.txt          # ffmpeg CPU fallback профиль
  app/
    config/
      settings.py            # Frozen dataclasses: StitcherConfig, EnvConfig и др.
      config_loader.py       # load_config() → StitcherConfig из config.toml
    models/
      domain.py              # Доменные модели: StitchJob, SlotKey, SourceVideo, WorkerResult
    ingest/
      link_normalizer.py     # normalize_youtube_link(), extract_youtube_video_id()
      youtube_metadata.py    # YtDlpBinaryMetadataFetcher — metadata через бинарник yt-dlp
      language_detector.py   # detect_language() — по metadata + langdetect fallback
    input/
      sheet_reader.py        # SlotLoader: Google Sheet → list[StitchJob]
      row_enricher.py        # RowEnricher: обогащение строк метаданными yt-dlp
      sheet_parser.py        # parse_sheet_datetime() — парсинг дат из таблицы
    download/
      video_downloader.py    # VideoDownloader.download() → DownloadedVideo
      thumbnail_fetcher.py   # ThumbnailFetcher.fetch() → DownloadedThumbnail
    transcode/
      video_normalizer.py    # VideoNormalizer.normalize() → NormalizedSegment
      thumbnail_clip.py      # ThumbnailClipBuilder.build_clip() → NormalizedSegment
      fade_clip.py           # FadeClipBuilder — fade-переход для превью
    concat/
      manifest_builder.py    # build_manifest() — ffmpeg concat list
      final_concat.py        # FinalConcat.concat(), build_output_filename()
    ffmpeg/
      command_builder.py     # load_profile(), build_*_command()
      codec_fallback.py      # run_with_fallback() — GPU → CPU fallback
    bot/
      handlers.py            # aiogram handlers: /start, /stop, stitch pipeline
      auth.py                # Telegram auth: проверка user_id по спискам
    runtime/
      paths.py               # PROJECT_ROOT (frozen-aware), StitcherPaths, get_project_paths()
      logging_config.py      # setup_logging(), setup_bot_logging(), get_logger()
      env_loader.py          # load_env_file(), load_env_config() → EnvConfig
      cleanup.py             # run_startup_cleanup() — очистка temp и logs
      ytdlp_updater.py       # maybe_update_ytdlp() — автообновление yt-dlp
    google/
      auth.py                # GoogleServicesFactory (OAuth2, sheets.readonly scope)
      sheets_client.py       # GoogleSheetsClient.read_rows() → list[RawSheetRow]
    worker/
      pipeline.py            # StitchPipeline.run() → WorkerResult
      progress.py            # ProgressTracker, CliProgressTracker
  tests/
    test_bot_auth.py
    test_cmd_run.py
    test_command_builder.py
    test_config.py
    test_fade_clip.py
    test_language_detector.py
    test_manifest_builder.py
    test_models.py
    test_pipeline.py
    test_preflight.py
    test_row_enricher.py
    test_sheet_parser.py
    test_sheet_reader.py
    test_sheets_client_parsing.py
```

## Точки входа

| Файл | Назначение | Команда запуска |
|------|-----------|-----------------|
| `main.py` | CLI-пайплайн | `python main.py` или `main.bat` |
| `bot.py` | Telegram-бот | `python bot.py` или `bot.bat` |
| `stitcher.exe` | Собранный CLI | `stitcher.exe` (после сборки) |

## Рабочие CLI-команды

```bash
python main.py               # Обработать все будущие слоты из Google Sheet
python main.py --dry-run     # Пробный прогон без реальной обработки
python main.py --debug       # Подробное логирование
```

## Конфигурация

- Формат: TOML (`config.toml` в корне проекта)
- Секции: `[paths]` `[tools]` `[ytdlp]` `[encoding]` `[video]` `[audio]` `[thumbnail]` `[output]` `[retention]`
- Все пути в `config.toml` — относительные, резолвятся от `PROJECT_ROOT`
- `PROJECT_ROOT` определяется в `app/runtime/paths.py` (frozen-aware: dev vs EXE)
- Переменные окружения: `secrets/.env` (по образцу `secrets/.env.example`)

## Переменные окружения (`secrets/.env`)

| Переменная | Обязательна для CLI | Назначение |
|-----------|--------------------|-----------| 
| `GOOGLE_SHEETS_ID` | ✅ да | ID Google-таблицы |
| `GOOGLE_DRIVE_FOLDER_ID` | нет | Не используется в CLI |
| `TELEGRAM_BOT_TOKEN` | нет | Только для bot.py |
| `TELEGRAM_CHAT_ID` | нет | Только для bot.py |
| `TELEGRAM_ADMIN_USER_IDS` | нет | Только для bot.py |
| `TELEGRAM_USER_IDS` | нет | Только для bot.py |

## Google OAuth2

- Используется OAuth2 Desktop flow (не service account)
- `secrets/credentials.json` — скачать из Google Cloud Console (Desktop OAuth client)
- `secrets/token.json` — генерируется при первом запуске через браузер

## Тестирование

```bash
pytest tests/
```

Тесты не требуют реального Google API — sheets_client замокан.

## Стиль кода

- Python 3.11+ (tomllib встроен)
- `from __future__ import annotations` в каждом файле
- Type hints везде
- Frozen dataclasses для моделей и конфигурации
- Логирование через `app.runtime.logging_config.get_logger(__name__)`
- Docstrings и комментарии: русский язык

## Фазы разработки

| Фаза | Содержание | Статус |
|------|-----------|--------|
| 0 Init | Структура, зависимости | ✅ Done |
| 1 Config | TOML, профили ffmpeg | ✅ Done |
| 2 Models | Доменные модели | ✅ Done |
| 3 Sheet | Google Sheet input layer | ✅ Done |
| 4 Download | yt-dlp скачивание | ✅ Done |
| 5 FFmpeg | Нормализация, thumb clip | ✅ Done |
| 6 Concat | Manifest, финальная склейка | ✅ Done |
| 7 Worker | Оркестрация пайплайна | ✅ Done |
| 8 CLI | Рабочий CLI-пайплайн | ✅ Done |
| 9 Bot | Telegram-бот (aiogram 3.x) | ✅ Done |
| 10 Build | PyInstaller EXE, portable-дистрибутив | 🔄 In progress |

## Технические константы

- Выходной файл: `{date}_{time}_{lang}.mp4`
- Видео: 1920×1080, 25fps, H.264
- Аудио: AAC, 512k, 48000Hz, stereo
- Thumbnail-клип: 3 секунды (перед каждым видео, включая первое)
- GPU: `h264_nvenc` (из `profiles/gpu_nvenc.txt`) с автоматическим fallback на `libx264`
- Concat: ffmpeg `-f concat -safe 0 -c copy`

## Ключевые ограничения

- Один слот за раз (без очереди задач)
- Целостность: если одно видео не прошло → весь слот падает
- Все видео перекодируются (не копируются)
- Готовый файл не отправляется в Telegram — бот пишет только путь

## НЕ входит в проект

Модули `llm/`, `publish/`, `pipeline/`, `planning/`, `observability/`, `core/`,
`media/`, `net/`, `modes/`, `resources/`, `application/`, `telegram/`,
`telegram_bot/`, `bootstrap/`, `paths/` — удалены при миграции из restreamer.
