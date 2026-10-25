# Sahifa — backend

Telegram bot + HTTP API for Sahifa, the 3D gift-museum bot. One Python process runs the
FastAPI API, the aiogram bot (long polling) and the daily housekeeping jobs.

Design: `docs/superpowers/specs/2026-10-25-sahifa-design.md`

## Run locally

```bash
py -m venv .venv
.venv/Scripts/python -m pip install -e "backend[dev]"
cp deploy/.env.example backend/.env   # fill in the values
cd backend && ../.venv/Scripts/python -m sahifa.main
```

`ffmpeg` and `ffprobe` must be on `PATH` (Windows: `winget install Gyan.FFmpeg`).

Tests: `cd backend && ../.venv/Scripts/python -m pytest -q`

## Free museums live in Telegram

An unpaid museum is not stored on this server. Its settings sit in the Mini App's Telegram
CloudStorage; its photos/videos are sent by the bot into the user's own chat
(`POST /api/tg-media` returns a signed token) and shown through `GET /api/tg-media/{token}`,
which streams from Telegram without writing to disk. Files must be ≤ 20 MB (Bot API limit).
When the user gifts it, `POST /api/museums/import` copies it into a normal server museum.

## Settings (`SAHIFA_*`)

| Variable | Meaning |
|---|---|
| `BOT_TOKEN`, `BOT_USERNAME` | from @BotFather |
| `ADMIN_IDS` | JSON list of admin Telegram ids |
| `ADMIN_CHAT_ID` | group that receives card receipts (the bot must be a member) |
| `PUBLIC_API_URL` | public HTTPS address of this server |
| `WEBAPP_URL` | Mini App address (GitHub Pages) |
| `DATABASE_URL`, `MEDIA_DIR` | default `./data/...`; receipts go to `data/receipts` (never served) |

## BotFather

1. `/newbot` → token.
2. `/mybots` → Bot Settings → **Menu Button** is set automatically on start (needs an `https` `WEBAPP_URL`).
3. Payments in Telegram Stars need no provider setup.

## Admin commands (in a private chat with the bot)

| Command | Does |
|---|---|
| `/stats` | users, museums, payments today and in total |
| `/narx [product currency value]` | show or set prices (`museum`, `reactivate`, `room`, `slots`; `uzs` or `stars`) |
| `/karta 8600 1234 5678 9012 Ism Familiya` | card(s) for transfers, one per line; `/karta tozalash` clears |
| `/bepul <id\|@username> [days]` | free use of everything (or reply to the user's forwarded message) |
| `/bepul_ochir <id\|@username>`, `/bepullar` | revoke, list |
| `/xabar` (as a reply) | copy that message to every user |
| `/qaytar <code>` | refund a Stars order |
| `/cheklar` | re-send every card receipt still waiting for a decision |

Card receipts arrive in the admin group with ✅ / ❌ buttons.

## Server (Ubuntu, behind a home router)

```bash
cd deploy && cp .env.example .env && nano .env
mkdir -p data && sudo chown 1000:1000 data   # the container runs as uid 1000
docker compose up -d --build
sudo tailscale funnel --bg 8000      # gives https://<host>.<tailnet>.ts.net
```

Back up `deploy/data/` (database, media, receipts). Full deployment and backups come with plan 4.
