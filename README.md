# Instagram Appium Automation Platform

Runnable project for importing Instagram jobs, discovering real devices, validating strict device assignment, planning action steps, executing with Appium, and generating reports.

## What Is Implemented

- Excel import with batch tracking
- Auto Android device discovery from adb
- Device registry with online/offline status
- Strict rule: only jobs with assigned and online device_id can run
- Planning engine with mandatory data checks per action
- Action engine with mock mode and live Appium mode
- Streamlit UI for import, discover, validate, plan, run, and report
- CSV report generation and evidence capture

## Folder Structure

- app/db.py: SQLite schema and data access
- app/devices.py: auto device discovery and assignment validation
- app/importer.py: import jobs from Excel
- app/planner.py: step planning and mandatory field checks
- app/action_engine.py: action execution with Appium hooks
- app/runner.py: batch run orchestration
- app/reports.py: report export
- ui.py: Streamlit UI
- main.py: CLI run
- create_template.py: sample job sheet

## Job Columns

- account_id
- device_id
- post_url
- intent
- sentiment_tag
- comment_template
- priority
- description

## Supported Intents

- launch
- terminate
- post
- review
- scroll
- like
- comment
- repost
- share
- like_and_comment

## Mandatory Data by Action

- launch: device_id
- terminate: device_id
- post: device_id, post_url
- review: device_id, post_url
- scroll: device_id
- like: device_id, post_url
- comment: device_id, post_url, comment_template
- repost: device_id, post_url
- share: device_id, post_url
- like_and_comment: device_id, post_url, description

If mandatory data is missing, planner inserts a skip step and marks the reason.

## Architecture

1. Import Layer
- Upload Excel and store rows in jobs table.

2. Device Layer
- Discover devices from adb and update devices table.
- Mark missing devices as blocked and offline devices as waiting.

3. Validation Layer
- Validate each job against discovered device registry.
- Keep only valid assigned jobs in pending/planned states.

4. Planning Layer
- Build deterministic step plan by intent.
- Enforce mandatory data for every action.

5. Execution Layer
- Run per planned job through ActionEngine.
- Mock mode logs actions.
- Live mode creates Appium session per device and executes real calls.

6. Reporting Layer
- Export batch report to reports folder.
- Capture evidence into evidence folder.

## Planner Prompt Template

Use this prompt shape if you connect an LLM planner:

You are a mobile automation planner. Return strict JSON only.
Input job:
- action_type: <intent>
- device_id: <device_id>
- post_url: <post_url>
- description: <description>
- comment_template: <comment_template>
Constraints:
- enforce mandatory data for action_type
- if missing data, return one skip step with reason
- include capture_evidence after key action
- wait range 500 to 3000 ms
Output schema:
{
  "device_id": "...",
  "steps": [
    {
      "order": 1,
      "action": "launch|open_url|like|comment|repost|share|scroll|terminate|capture_evidence|skip",
      "value": "...",
      "min_wait_ms": 700,
      "max_wait_ms": 1800
    }
  ]
}

## Setup

1. Create and activate venv

PowerShell:

python -m venv venv
.\venv\Scripts\Activate.ps1

2. Install dependencies

pip install -r requirements.txt

3. Generate sample Excel

python create_template.py

## Run UI

streamlit run ui.py

UI flow:

1. Upload jobs_template.xlsx
2. Discover Devices
3. Validate Device Assignment
4. Plan Steps
5. Run Batch
6. Generate Report

## React UI (run_dev.py)

`run_dev.py` is the single-command launcher that starts both the FastAPI backend and the
React frontend together. Press **Ctrl+C** once to stop both processes cleanly.

---

### Prerequisites

Before running `run_dev.py`, ensure these tools are installed and available on your PATH.

| Tool | Minimum version | Install |
|------|----------------|---------|
| Python | 3.10+ | python.org |
| Node.js | 18+ | nodejs.org |
| npm | 9+ | Bundled with Node.js |
| Appium CLI (optional, live mode only) | 2.x | `npm i -g appium` |

Verify all tools are ready:

```
python --version
node --version
npm --version
uvicorn --version
```

---

### Step 1 — Create and activate virtual environment

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

On macOS / Linux:

```bash
python -m venv venv
source venv/bin/activate
```

---

### Step 2 — Install Python dependencies

```
pip install -r requirements.txt
```

This installs FastAPI, Uvicorn, python-multipart, Streamlit, openpyxl, pandas, and Appium client.

---

### Step 3 — Run the single launcher

```
python run_dev.py
```

What happens automatically:

1. Checks that `uvicorn` and `npm` are on PATH
2. If `web/node_modules` is missing, runs `npm install` inside `web/` automatically
3. Starts FastAPI on `http://127.0.0.1:8000`
4. Starts React (Vite) on `http://127.0.0.1:5173`
5. On Ctrl+C, sends a kill signal to both processes

---

### Step 4 — Open the browser

```
http://127.0.0.1:5173
```

The React app connects to the API at `http://127.0.0.1:8000` by default.

---

### Configuration

#### Change the API URL (React → FastAPI)

Create `web/.env` with:

```
VITE_API_URL=http://127.0.0.1:8000
```

Change the value if your API runs on a different host or port.

#### Change the FastAPI port

Edit `run_dev.py`, find the `python_cmd` list, and change `"8000"` to your preferred port.
Update `VITE_API_URL` in `web/.env` to match.

#### Change the React port

Edit `web/vite.config.js` and add a server block:

```js
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000   // change to any available port
  }
})
```

---

### Manual option (without run_dev.py)

Run each service in a separate terminal:

**Terminal 1 — API**

```
uvicorn api:app --reload --host 127.0.0.1 --port 8000
```

**Terminal 2 — React**

```
cd web
npm install
npm run dev
```

---

### Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| `npm not found` | Node.js not installed | Install from nodejs.org |
| `vite is not recognized` | `npm install` not run | `run_dev.py` runs it automatically; or run `cd web && npm install` manually |
| `uvicorn not found` | Python deps not installed | Run `pip install -r requirements.txt` in the venv |
| React shows blank page | API not reachable | Confirm API is running on port 8000; check `VITE_API_URL` in `web/.env` |
| Port already in use | Another process on 8000 or 5173 | Change port in `run_dev.py` and `vite.config.js` |
| FastAPI lingers after Ctrl+C | Windows process tree not killed | `taskkill /IM uvicorn.exe /F` |

---

### File Reference

| File | Purpose |
|------|---------|
| `run_dev.py` | Single-command launcher for API + React |
| `api.py` | FastAPI REST endpoints wrapping automation modules |
| `web/` | React (Vite) frontend source |
| `web/src/App.jsx` | Main UI component with tab layout |
| `web/src/api.js` | Fetch helpers for calling the FastAPI backend |
| `web/src/styles.css` | Global styles and responsive layout rules |
| `web/.env` | Optional env file to override `VITE_API_URL` |

## Run CLI

Mock run:

python main.py jobs_template.xlsx

Live Appium run:

python main.py jobs_template.xlsx --live --appium-server-url http://127.0.0.1:4723

## Appium and Device Requirements

- Appium server running
- Android devices connected and visible in adb devices -l
- Instagram installed on devices

## Outputs

- Database: data/automation.db
- Reports: reports/batch_<id>_report.csv
- Evidence: evidence/job_<id>_<timestamp>.png or txt in mock mode

## Compliance

Use only for authorized accounts and approved workflows, and comply with platform policies.
