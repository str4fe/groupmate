# groupmate

Open-source foundation for attendance and study-process management in university groups. The application uses FastAPI, SQLAlchemy 2 async, Alembic, and PostgreSQL; SQLite is available for local development.

## Requirements

- Python 3.12+ for local development, or Docker Compose
- PostgreSQL 16 for the containerized setup
- Node.js 22+ and npm for local Mini App builds (Docker builds the frontend automatically)

## Run with Docker Compose

1. Clone the repository and enter its directory.
2. Create local configuration and seed files:

   ```sh
   cp .env.example .env
   cp group_seed.example.json group_seed.json
   ```

3. Set a private `APP_SECRET_KEY`, a strong `POSTGRES_PASSWORD`, and your `BOT_TOKEN` in `.env`. Keep `.env` and `group_seed.json` private; both are ignored by Git. Adjust `DATABASE_URL` if you change the database credentials.
4. Replace the example subjects, students, Telegram IDs, and roles in `group_seed.json` with your own group data. Valid roles are `student`, `deputy`, and `headman`; subgroups are `1` or `2`.
5. Start the API and PostgreSQL:

   ```sh
   docker compose up --build -d
   ```

   The app waits for the database, applies migrations, and starts Uvicorn. Data is persisted in the `postgres_data` volume.
6. Copy the seed file into the app container, import group data, and check the database health:

   ```sh
   docker compose cp group_seed.json app:/app/group_seed.json
   docker compose exec app python -m app.cli.seed
   curl http://localhost:8000/api/v1/health
   ```

## Local development with SQLite

Create `.env`, set `DATABASE_URL=sqlite+aiosqlite:///./data/app.db`, then install and run:

```sh
python -m venv .venv
. .venv/bin/activate
pip install -e .
mkdir -p data
alembic upgrade head
python -m app.cli.seed group_seed.json
uvicorn app.main:app --reload
```

For PostgreSQL, use `DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@HOST:5432/DBNAME`. Alembic migrations are applied at container startup; locally use `alembic upgrade head` after starting your database.

## Telegram Mini App

The mobile UI is served at `/` from `frontend/dist` after a build. Run locally:

```sh
cd frontend
npm ci
npm run build
```

Then start/restart `uvicorn app.main:app --reload` from the project root and open `http://localhost:8000/`. Alternatively run `npm run dev` in `frontend/` for Vite at `http://localhost:5173/` (requests to `/api` are proxied to port 8000). Docker Compose builds the UI in a Node stage and includes it in the backend image. `/docs` and `/api/v1/*` remain served by FastAPI.

Inside Telegram the Mini App posts the WebApp `initData` to the backend and saves the resulting tokens in session storage. Outside Telegram it offers a development-only login by Telegram ID; it requires `DEBUG_AUTH=true` and a corresponding seeded user. Example IDs in the form must match your seed data. Do not enable `DEBUG_AUTH` in production. Configure the bot's `WEBAPP_URL` to the public HTTPS URL of this application; Telegram Mini Apps require HTTPS. For real JWT issuance, provide a private `APP_SECRET_KEY`.

Lesson times are optional: set `SCHEDULE_SLOT_TIMES` to a JSON mapping such as `{"1":["08:30","10:05"],"2":["10:20","11:55"]}`. When unspecified, the UI shows the lesson number instead of invented times. Lesson type is read from the schedule slot if available.

## Configuration

| Variable | Description | Default |
| --- | --- | --- |
| `BOT_TOKEN` | Optional Telegram bot token; configure only in private `.env` | empty |
| `DATABASE_URL` | Async SQLAlchemy database URL | SQLite local file |
| `TIMEZONE` | Application timezone | `UTC` |
| `APP_SECRET_KEY` | JWT signing secret; must be changed from placeholder | development placeholder |
| `APP_NAME` | FastAPI title | `University Attendance` |
| `DEBUG` | Enable SQL debug logging | `false` |
| `DEBUG_AUTH` | Enable development Telegram ID login (disable in production) | `false` |
| `SCHEDULE_SLOT_TIMES` | Optional JSON mapping of slot number to start/end time | `{}` |

`GET /api/v1/health` executes `SELECT 1` and returns HTTP 200 only when the database is reachable. Seed import is repeatable: existing subjects are matched by name and users by `telegram_id`, then updated.
