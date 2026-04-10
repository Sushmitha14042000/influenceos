from __future__ import annotations

import os
import shutil
import subprocess
from datetime import datetime, timezone

from app.db import execute, fetch_all, fetch_one


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    if os.name == "nt":
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}"],
            capture_output=True,
            text=True,
            check=False,
        )
        return str(pid) in (result.stdout or "")
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def start_server_for_device(device_id: str, host: str = "127.0.0.1", port: int = 4723) -> dict[str, str | int]:
    existing = fetch_one("SELECT pid, status FROM appium_servers WHERE device_id = ?", [device_id])
    if existing and _is_pid_alive(existing["pid"]):
        return {
            "device_id": device_id,
            "host": host,
            "port": port,
            "pid": int(existing["pid"]),
            "status": "already_running",
        }

    # Resolve the appium executable; on Windows npm installs a .cmd wrapper
    appium_exe = shutil.which("appium") or shutil.which("appium.cmd")
    if appium_exe is None and os.name == "nt":
        # npm global bin may not be on PATH — derive it from `npm prefix -g`
        try:
            npm_prefix = subprocess.check_output(
                ["npm", "prefix", "-g"], text=True, stderr=subprocess.DEVNULL
            ).strip()
            candidate = os.path.join(npm_prefix, "appium.cmd")
            if os.path.isfile(candidate):
                appium_exe = candidate
        except Exception:
            pass
    if appium_exe is None:
        raise RuntimeError("Appium CLI not found. Install globally: npm i -g appium")

    cmd = [appium_exe, "--address", host, "--port", str(port)]
    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("Appium CLI not found. Install globally: npm i -g appium") from exc

    execute(
        """
        INSERT INTO appium_servers(device_id, host, port, pid, status, started_at, stopped_at)
        VALUES (?, ?, ?, ?, 'running', ?, NULL)
        ON CONFLICT(device_id) DO UPDATE SET
            host=excluded.host,
            port=excluded.port,
            pid=excluded.pid,
            status='running',
            started_at=excluded.started_at,
            stopped_at=NULL
        """,
        [device_id, host, port, proc.pid, _utc_now()],
    )

    execute(
        "UPDATE devices SET appium_server_url = ? WHERE device_id = ?",
        [f"http://{host}:{port}", device_id],
    )

    return {
        "device_id": device_id,
        "host": host,
        "port": port,
        "pid": proc.pid,
        "status": "started",
    }


def stop_server_for_device(device_id: str) -> dict[str, str]:
    row = fetch_one("SELECT pid FROM appium_servers WHERE device_id = ?", [device_id])
    if not row:
        return {"device_id": device_id, "status": "not_found"}

    pid = int(row["pid"]) if row["pid"] else None
    if pid and _is_pid_alive(pid):
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, text=True, check=False)
        else:
            try:
                os.kill(pid, 15)
            except OSError:
                pass

    execute(
        "UPDATE appium_servers SET status = 'stopped', stopped_at = ? WHERE device_id = ?",
        [_utc_now(), device_id],
    )
    return {"device_id": device_id, "status": "stopped"}


def list_servers() -> list[dict[str, str | int | bool | None]]:
    rows = fetch_all(
        "SELECT device_id, host, port, pid, status, started_at, stopped_at FROM appium_servers ORDER BY device_id"
    )
    output: list[dict[str, str | int | bool | None]] = []
    for row in rows:
        pid = int(row["pid"]) if row["pid"] else None
        output.append(
            {
                "device_id": row["device_id"],
                "host": row["host"],
                "port": row["port"],
                "pid": pid,
                "status": row["status"],
                "alive": _is_pid_alive(pid),
                "started_at": row["started_at"],
                "stopped_at": row["stopped_at"],
            }
        )
    return output
