# CLAUDE.md — Stitcher Project

## Что это

**Stitcher** — локальный автоматизированный пайплайн склейки видео.
По набору YouTube-ссылок из Google Sheet выполняет скачивание, нормализацию
и финальную склейку видео в один MP4-файл.

```
Google Sheet → SheetClient (raw) → RowEnricher (metadata+lang) → SlotLoader → StitchJob → Worker → MP4
                                                                       ↑
                                                                Telegram bot (пульт управления)
```

Связанный проект: **restreamer** (публикует слоты в Google Sheet).

## Структура проекта

```
stitcher/
  main.py                    # CLI entry point (argparse)
  bot.py                     # Telegram bot entry point (заглушка)
  config.toml                # TOML-конфигурация
  requirements.txt           # Python-зависимости (минимальный набор)
  ffmpeg_profiles/           # Профили кодирования ffmpeg
    gpu_nvenc.txt
    cpu_libx264.txt
  app/
    config/
      settings.py            # Frozen dataclasses конфигурации (StitcherConfig)
      config_loader.py       # load_config() → StitcherConfig из config.toml
    models/
      domain.py              # Все доменные модели: StitchJob, SlotKey, SourceVideo и др.
    ingest/
      link_normalizer.py     # normalize_youtube_link(), extract_youtube_video_id()
      youtube_metadata.py    # YtDlpBinaryMetadataFetcher — metadata через бинарник yt-dlp.exe
      language_detector.py   # detect_language() — по metadata + langdetect fallback
    input/
      sheet_reader.py        # SlotLoader: Google Sheet → list[StitchJob]
      sheet_parser.py        # parse_sheet_datetime() — парсинг дат из таблицы
    download/
      video_downloader.py    # VideoDownloader.download() → DownloadedVideo
      thumbnail_fetcher.py   # ThumbnailFetcher.fetch() → DownloadedThumbnail
    transcode/
      video_normalizer.py    # VideoNormalizer.normalize() → NormalizedSegment
      thumbnail_clip.py      # ThumbnailClipBuilder.build_clip() → NormalizedSegment
    concat/
      manifest_builder.py    # build_manifest()
      final_concat.py        # FinalConcat.concat(), build_output_filename()
    ffmpeg/
      command_builder.py     # load_profile(), build_*_command()
      codec_fallback.py      # run_with_fallback()
    bot/                     # (пусто) Фаза 9: Telegram handlers
    runtime/
      paths.py               # PROJECT_ROOT, StitcherPaths, get_project_paths()
      logging_config.py      # setup_logging(), setup_bot_logging(), get_logger()
      cleanup.py             # run_startup_cleanup() — очистка temp и logs
    google/
      auth.py                # GoogleServicesFactory (sheets.readonly scope)
      sheets_client.py       # GoogleSheetsClient.read_rows() → list[RawSheetRow]
    worker/
      pipeline.py            # StitchPipeline.run() → WorkerResult
      progress.py            # ProgressTracker, CliProgressTracker
  tests/
    test_config.py           # Тест загрузки конфига
    test_models.py           # Тест создания доменных моделей
    test_sheet_parser.py     # Тест парсинга дат
    test_sheet_reader.py     # Тест группировки слотов (с моками)
```

## Рабочие CLI-команды

```bash
python main.py --check-config        # Загрузить и вывести конфигурацию
python main.py --list-slots           # Показать будущие слоты из Google Sheet
python main.py --slot KEY             # Полный пайплайн по слоту Google Sheet
python main.py --slot KEY --dry-run   # Пробный прогон без запуска пайплайна
python main.py --urls URL1 URL2       # Полный пайплайн в ручном режиме
python main.py --file links.txt       # Полный пайплайн по файлу ссылок
```

## Конфигурация

- Формат: TOML (`config.toml` в корне проекта)
- Секции: `[paths]` `[tools]` `[encoding]` `[video]` `[audio]` `[thumbnail]` `[output]` `[retention]` `[telegram]` `[google]`
- Токен бота: `[telegram].bot_token` или env `STITCHER_BOT_TOKEN`
- Python 3.11+ (tomllib встроен)

## Тестирование

```bash
pytest tests/
```

Тесты не требуют реального Google API — sheets_client замокан.

## Стиль кода

- Python 3.11+
- `from __future__ import annotations` в каждом файле
- Type hints везде
- Frozen dataclasses для моделей и конфигурации
- Логирование через `app.runtime.logging_config.get_logger(__name__)`
- Формат логов: `"%(asctime)s | %(levelname)s | %(name)s | %(message)s"`
- Docstrings и комментарии: русский язык

## Фазы разработки

| Фаза | Содержание | Статус |
|------|-----------|--------|
| 0 Init | Структура, зависимости, утилиты | ✅ Done |
| 1 Config | TOML, профили ffmpeg | ✅ Done |
| 2 Models | Доменные модели | ✅ Done |
| 3 Sheet | Google Sheet input layer | ✅ Done |
| 4 Download | yt-dlp скачивание | ✅ Done |
| 5 FFmpeg | Нормализация, thumb clip | ✅ Done |
| 6 Concat | Manifest, финальная склейка | ✅ Done |
| 7 Worker | Оркестрация пайплайна | ✅ Done |
| 8 CLI | MILESTONE 1: рабочий CLI | ✅ Done (--slot, --urls, --file работают) |
| 9 Bot | MILESTONE 2: Telegram-бот | ✅ Done |
| 10 Build | PyInstaller, дистрибутив | Pending |

## Worker pipeline (реализованные модули)

app/download/video_downloader.py  — VideoDownloader.download() → DownloadedVideo  
app/download/thumbnail_fetcher.py — ThumbnailFetcher.fetch() → DownloadedThumbnail  
app/transcode/video_normalizer.py — VideoNormalizer.normalize() → NormalizedSegment  
app/transcode/thumbnail_clip.py   — ThumbnailClipBuilder.build_clip() → NormalizedSegment  
app/ffmpeg/command_builder.py     — load_profile(), build_*_command()  
app/ffmpeg/codec_fallback.py      — run_with_fallback()  
app/concat/manifest_builder.py    — build_manifest()  
app/concat/final_concat.py        — FinalConcat.concat()  
app/worker/pipeline.py            — StitchPipeline.run() → WorkerResult  
app/worker/progress.py            — ProgressTracker, CliProgressTracker

## Telegram Bot

- Библиотека: aiogram 3.x
- Режимы: polling (по умолчанию), oneshot
- Команды: /start, /stitch, /status, /cancel
- Один слот за раз (threading.Lock)
- Pipeline запускается в отдельном потоке
- Прогресс обновляется в Telegram-сообщении

## Ключевые ограничения

- Один слот за раз (без очереди задач)
- Целостность: если одно видео не прошло → весь слот падает
- Все видео всегда перекодируются (не копируются)
- Готовый файл не отправляется в Telegram — бот пишет только путь

## НЕ входит в проект (удалено из restreamer)

Модули `llm/`, `publish/`, `pipeline/`, `planning/`, `observability/`, `core/`,
`media/`, `net/`, `modes/`, `resources/`, `application/`, `telegram/`,
`telegram_bot/`, `bootstrap/`, `paths/` — не используются в stitcher.
