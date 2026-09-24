# Rehnuma website (`web/`)

Next.js site for Rehnuma: a home page (what it does, the NEPRA documents it is built on),
an accuracy page (evals, real bugs, known limits), and a chat widget (bottom-left) that talks
to the Rehnuma API on Render.

```bash
cd web
npm install
npm run dev          # http://localhost:3000 (uses the live Render API by default)
npm run lint
npm run build
```

To use a local API instead (`uv run rehnuma-api` in the repo root), create `web/.env.local`:

```
NEXT_PUBLIC_API_URL=http://localhost:7860
```

The API only accepts browser requests from origins listed in `REHNUMA_CORS_ORIGINS`
(default `http://localhost:3000`). After deploying to Vercel, add the Vercel URL there on Render.

| Path | What |
|---|---|
| `src/app/page.tsx` | Home |
| `src/app/accuracy/page.tsx` | Accuracy report (numbers from `docs/`) |
| `src/components/ChatWidget.tsx` | Chat: sample bills, photo upload, Urdu/English, citations |
| `src/lib/api.ts` | Typed API client (shapes mirror `src/rehnuma/api/views.py`) |
| `src/lib/content.ts` | NEPRA document list shown on the home page |
| `src/app/icon.png`, `public/logo-*.png` | Favicon (ر) and wordmark, from the Rehnuma logo |
