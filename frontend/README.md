# Tickertone frontend

Next.js 14 app (App Router) that consumes the FastAPI `event-intelligence-service` backend
and layers on Supabase auth plus a three-tier scan-quota demo.

## Setup

1. Copy `.env.local.example` to `.env.local` and fill in:
   - `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY` from your Supabase project
   - `SUPABASE_SERVICE_ROLE_KEY` (server-only, used by the quota API routes)
   - `NEXT_PUBLIC_API_BASE_URL` and `BACKEND_API_BASE_URL` pointing at the deployed FastAPI backend
2. In the Supabase SQL editor, run `supabase/migrations/0001_init.sql` once against a fresh project.
3. Install dependencies and run locally:
   ```bash
   npm install
   npm run dev
   ```
4. Visit `http://localhost:3000`.

## Tiers

| Tier       | Daily scans | Price |
| ---------- | ----------- | ----- |
| free       | 1           | A$0   |
| pro        | 3           | A$19  |
| enterprise | unlimited   | A$249 |

Upgrade is a demo (no Stripe); `/api/subscribe` flips `profiles.tier` directly.

## Deploy

Push the `frontend/` directory to a Vercel project and set the same env vars in the Vercel
dashboard. The Supabase migrations must already be applied to the project you connect.
