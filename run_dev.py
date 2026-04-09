from __future__ import annotations

import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
WEB_DIR = ROOT_DIR / "web"


def _check_command(name: str) -> None:
    if shutil.which(name) is None:
        raise RuntimeError(f"Required command not found: {name}")


def _build_npm_cmd() -> list[str]:
    if sys.platform == "win32":
        return ["cmd", "/c", "npm", "run", "dev"]
    return ["npm", "run", "dev"]


def _terminate_process(proc: subprocess.Popen[bytes] | subprocess.Popen[str]) -> None:
    if proc.poll() is not None:
        return

    try:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                capture_output=True,
                text=True,
                check=False,
            )
            return
        proc.terminate()
        proc.wait(timeout=5)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def _ensure_web_dependencies() -> None:
    vite_cmd = WEB_DIR / "node_modules" / ".bin" / ("vite.cmd" if sys.platform == "win32" else "vite")
    if vite_cmd.exists():
        return

    print("Installing React dependencies (npm install)...")
    install_cmd = ["cmd", "/c", "npm", "install"] if sys.platform == "win32" else ["npm", "install"]
    result = subprocess.run(install_cmd, cwd=str(WEB_DIR), check=False)
    if result.returncode != 0:
        raise RuntimeError("npm install failed in ./web")


def main() -> int:
    _check_command("uvicorn")
    if sys.platform == "win32":
        _check_command("cmd")
        _check_command("npm.cmd")
    else:
        _check_command("npm")

    if not WEB_DIR.exists():
        raise RuntimeError("web folder not found. Expected React app in ./web")

    _ensure_web_dependencies()

    python_cmd = [
        "uvicorn",
        "api:app",
        "--reload",
        "--host",
        "127.0.0.1",
        "--port",
        "8000",
    ]

    npm_cmd = _build_npm_cmd()

    print("Starting FastAPI on http://127.0.0.1:8000")
    api_proc = subprocess.Popen(python_cmd, cwd=str(ROOT_DIR))

    print("Starting React on http://127.0.0.1:5173")
    try:
        web_proc = subprocess.Popen(npm_cmd, cwd=str(WEB_DIR))
    except Exception:
        _terminate_process(api_proc)
        raise

    children = [api_proc, web_proc]

    def _shutdown(*_: object) -> None:
        print("\nShutting down services...")
        for child in children:
            _terminate_process(child)
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    try:
        while True:
            if api_proc.poll() is not None:
                print("FastAPI process stopped. Stopping React process.")
                _terminate_process(web_proc)
                return api_proc.returncode or 0

            if web_proc.poll() is not None:
                print("React process stopped. Stopping FastAPI process.")
                _terminate_process(api_proc)
                return web_proc.returncode or 0

            time.sleep(0.5)
    except KeyboardInterrupt:
        _shutdown()

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"Error: {exc}")
        raise SystemExit(1)
