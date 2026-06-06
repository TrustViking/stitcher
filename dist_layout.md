# Portable / installed структура Stitcher

## Portable build (`dist\stitcher\`)

Создаётся командой `build_stitcher_exe.bat`. Папка `dist\stitcher\` —
самодостаточный portable-корень, его можно переносить целиком.

```
dist\stitcher\
  stitcher.exe              ← точка запуска
  run_debug.bat             ← запуск с выводом exit code и pause
  stitch.ico                ← иконка
  config.toml               ← локальная конфигурация (личный sheets_id)
  config.example.toml       ← шаблон конфигурации
  profiles\                 ← ffmpeg/yt-dlp профили
    gpu_nvenc.txt
    cpu_libx264.txt
    ytdlp_video.txt
    ytdlp_thumbnail.txt
    ytdlp_bestvideo.txt
  tools\                    ← внешние бинарники, автообновляются
    _ffmpeg\bin\
      ffmpeg.exe
    _yt-dlp\
      yt-dlp.exe
    _deno\
      deno.exe
  secrets\
    README.txt              ← инструкция для пользователя
    credentials.json        ← OAuth2 Desktop client (личный)
    token.json              ← создаётся после первого OAuth (личный)
    cookies.txt             ← опционально (личный)
  logs\                     ← создаётся автоматически
  state\                    ← создаётся автоматически
  temp\                     ← создаётся автоматически
  output\                   ← создаётся автоматически
  _internal\                ← Python runtime, не трогать
```

## Installer (`dist\installer\stitcher-setup-<version>.exe`)

Inno Setup-installer ставит то же самое, но с разделением:

- `release` build (`build_release.bat`) — без реальных секретов, без личного
  `sheets_id`. Подходит для GitHub Releases. В `secrets\` только `README.txt`.
  `config.toml` развёртывается из `config.example.toml` при первой установке
  (с пустым `sheets_id`) и не перезаписывается на обновлении (`onlyifdoesntexist`).
- `local` build (`build_local.bat`) — с реальными секретами из локальной
  папки `secrets\` И с личным `config.toml` из корня проекта (включая
  настоящий `sheets_id`). После установки приложение полностью готово
  к запуску без правки конфига. НЕ публиковать. Существующие
  `config.toml`, `credentials.json`, `token.json`, `cookies.txt` у уже
  установленного приложения не перезаписываются (`onlyifdoesntexist`).

Ярлык `Stitcher` на рабочем столе запускает `run_debug.bat`, который
вызывает `stitcher.exe` и оставляет окно консоли открытым после завершения,
чтобы пользователь видел сообщения preflight и итоговый exit code.

## Запуск

```
# Portable
dist\stitcher\stitcher.exe              # обычный прогон
dist\stitcher\stitcher.exe --dry-run    # smoke test без обработки
dist\stitcher\stitcher.exe --debug      # подробное логирование

# Installed (после установки installer'а)
Desktop\Stitcher (ярлык → run_debug.bat → stitcher.exe)
```

## Telegram

Stitcher v1 — локальное CLI/EXE-приложение без Telegram-бота. Запуск только
через ярлык/EXE. Telegram-интеграция может быть добавлена позже как отдельная
точка входа, но не входит в текущую версию.
