# Portable-структура дистрибутива Stitcher CLI

После сборки через `build_cli.bat` папка `dist/stitcher/` содержит EXE и зависимости.
Для работы рядом с ней нужно положить следующее:

```
stitcher_portable/          ← итоговая папка поставки
  stitcher/                 ← содержимое dist/stitcher/ (EXE + Python runtime)
    stitcher.exe
    profiles/               ← ffmpeg-профили (внутри сборки)
    ...
  config.toml               ← конфигурация (редактируется под окружение)
  secrets/
    .env                    ← GOOGLE_SHEETS_ID и опционально Telegram-переменные
    credentials.json        ← OAuth2 Desktop client из Google Cloud Console
    token.json              ← генерируется при первом запуске (OAuth flow)
  tools/
    _ffmpeg/
      bin/
        ffmpeg.exe
    _yt-dlp/
      yt-dlp.exe
  logs/                     ← создаётся автоматически
  temp/                     ← создаётся автоматически
  output/                   ← создаётся автоматически
  state/                    ← создаётся автоматически
```

## Запуск

```
stitcher\stitcher.exe              # обычный прогон
stitcher\stitcher.exe --dry-run    # smoke test без реальной обработки
stitcher\stitcher.exe --debug      # подробное логирование
```

## Ярлык

Создать ярлык для `stitcher\stitcher.exe`.  
В свойствах ярлыка установить "Рабочая папка" = путь к `stitcher_portable\stitcher\`.  
Ярлык можно вынести куда угодно — он будет работать автономно.

## Примечания

- `token.json` генерируется при первом запуске через браузер (OAuth2 flow).  
  После первого успешного входа токен сохраняется и последующие запуски не требуют браузера.
- Telegram-переменные в `secrets/.env` можно оставить пустыми — CLI их не использует.
- `GOOGLE_DRIVE_FOLDER_ID` в CLI не используется — можно оставить пустым.
