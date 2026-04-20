# Portable-структура дистрибутива Stitcher CLI

`build_cli.bat` выполняет сборку и автоматически формирует готовый portable-дистрибутив.
После выполнения `build_cli.bat` папка `dist\stitcher\` является самодостаточным корнем:

```
dist\stitcher\               ← portable-корень (можно перенести куда угодно)
  stitcher.exe               ← точка запуска
  config.toml                ← конфигурация (копируется из корня проекта)
  profiles\                  ← ffmpeg-профили (копируются из корня проекта)
    gpu_nvenc.txt
    cpu_libx264.txt
    ytdlp_video.txt
    ytdlp_thumbnail.txt
  tools\                     ← внешние бинарники (копируются из корня проекта)
    _ffmpeg\
      bin\
        ffmpeg.exe
    _yt-dlp\
      yt-dlp.exe
  secrets\                   ← копируется из корня проекта
    .env                     ← GOOGLE_SHEETS_ID и Telegram-переменные
    credentials.json         ← OAuth2 Desktop client из Google Cloud Console
    token.json               ← генерируется при первом запуске (OAuth flow)
  _internal\                 ← Python runtime (не трогать)
  logs\                      ← создаётся автоматически при первом запуске
  temp\                      ← создаётся автоматически при первом запуске
  output\                    ← создаётся автоматически при первом запуске
  state\                     ← создаётся автоматически при первом запуске
```

## Сборка

```
build_cli.bat
```

Скрипт:
1. Запускает PyInstaller с `stitcher.spec`
2. Копирует `config.toml`, `profiles\`, `tools\`, `secrets\` из корня проекта в `dist\stitcher\`
3. Сообщает об отсутствующих ресурсах (WARN), если какой-то папки нет

## Запуск

```
dist\stitcher\stitcher.exe              # обычный прогон
dist\stitcher\stitcher.exe --dry-run    # smoke test без реальной обработки
dist\stitcher\stitcher.exe --debug      # подробное логирование
```

## Примечания

- `token.json` генерируется при первом запуске через браузер (OAuth2 flow).
  После первого успешного входа токен сохраняется и последующие запуски не требуют браузера.
- `profiles\` — внешние файлы, редактируются без пересборки.
- `logs\`, `temp\`, `output\`, `state\` создаются приложением автоматически при первом запуске.
