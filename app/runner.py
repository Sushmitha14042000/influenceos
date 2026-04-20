from __future__ import annotations

from datetime import datetime, timezone

from app.action_engine import ActionEngine
from app.db import execute, fetch_all
from app.devices import get_device, validate_batch_device_assignments
from app.models import Status
from app.planner import plan_batch


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_batch(batch_id: int, use_mock: bool = False) -> dict:
    # Keep run order safe and deterministic even when called directly from API/UI.
    validate_batch_device_assignments(batch_id)
    plan_batch(batch_id)
    import threading
    from collections import defaultdict
    from concurrent.futures import ThreadPoolExecutor, as_completed

    jobs = fetch_all(
        """
        SELECT *
        FROM jobs
        WHERE batch_id = ?
                  AND status = 'planned'
          AND device_id IS NOT NULL
          AND TRIM(device_id) <> ''
        ORDER BY priority DESC, id ASC
        """,
        [batch_id],
    )

    # Group jobs by device_id
    jobs_by_device = defaultdict(list)
    for job in jobs:
        jobs_by_device[str(job["device_id"])].append(job)

    totals = {"total": len(jobs), "done": 0, "error": 0, "skipped": 0}
    lock = threading.Lock()

    def run_jobs_for_device(device_id, jobs):
        engine = ActionEngine(use_mock=use_mock)
        try:
            for job in jobs:
                job_id = int(job["id"])
                device = get_device(device_id)
                if not device or device["status"] != "online":
                    execute(
                        "UPDATE jobs SET status = ?, error_message = ? WHERE id = ?",
                        [Status.WAITING_DEVICE_ONLINE.value, f"device {device_id} offline/unavailable", job_id],
                    )
                    continue

                execute("UPDATE jobs SET status = ?, started_at = ? WHERE id = ?", [Status.RUNNING.value, _utc_now(), job_id])

                try:
                    steps = fetch_all("SELECT * FROM planned_steps WHERE job_id = ? ORDER BY step_order ASC", [job_id])
                    evidence_path = None
                    skipped_job = False

                    for step in steps:
                        action = str(step["action"])
                        value = step["value"]
                        if action == "skip":
                            skipped_job = True
                        result = engine.run_step(
                            job_id=job_id,
                            device_id=device_id,
                            appium_server_url=str(device["appium_server_url"]),
                            action=action,
                            value=value,
                            min_wait_ms=int(step["min_wait_ms"]),
                            max_wait_ms=int(step["max_wait_ms"]),
                        )
                        if result:
                            evidence_path = result

                    final_status = Status.SKIPPED if skipped_job else Status.DONE
                    execute(
                        "UPDATE jobs SET status = ?, finished_at = ?, evidence_path = ? WHERE id = ?",
                        [final_status.value, _utc_now(), evidence_path, job_id],
                    )
                    with lock:
                        totals[final_status.value] += 1
                except Exception as exc:
                    execute(
                        "UPDATE jobs SET status = ?, error_message = ?, finished_at = ? WHERE id = ?",
                        [Status.ERROR.value, str(exc), _utc_now(), job_id],
                    )
                    execute(
                        "INSERT INTO run_events(job_id, level, message, created_at) VALUES (?, ?, ?, ?)",
                        [job_id, "ERROR", str(exc), _utc_now()],
                    )
                    with lock:
                        totals["error"] += 1
        finally:
            engine.close()

    with ThreadPoolExecutor(max_workers=len(jobs_by_device)) as executor:
        futures = [executor.submit(run_jobs_for_device, device_id, jobs) for device_id, jobs in jobs_by_device.items()]
        for future in as_completed(futures):
            pass  # All exceptions are handled inside run_jobs_for_device

    return totals
