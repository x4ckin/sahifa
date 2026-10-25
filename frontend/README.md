# Sahifa — Mini App

Telegram Mini App (Vue 3 + Vite) for Sahifa: build a free 3D-gift museum that lives in the user's
Telegram account, decorate it, gift it (Telegram Stars or card transfer), manage gifted museums,
and view a gift (also in a normal browser).

Design: `docs/superpowers/specs/2026-10-25-sahifa-miniapp-design.md`

## Develop

```bash
cd frontend
npm install
cp .env.example .env.local   # VITE_API_URL (backend, https), VITE_BOT_USERNAME
npm run dev                  # http://localhost:5173 — outside Telegram, CloudStorage falls back to localStorage
npm test                     # Vitest
npm run build                # type-check + dist/
```

Inside Telegram the app needs an HTTPS address: deploy to GitHub Pages (below) or tunnel the dev
server, and set it in BotFather (Bot Settings → Menu Button / Configure Mini App).

## Structure

| Path | Role |
|---|---|
| `src/telegram.ts` | the only code that touches the Telegram SDK (works without it) |
| `src/api.ts` | the only code that talks to the backend |
| `src/account/store.ts` | free museums in Telegram CloudStorage (crash- and multi-device-safe revisions) |
| `src/upload/queue.ts` | parallel-limited uploads to the user's Telegram chat |
| `src/catalog.ts` | theme / opening / mascot / template keys shared with the backend and 3D scene |
| `src/views/*` | screens: Home, New (media → decor → review), Gift, Order, Done, ServerMuseum, LocalMuseum, Viewer |

## Deploy (GitHub Pages)

`.github/workflows/pages.yml` builds and publishes `frontend/dist` on every push to `main`.
In the GitHub repo: Settings → Pages → Source "GitHub Actions"; Settings → Variables →
`SAHIFA_API_URL` (e.g. `https://sahifa.tailXXXX.ts.net`) and `SAHIFA_BOT_USERNAME`.
The backend's `SAHIFA_WEBAPP_URL` must be the Pages address (`https://<user>.github.io/<repo>`).
