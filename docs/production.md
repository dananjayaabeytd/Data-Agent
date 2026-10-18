# Production Runbook

## Required secrets

Set these through a secret manager or deployment environment, not source control:

- `OPENAI_API_KEY`
- `JWT_SECRET` with at least 32 random characters
- `JWT_ISSUER` and `JWT_AUDIENCE`
- Database credentials for the application and read-only analytics role

Set `APP_ENV=production`, `SESSION_BACKEND=postgres`, and a narrow `ALLOWED_ORIGINS` list.
Set `ETL_ALLOWED_HOSTS` to explicit trusted API hostnames. Do not leave it empty in production.

## Database

The API applies `db/migrations/*.sql` at startup (`DB_MIGRATE_ON_STARTUP`, default `true`).
Migrations must be idempotent because every replica runs them on boot. Seed loading
(`DB_SEED_ON_STARTUP`) defaults to `false` in production and only loads into empty tables.
Add a new numbered file in `db/migrations/` for future schema changes.
The analytics role must have `CONNECT`, schema `USAGE`, and `SELECT` on business tables only.
It must not access `agent_sessions` or perform writes. In production the API refuses to start if
`db_readonly_user` is missing or equal to `user`. Set `DB_MANAGE_READONLY_ROLE=true` to let startup
create the role and apply exactly these grants (`db/bootstrap.py`), or create it yourself when the
application user cannot run `CREATE ROLE`.

## Deployment

Build and start the API only after secrets are configured:

```powershell
docker compose build api
docker compose up -d
```

Put an HTTPS reverse proxy in front of port 8000. Do not expose PostgreSQL publicly.
Production API documentation is disabled; expose it only through an authenticated internal route when needed.

## Operations

- Use `/health` for liveness and `/ready` for database readiness.
- Preserve `X-Request-ID` in centralized logs.
- Alert on 5xx rates, 429 rates, latency, database failures, and LLM spend.
- Back up PostgreSQL and test restores regularly.
- Set retention and deletion policies for session data.
- Rotate JWT/database/OpenAI secrets regularly.
- Scan the Docker image and dependencies in CI before release.