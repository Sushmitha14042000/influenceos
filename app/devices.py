from __future__ import annotations

import os
import subprocess
from datetime import datetime, timezone

from app.db import execute, fetch_all, fetch_one
from app.models import Status


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_cmd(args: list[str]) -> str:
    try:
        result = subprocess.run(args, capture_output=True, text=True, check=False)
        return (result.stdout or "").strip()
    except OSError:
        return ""


def discover_android_devices() -> list[dict[str, str]]:
    output = _run_cmd(["adb", "devices", "-l"])
    devices: list[dict[str, str]] = []
    if not output:
        return devices

    for line in output.splitlines():
        line = line.strip()
        if not line or line.startswith("List of devices"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        udid = parts[0]
        state = parts[1]
        if state != "device":
            continue

        model = ""
        for token in parts:
            if token.startswith("model:"):
                model = token.split(":", 1)[1]
                break

        os_version = _run_cmd(["adb", "-s", udid, "shell", "getprop", "ro.build.version.release"])
        devices.append(
            {
                "device_id": udid,
                "platform": "android",
                "model": model,
                "os_version": os_version,
            }
        )
    return devices


def sync_devices(appium_server_url: str | None = None) -> dict[str, int]:
    server_url = appium_server_url or os.getenv("APPIUM_SERVER_URL", "http://127.0.0.1:4723")
    now = _utc_now()

    discovered = discover_android_devices()
    discovered_ids = {d["device_id"] for d in discovered}

    existing = fetch_all("SELECT device_id FROM devices")
    existing_ids = {str(r["device_id"]) for r in existing}

    for device in discovered:
        execute(
            """
            INSERT INTO devices(device_id, platform, model, os_version, appium_server_url, status, last_seen_at)
            VALUES (?, ?, ?, ?, ?, 'online', ?)
            ON CONFLICT(device_id) DO UPDATE SET
                platform=excluded.platform,
                model=excluded.model,
                os_version=excluded.os_version,
                appium_server_url=excluded.appium_server_url,
                status='online',
                last_seen_at=excluded.last_seen_at
            """,
            [
                device["device_id"],
                device["platform"],
                device["model"],
                device["os_version"],
                server_url,
                now,
            ],
        )

    offline_ids = existing_ids - discovered_ids
    for device_id in offline_ids:
        execute(
            "UPDATE devices SET status = 'offline', last_seen_at = ? WHERE device_id = ?",
            [now, device_id],
        )

    return {
        "online": len(discovered_ids),
        "offline": len(offline_ids),
        "total": len(existing_ids | discovered_ids),
    }


def list_devices() -> list[dict[str, str]]:
    rows = fetch_all(
        "SELECT device_id, platform, model, os_version, appium_server_url, status, last_seen_at FROM devices ORDER BY device_id"
    )
    return [dict(r) for r in rows]


def get_device(device_id: str) -> dict[str, str] | None:
    row = fetch_one(
        "SELECT device_id, appium_server_url, status FROM devices WHERE device_id = ?",
        [device_id],
    )
    return dict(row) if row else None


def validate_batch_device_assignments(batch_id: int) -> dict[str, int]:
    rows = fetch_all("SELECT id, device_id FROM jobs WHERE batch_id = ?", [batch_id])
    out = {"ready": 0, "blocked_no_device": 0, "blocked_unknown_device": 0, "waiting_device_online": 0}

    for row in rows:
        job_id = int(row["id"])
        device_id = str(row["device_id"] or "").strip()

        if not device_id:
            execute("UPDATE jobs SET status = ?, error_message = ? WHERE id = ?", [Status.BLOCKED_NO_DEVICE.value, "device_id missing", job_id])
            out["blocked_no_device"] += 1
            continue

        device = get_device(device_id)
        if not device:
            execute(
                "UPDATE jobs SET status = ?, error_message = ? WHERE id = ?",
                [Status.BLOCKED_UNKNOWN_DEVICE.value, f"device_id '{device_id}' not found in discovered registry", job_id],
            )
            out["blocked_unknown_device"] += 1
            continue

        if device["status"] != "online":
            execute(
                "UPDATE jobs SET status = ?, error_message = ? WHERE id = ?",
                [Status.WAITING_DEVICE_ONLINE.value, f"device_id '{device_id}' is offline", job_id],
            )
            out["waiting_device_online"] += 1
            continue

        execute("UPDATE jobs SET status = ?, error_message = NULL WHERE id = ?", [Status.PENDING.value, job_id])
        out["ready"] += 1

    return out
