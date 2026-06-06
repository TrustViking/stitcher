secrets/ — локальные секреты Stitcher

Этот каталог нужен для:

1. credentials.json
   OAuth2 Desktop client из Google Cloud Console.
   Без него Stitcher не сможет читать Google Sheet.

   Где взять:
   - https://console.cloud.google.com → APIs & Services → Credentials
   - Create credentials → OAuth client ID → Desktop application
   - Скачать JSON, переименовать в credentials.json, положить сюда.

2. token.json
   Создаётся автоматически после первого OAuth-входа в браузере.
   Удалять только если нужно перелогиниться под другим аккаунтом.

3. cookies.txt (опционально)
   YouTube cookies в формате Netscape для yt-dlp.
   Нужны, если yt-dlp начинает упираться в "Sign in to confirm you're not a bot".
   Экспортируются вручную браузерным расширением (например, "Get cookies.txt LOCALLY").

Содержимое этого каталога — личные данные. НЕ коммитить в публичный репозиторий.
В .gitignore секреты отфильтрованы; в репо попадает только этот README.txt.
