# Automation Platform — Copilot Instructions

This is a Python + React automation platform for executing Instagram workflows on Android
devices via Appium. The project has a FastAPI REST backend, a React (Vite) frontend, a
Streamlit legacy UI, and a CLI entry point.

---

## Stack and Entry Points

| Layer | File / Folder | Purpose |
|-------|--------------|---------|
| FastAPI REST API | `api.py` | All endpoints for React frontend |
| React UI | `web/src/App.jsx` | Tab-based frontend consuming `api.py` |
| Streamlit UI | `ui.py` | Legacy UI, kept intact, runs via `streamlit run ui.py` |
| CLI | `main.py` | Argparse CLI for headless batch execution |
| Dev launcher | `run_dev.py` | Starts FastAPI + React together with one command |
| Database | `data/automation.db` | SQLite; schema owns in `app/db.py` |

---

## Python Module Map (`app/`)

| Module | Responsibility |
|--------|---------------|
| `db.py` | `init_db()`, `execute()`, `fetch_all()`, `fetch_one()`, `execute_many()` — all raw SQLite access |
| `models.py` | `Intent` enum, `Status` enum, `JobInput` dataclass, `PlannedStep` dataclass |
| `devices.py` | `sync_devices()` via adb, `list_devices()`, `validate_batch_device_assignments()` |
| `importer.py` | `import_excel(file_path)` — reads xlsx, creates import_batch row, inserts jobs |
| `planner.py` | `plan_batch(batch_id)` — deterministic step planner per Intent; inserts into planned_steps |
| `runner.py` | `run_batch(batch_id, use_mock)` — loops planned jobs, calls ActionEngine per step |
| `action_engine.py` | `ActionEngine` class — mock mode + live Appium mode; writes run_events |
| `appium_servers.py` | `start_server_for_device()`, `stop_server_for_device()`, `list_servers()` |
| `reports.py` | `generate_batch_report(batch_id)` — writes CSV to `reports/` |

---

## Database Schema (SQLite)

Tables and their key columns:

- **import_batches**: `id`, `source_file`, `created_at`
- **devices**: `device_id` (UNIQUE), `platform`, `model`, `os_version`, `appium_server_url`, `status`, `last_seen_at`
- **appium_servers**: `device_id` (UNIQUE FK), `host`, `port`, `pid`, `status`, `started_at`, `stopped_at`
- **jobs**: `id`, `batch_id` (FK), `account_id`, `device_id`, `post_url`, `intent`, `sentiment_tag`, `comment_template`, `priority`, `description`, `status`, `error_message`, `evidence_path`, `created_at`, `started_at`, `finished_at`
- **planned_steps**: `id`, `job_id` (FK), `step_order`, `action`, `value`, `min_wait_ms`, `max_wait_ms`
- **run_events**: `id`, `job_id` (FK), `level`, `message`, `created_at`

---

## Intent and Status Enums

**Intent values** (maps to job `intent` column):
`launch`, `terminate`, `post`, `review`, `scroll`, `like`, `comment`, `repost`, `share`, `like_and_comment`

**Status values** (maps to job `status` column):
`pending`, `planned`, `waiting_device_online`, `blocked_no_device`, `blocked_unknown_device`, `running`, `done`, `error`, `skipped`

---

## Mandatory Fields per Intent

The planner enforces these before generating steps.
If a field is missing, a single `skip` step is inserted and the job is marked accordingly.

| Intent | Required Fields |
|--------|----------------|
| `launch`, `terminate`, `scroll` | `device_id` |
| `post`, `review`, `like`, `repost`, `share` | `device_id`, `post_url` |
| `comment` | `device_id`, `post_url`, `comment_template` |
| `like_and_comment` | `device_id`, `post_url`, `description` |

---

## Action Engine

`ActionEngine` in `app/action_engine.py` handles step execution.

- **Mock mode** (`use_mock=True`): logs actions to `run_events`, writes `.txt` placeholder evidence.
- **Live mode** (`use_mock=False`): creates one Appium `webdriver.Remote` session per `device_id`, reuses it across steps, closes all sessions in `engine.close()`.
- Supported actions: `launch`, `terminate`, `open_url`, `scroll`, `like`, `comment`, `repost`, `share`, `skip`, `capture_evidence`
- Evidence saved to `evidence/job_{id}_{timestamp}.png` (live) or `.txt` (mock)
- All step events written to `run_events` via `db.execute()`

---

## FastAPI API (`api.py`)

Base URL: `http://127.0.0.1:8000`

CORS is open to `http://localhost:5173` and `http://127.0.0.1:5173` for local React dev.

Key endpoints:

| Method | Path | Description |
|--------|------|-------------|
| GET | `/batches` | List all import batches |
| POST | `/batches/import` | Upload xlsx, create batch |
| POST | `/batches/{id}/validate` | Validate device assignments |
| POST | `/batches/{id}/plan` | Plan steps for batch |
| POST | `/batches/{id}/run` | Run batch (`live_mode` form field) |
| POST | `/batches/{id}/report` | Generate CSV report |
| GET | `/devices` | List all discovered devices |
| POST | `/devices/sync` | Sync devices from adb |
| GET | `/servers` | List managed Appium servers |
| POST | `/servers/start` | Start server for device |
| POST | `/servers/stop` | Stop server for device |
| GET | `/jobs` | List jobs (latest 500) |
| GET | `/events` | List run events (latest 200) |

Form-encoded bodies use `python-multipart`. File upload uses `UploadFile`.

---

## React Frontend (`web/`)

- Framework: React 18 + Vite 5
- No external component library — plain CSS in `web/src/styles.css`
- API helper: `web/src/api.js` — `get(path)`, `postForm(path, fields)`, `postFile(path, file)`
- API base URL: `import.meta.env.VITE_API_URL` (defaults to `http://127.0.0.1:8000`)
- Set custom URL in `web/.env`: `VITE_API_URL=http://...`

UI structure (tabs):
1. **Import** — upload xlsx, create batch
2. **Batch Workflow** — select batch, validate / plan / run / report
3. **Devices & Servers** — sync devices, start/stop Appium servers
4. **Monitoring** — sub-tabs: Jobs, Run Events, Servers; job search filter; auto-refresh every 7 s

---

## Development Commands

```powershell
# activate venv
.\venv\Scripts\Activate.ps1

# install all Python deps
pip install -r requirements.txt

# start API + React together (auto-installs npm deps if missing)
python run_dev.py

# start legacy Streamlit UI
streamlit run ui.py

# CLI mock run
python main.py jobs_template.xlsx

# CLI live Appium run
python main.py jobs_template.xlsx --live --appium-server-url http://127.0.0.1:4723

# generate sample Excel template
python create_template.py
```

---

## Coding Conventions

- All Python modules use `from __future__ import annotations`
- DB access goes through `app/db.py` helpers only — never open `sqlite3` connections elsewhere
- All timestamps use `datetime.now(timezone.utc).isoformat()`
- Status and Intent values always use the enum (`Status.DONE.value`, not raw strings)
- ActionEngine receives `appium_server_url` per step — it does not read from DB directly
- Mock mode is the default; live mode must be explicitly opted into
- Evidence files land in `evidence/`, reports in `reports/`, DB in `data/`
- React components stay in `web/src/`; no TypeScript — plain `.jsx` and `.js`
- CSS uses CSS custom properties defined in `:root` block at top of `styles.css`

---

## Key Constraints

- A job can only run if its `device_id` exists in the `devices` table AND has `status = 'online'`
- `validate_batch_device_assignments()` must be called before `plan_batch()` in the correct order
- `run_batch()` calls `validate_batch_device_assignments()` internally as a safety check
- The planner deletes existing planned_steps for a job before replanning
- `ActionEngine.close()` must be called after `run_batch()` to release Appium sessions
- `run_dev.py` uses `taskkill /T /F` on Windows to kill process trees on Ctrl+C
