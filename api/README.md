# Lumi API (папка api в репозитории Lumi-spase)

Бэкенд платформы Lumi: регистрация/вход, пространства, брони, статистика хозяина.
FastAPI + PostgreSQL. Лежит в подпапке `api/`, а сайт (`index.html`) — в корне того же репозитория.

## Файлы
- `main.py` — весь сервер
- `requirements.txt` — зависимости
- `Procfile` — команда запуска

## Деплой на Railway (один репозиторий, через сайт)

1. В репозитории `Lumi-spase` должна появиться папка `api` с этими тремя файлами.
   (На GitHub: Add file → Upload files → перетащи папку `api` целиком → Commit.)
2. Зайди на railway.app, войди через GitHub.
3. **New Project → Deploy from GitHub repo → выбери `Lumi-spase`.**
4. Открой созданный сервис → **Settings → Root Directory** → впиши `api` → сохрани.
   (Это говорит Railway, что код лежит в подпапке, а не в корне.)
5. В проекте: **New → Database → Add PostgreSQL.**
6. Снова открой сервис с кодом → вкладка **Variables → New Variable:**
   - `DATABASE_URL` = нажми «Add Reference» и выбери `DATABASE_URL` из Postgres
     (или впиши значение `${{Postgres.DATABASE_URL}}`)
   - `SECRET_KEY` = любая длинная случайная строка
7. **Settings → Networking → Generate Domain** → получишь адрес `https://...up.railway.app`.
8. Открой адрес в браузере — должно показать `{"ok": true, "service": "lumi-api"}`.

Важно: GitHub Pages по-прежнему раздаёт сайт из корня (`index.html`), а Railway запускает сервер из папки `api`. Они не мешают друг другу.

Пришли адрес домена — подключу к нему сайт.
