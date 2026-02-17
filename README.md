# SkillLens

SkillLens is an AI Skill Security & Intelligence Platform scaffolded from `AGENTS.md`.

This repository uses `AGENTS.md` as the source of truth for structure and modules, with path mapping:
- `backend/*` -> `server/*`
- `frontend/*` -> `client/*`

## Run with Docker

```bash
docker compose up --build
```

Open:
- Client: http://localhost:5173
- Server docs: http://localhost:8000/docs

## Database Migrations (Supabase)

Migrations are stored in `supabase/migrations/`.

### Option A: Supabase CLI

1. Link your project:
```bash
supabase link --project-ref <your-project-ref>
```

2. Push migrations:
```bash
supabase db push
```

### Option B: psql script

1. Export DB URL:
```bash
export SUPABASE_DB_URL='postgresql://postgres:<PASSWORD>@db.<PROJECT-REF>.supabase.co:5432/postgres?sslmode=require'
```

2. Apply all migrations:
```bash
./scripts/db_apply.sh
```

3. Apply a single migration:
```bash
./scripts/db_apply.sh supabase/migrations/20260216170000_init_skilllens.sql
```

Optional local check:
```bash
supabase start
supabase db reset
```

`database/schema.sql` mirrors the latest migration for SQL Editor convenience.
