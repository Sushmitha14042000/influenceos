from __future__ import annotations

import argparse
import os

from app.db import init_db
from app.devices import sync_devices, validate_batch_device_assignments
from app.importer import import_excel
from app.planner import plan_batch
from app.reports import generate_batch_report
from app.runner import run_batch


def main() -> None:
    parser = argparse.ArgumentParser(description="Automation Platform CLI")
    parser.add_argument("excel_file", help="Input Excel file path")
    parser.add_argument("--live", action="store_true", help="Use live mode instead of mock mode")
    parser.add_argument(
        "--appium-server-url",
        default=os.getenv("APPIUM_SERVER_URL", "http://127.0.0.1:4723"),
        help="Appium server URL used for discovered devices",
    )
    args = parser.parse_args()

    init_db()
    device_stats = sync_devices(args.appium_server_url)
    batch_id = import_excel(args.excel_file)
    validation = validate_batch_device_assignments(batch_id)
    planned = plan_batch(batch_id)
    result = run_batch(batch_id, use_mock=(not args.live))
    report_path = generate_batch_report(batch_id)

    print(f"Device sync: {device_stats}")
    print(f"Batch ID: {batch_id}")
    print(f"Validation: {validation}")
    print(f"Planned jobs: {planned}")
    print(f"Run summary: {result}")
    print(f"Report: {report_path}")


if __name__ == "__main__":
    main()
