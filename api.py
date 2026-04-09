from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.appium_servers import list_servers, start_server_for_device, stop_server_for_device
from app.db import fetch_all, init_db
from app.devices import list_devices, sync_devices, validate_batch_device_assignments
from app.importer import import_excel
from app.planner import plan_batch
from app.reports import generate_batch_report
from app.runner import run_batch

app = FastAPI(title="Automation Platform API", version="1.0.0")

# Allow local React dev server to call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/batches")
def get_batches() -> list[dict[str, object]]:
    rows = fetch_all("SELECT id, source_file, created_at FROM import_batches ORDER BY id DESC")
    return [dict(r) for r in rows]


@app.post("/batches/import")
def import_batch(file: UploadFile = File(...)) -> dict[str, int]:
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="Only .xlsx files are supported")

    upload_dir = Path("data")
    upload_dir.mkdir(parents=True, exist_ok=True)
    out_file = upload_dir / "upload.xlsx"

    with out_file.open("wb") as handle:
        shutil.copyfileobj(file.file, handle)

    batch_id = import_excel(str(out_file))
    return {"batch_id": batch_id}


@app.post("/batches/{batch_id}/validate")
def validate_batch(batch_id: int) -> dict[str, int]:
    return validate_batch_device_assignments(batch_id)


@app.post("/batches/{batch_id}/plan")
def plan(batch_id: int) -> dict[str, int]:
    return {"planned": plan_batch(batch_id)}


@app.post("/batches/{batch_id}/run")
def run(batch_id: int, live_mode: bool = Form(False)) -> dict[str, int]:
    return run_batch(batch_id, use_mock=(not live_mode))


@app.post("/batches/{batch_id}/report")
def report(batch_id: int) -> dict[str, str]:
    path = generate_batch_report(batch_id)
    return {"report_path": path}


@app.get("/devices")
def get_devices() -> list[dict[str, str]]:
    return list_devices()


@app.post("/devices/sync")
def sync(server_host: str = Form("127.0.0.1"), base_port: int = Form(4723)) -> dict[str, int]:
    return sync_devices(f"http://{server_host}:{base_port}")


@app.get("/servers")
def get_servers() -> list[dict[str, object]]:
    return list_servers()


@app.post("/servers/start")
def start_server(
    device_id: str = Form(...),
    server_host: str = Form("127.0.0.1"),
    port: int = Form(4723),
) -> dict[str, object]:
    return start_server_for_device(device_id, host=server_host, port=port)


@app.post("/servers/stop")
def stop_server(device_id: str = Form(...)) -> dict[str, str]:
    return stop_server_for_device(device_id)


@app.get("/jobs")
def get_jobs(limit: int = 500) -> list[dict[str, object]]:
    rows = fetch_all(
        """
        SELECT j.id, j.batch_id, j.account_id, j.device_id, j.intent, j.status, j.priority,
               j.error_message, j.evidence_path, j.created_at
        FROM jobs j
        ORDER BY j.id DESC
        LIMIT ?
        """,
        [limit],
    )
    return [dict(r) for r in rows]


@app.get("/events")
def get_events(limit: int = 200) -> list[dict[str, object]]:
    rows = fetch_all(
        "SELECT e.id, e.job_id, e.level, e.message, e.created_at FROM run_events e ORDER BY e.id DESC LIMIT ?",
        [limit],
    )
    return [dict(r) for r in rows]
