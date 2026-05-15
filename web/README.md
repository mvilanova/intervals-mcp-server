# Personal health & training dashboard

Self-hosted Next.js dashboard that syncs daily wellness and activity data from Intervals.icu into Postgres, lets you log weight and meal adherence in a few taps from your phone, and surfaces a single "today" view of where you stand against a goal.

Lives alongside the parent repo's [Intervals.icu MCP server](../README.md). The two share an Intervals.icu API key but don't depend on each other.

## Stack

- Next.js 16 (App Router) · TypeScript · Tailwind 4
- Prisma 6 · Postgres 16
- HMAC-signed cookie auth gated by a single PIN (see `proxy.ts`)
- Docker Compose for production · Caddy for automatic HTTPS
- GitHub Actions for typecheck/lint/build + SSH deploy

## Local development

Requires Node 22 and Docker.

```bash
# 1. Postgres for dev (port 5433 so it doesn't clash with anything)
docker compose -f ../deploy/docker-compose.dev.yml up -d

# 2. Local env
cp .env.example .env
# Edit .env — at minimum set DASHBOARD_PIN and SESSION_SECRET.
# Generate SESSION_SECRET with:  openssl rand -hex 32

# 3. Install + apply migrations + seed a user
npm ci
npx prisma migrate dev
npm run db:seed

# 4. Run
npm run dev          # http://localhost:3000
```

Visit `/login`, enter your PIN, and you're in. `/admin/sync` triggers a manual Intervals.icu sync (requires `INTERVALS_API_KEY` and `INTERVALS_ATHLETE_ID` in `.env`); `/health` returns DB + latest-sync status.

Useful npm scripts:

| Script | Purpose |
| --- | --- |
| `npm run dev` | Next.js dev server with HMR |
| `npm run typecheck` | `tsc --noEmit` |
| `npm run lint` | ESLint |
| `npm run build` | Production build (uses `output: "standalone"`) |
| `npm run db:migrate` | `prisma migrate dev` against local Postgres |
| `npm run db:seed` | Insert/upsert the seed user from `SEED_*` env vars |
| `npm run db:studio` | Open Prisma Studio to browse the DB |

## Architecture at a glance

```
web/
├── app/
│   ├── page.tsx              # "Hello, you" landing — proves the stack works end-to-end
│   ├── login/page.tsx        # PIN form + server action that issues a signed cookie
│   ├── admin/sync/page.tsx   # Manual sync trigger + last 10 SyncRun history
│   └── health/route.ts       # GET /health → { ok, db, latestSync }
├── lib/
│   ├── auth.ts               # HMAC sign/verify on a single static payload
│   ├── db.ts                 # Prisma singleton (hot-reload safe)
│   └── sync/
│       ├── intervals.ts      # syncIntervals({ mode }) — fetches + upserts
│       └── types.ts          # zod schemas for the Intervals.icu API shapes
├── proxy.ts                  # Next.js 16 proxy middleware — PIN-gated routing
├── cron.ts                   # Long-running sidecar: full sync on boot, then every N hours
├── prisma/schema.prisma      # 6 models + SyncRun (see below)
└── Dockerfile                # 4 build targets: deps → builder → runner / migrator / cron
```

### Data model

- `User` — one row per athlete (single-user for now)
- `WeightLog` — daily weight, either typed in here or synced from Intervals
- `MealLog` — daily breakfast/comida/merienda/cena × hit/partial/missed
- `DailyMetrics` — synced from Intervals: CTL, ATL, RHR, HRV, sleep, steps, nutrition macros
- `Activity` — synced from Intervals: type, duration, TSS, distance
- `DailySummary` — AI-generated daily review text (reserved for a later phase)
- `SyncRun` — one row per sync attempt with counts and errors; partial unique index `WHERE finishedAt IS NULL` enforces a single in-progress sync at a time

## Production deploy

The `web/` image is consumed by the compose stack at `../deploy/docker-compose.yml`. Four services run together: `postgres`, a one-shot `migrate` sidecar (builds against the `migrator` target), the `web` runner, a `cron` sidecar that runs `cron.ts`, and `caddy` for TLS.

```bash
# On the VPS, after `git pull`:
docker compose -f deploy/docker-compose.yml --env-file deploy/.env up -d --build
```

CI (`.github/workflows/web-ci.yml`) typechecks + builds on every PR and SSH-deploys on push to `main`. After deploy it polls `docker compose ps` until the `web` service reports `healthy`, then prunes dangling images. A web-service healthcheck against `/health` makes that polling meaningful.

## Auth model (v1)

Single-user: a PIN in env (`DASHBOARD_PIN`) plus a server-side secret (`SESSION_SECRET`) HMAC-signed into a cookie. Both must be set or the proxy returns 503 — there's no fail-open path. When multi-tenant comes later, this gets replaced with real per-user sessions; the cookie scheme is intentionally minimum-viable.

## Env vars

See [`./.env.example`](./.env.example) for local dev and [`../deploy/.env.example`](../deploy/.env.example) for production. Required everywhere:

- `DATABASE_URL`
- `DASHBOARD_PIN`
- `SESSION_SECRET` (32+ chars, generated with `openssl rand -hex 32`)
- `INTERVALS_API_KEY` + `INTERVALS_ATHLETE_ID` (Week 2 sync onward)
