# ATOS Architecture Audit

Sprint: Studio Sprint 01
Audit date: 2026-07-12

## Repository

- ATOS repository path: `/Users/zhangkaikai/Documents/INDEX/ATOS`
- Branch: `release/v1.0.0`
- Commit: `4c2277ff048aac94838960ec73ebc191f59e4ce1`
- Working tree at audit time: clean
- ATOS-Studio repository path: `/Users/zhangkaikai/Documents/INDEX/ATOS-Studio`

## Technology Stack

| Area | Current ATOS implementation |
| --- | --- |
| Frontend framework | React 18, TypeScript, Vite 6, React Router, Axios, Tailwind CSS, lucide-react |
| Backend framework | FastAPI |
| Python version | Dockerfile uses `python:3.12-slim`; local system Python observed as 3.9.6 |
| API framework | FastAPI routers under `backend/app/api` |
| Database type | Local default SQLite; Docker compose uses PostgreSQL 16 |
| ORM / data access | SQLAlchemy 2.0 declarative models, session dependency, repository base class |
| Migrations | Alembic under `backend/alembic` |
| Dashboard framework | React single-page console in `frontend/src/App.tsx` |
| Background queue | Database-backed scheduler/execution queues through `scheduler_tasks`, `execution_queue`, `task_locks`; Redis is configured and health-checked but no Celery/RQ usage was found |
| Configuration | Pydantic Settings in `backend/app/config.py`; `.env`, `.env.local`, and environment-specific examples |
| Logging | `backend/app/logging_config.py` plus request trace middleware in `backend/app/middleware.py`; JSON log settings in env |
| Test framework | Python `unittest` in `backend/tests`; frontend TypeScript build/lint |
| Backend start command | `cd backend && ../.venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000` |
| Frontend start command | `cd frontend && pnpm dev` |
| Current ports | Backend 8000 in Docker/Makefile; frontend 5173; pgAdmin 5050; PostgreSQL 5432; Redis 6379. `MAIN_PORT=8080` exists for remote-worker/public settings. |
| Docker usage | Root `docker-compose.yml`, `docker-compose.prod.yml`, backend Dockerfile, frontend Dockerfile |
| Redis usage | Redis service in compose and `REDIS_URL`; health endpoint checks socket connectivity. No Celery/RQ worker code found. |

## Directory Structure

Important ATOS directories:

- `backend/app`: FastAPI app, config, models, API routers, services, serializers, middleware
- `backend/app/api`: route modules for health, dashboard, posts, pipeline, AI runtime, scheduler, automation, settings, GPU worker, accounts, etc.
- `backend/app/services`: business/runtime services
- `backend/alembic`: Alembic migration environment and versions
- `backend/tests`: backend unittest suite
- `frontend/src`: React/Vite console
- `workers/gpu`: independent GPU worker loop
- `infra`: nginx, monitoring, redis, logrotate configs
- `scripts`: migration, seed, smoke, backup scripts
- `docs`: architecture, deployment, sprint, release, and runtime documents

## Database

Current database configuration:

- `backend/app/config.py` default: `sqlite:///{BACKEND_DIR / 'atos.db'}`
- `.env.example` default: `DATABASE_URL=sqlite:///atos.db`
- `docker-compose.yml`: `postgresql+psycopg://...@postgres:5432/atos`
- Migration command: `python scripts/migrate.py`, which runs `alembic upgrade head`
- Table structure is managed by SQLAlchemy models in `backend/app/models.py` and Alembic migrations in `backend/alembic/versions`

Observed tables/classes include:

- Core source data: `platforms`, `platform_registry`, `data_sources`, `posts`, `post_timelines`, `crawl_logs`, `actor_mappings`
- AI/reply flow: `ai_tasks`, `ai_analysis_results`, `llm_providers`, `provider_routing`, `prompt_templates`, `prompt_versions`, `ai_generation_logs`, `replies`, `reply_tasks`, `reply_templates`
- Queue/runtime: `scheduler_tasks`, `scheduler_logs`, `execution_tasks`, `execution_queue`, `task_locks`, `worker_nodes`, `worker_logs`, `gpu_worker_statuses`, `gpu_generation_tasks`
- Browser/submission: `browser_sessions`, `browser_tabs`, `submission_tasks`, `submission_logs`, `replay_files`, `replay_indexes`
- Configuration/statistics: `system_settings`, `statistics_snapshots`, `runtime_metrics`, `system_alerts`, `filter_presets`, performance tables
- Account assets: `accounts`, `account_limits`, `account_working_windows`, `tge_profiles`

Specific table checks:

- User table: not found. No `users`/`User` model was identified.
- Posts table: found as `posts`.
- Comments table: not found as a separate comment table. Reply-related tables exist.
- Tasks tables: found, including `ai_tasks`, `reply_tasks`, `scheduler_tasks`, `execution_tasks`, `submission_tasks`, `gpu_generation_tasks`.
- Config table: found as `system_settings`; environment configuration also uses Pydantic Settings and `.env`.

Studio database recommendation:

- Do not modify ATOS production/core tables in Sprint 01.
- Studio should own its future tables with a `studio_` prefix.
- ATOS core source data should be read through a stable API contract rather than direct writes to ATOS tables.

## Authentication And Login

Observed facts:

- No formal end-user login route such as `/login`, `/auth/login`, or `/logout` was found in the backend route modules.
- No `users` table/model was found.
- The frontend API client reads `atos.token` from `window.localStorage` and sends `Authorization: Bearer ...` when present.
- Backend worker-style authentication exists:
  - GPU worker endpoints use bearer token validation through `require_gpu_worker_bearer`.
  - Remote worker endpoints use `X-Worker-Token` through `require_worker_token`.
- Production security settings include `ADMIN_DEFAULT_PASSWORD_CHANGED`, `COOKIE_SECURE`, and worker-token checks.

Conclusion:

- Current formal user login/session/JWT system: not confirmed.
- Login state storage for human users: not confirmed.
- Studio cannot claim shared login is implemented.
- Future Studio API authentication should be designed explicitly instead of assuming reuse.

## Existing API Surface

ATOS exposes many FastAPI routers. Confirmed route families include:

- Health and readiness: `/health`, `/health/backend`, `/health/database`, `/health/redis`, `/ready`, `/live`, `/metrics`
- Dashboard: `/dashboard/summary`
- Source/content: `/data-sources`, `/posts`, `/pipeline`
- AI: `/ai`, `/ai-runtime`, `/prompt-templates`, `/prompt-versions`
- Reply and scheduling: `/reply-tasks`, `/reply-templates`, `/scheduler`
- Execution/browser/automation: `/execution`, `/browser`, `/automation`
- Accounts and TGE: `/accounts`, `/tge-profiles`
- Settings/statistics/help: `/settings`, `/statistics`, `/help`
- GPU worker: `/api/gpu-worker`

There is no existing `/api/studio/*` API in ATOS.

## Reusable Modules

The following patterns are reusable for Studio:

- FastAPI app/routers/services organization
- Pydantic Settings configuration style
- SQLAlchemy model/repository conventions
- Health endpoint pattern
- Unified local-development defaults
- JSON logging and trace ID idea
- Alembic migration model for future `studio_` tables

## Potential Conflicts

- Directly sharing the ATOS database would couple Studio to ATOS migrations and table semantics.
- Direct writes to `posts`, `ai_tasks`, `execution_queue`, or other ATOS core tables could break ATOS lifecycle assumptions.
- Authentication is not yet a stable shared boundary.
- ATOS supports SQLite locally and PostgreSQL in Docker; Studio must avoid assuming one database mode.
- The frontend currently sends a bearer token if one exists, but backend human auth is not verified.

## Recommended Integration Mode

Recommendation: B, Studio reads ATOS data through ATOS internal APIs.

Rationale:

- Keeps ATOS and Studio independently deployable.
- Avoids two repositories writing the same ATOS core tables.
- Allows Studio to become independently sellable.
- Gives ATOS ownership of data collection, normalization, scoring, and reply operations.
- Keeps Studio free to own `studio_` tables for content pools, projects, assets, generation jobs, output records, and backup records.
- Current development complexity remains moderate because Studio Sprint 01 only defines the contract and can start with configured ATOS URLs.

Future exception:

- A mixed mode can be considered later if Studio needs local `studio_` tables in the same PostgreSQL instance for operational simplicity. Even in that case, Studio should not mutate ATOS core tables directly.

## Unconfirmed Items

- Whether production currently runs SQLite or PostgreSQL in the user's live deployment.
- Whether a hidden or planned human login system exists outside the inspected code.
- Exact deployment port mapping in production outside the local Docker/Makefile configuration.
- Whether Redis is used beyond health/runtime scaffolding in production.
- Whether current `.env.production` contains live credentials; it was not opened to avoid exposing secrets.

