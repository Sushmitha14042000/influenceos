from __future__ import annotations

from pathlib import Path

from app.db import fetch_all


def generate_batch_report(batch_id: int) -> str:
    rows = fetch_all(
        """
        SELECT j.id, j.account_id, j.device_id, j.intent, j.status, j.error_message,
               j.evidence_path, j.started_at, j.finished_at
        FROM jobs j
        WHERE j.batch_id = ?
        ORDER BY j.id ASC
        """,
        [batch_id],
    )

    report_dir = Path("reports")
    report_dir.mkdir(parents=True, exist_ok=True)
    out_file = report_dir / f"batch_{batch_id}_report.csv"

    header = "job_id,account_id,device_id,intent,status,error_message,evidence_path,started_at,finished_at\n"
    lines = [header]

    for row in rows:
        fields = [
            str(row["id"]),
            str(row["account_id"]),
            str(row["device_id"]),
            str(row["intent"]),
            str(row["status"]),
            str(row["error_message"] or ""),
            str(row["evidence_path"] or ""),
            str(row["started_at"] or ""),
            str(row["finished_at"] or ""),
        ]
        escaped = ['"' + f.replace('"', '""') + '"' for f in fields]
        lines.append(",".join(escaped) + "\n")

    out_file.write_text("".join(lines), encoding="utf-8")
    return str(out_file)
