from __future__ import annotations

from app.db import execute, fetch_all
from app.models import Intent


MANDATORY_FIELDS: dict[str, list[str]] = {
    "launch": ["device_id"],
    "terminate": ["device_id"],
    "post": ["device_id", "post_url"],
    "scroll": ["device_id"],
    "like": ["device_id", "post_url"],
    "comment": ["device_id", "post_url", "comment_template"],
    "repost": ["device_id", "post_url"],
    "share": ["device_id", "post_url"],
    "review": ["device_id", "post_url"],
    "like_and_comment": ["device_id", "post_url", "description"],
}


def _insert_steps(job_id: int, steps: list[tuple[int, str, str | None, int, int]]) -> None:
    execute("DELETE FROM planned_steps WHERE job_id = ?", [job_id])
    for step in steps:
        execute(
            """
            INSERT INTO planned_steps(job_id, step_order, action, value, min_wait_ms, max_wait_ms)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [job_id, step[0], step[1], step[2], step[3], step[4]],
        )


def plan_batch(batch_id: int) -> int:
    jobs = fetch_all(
        "SELECT * FROM jobs WHERE batch_id = ? AND status IN ('pending', 'planned') ORDER BY priority DESC, id ASC",
        [batch_id],
    )
    planned_count = 0

    for job in jobs:
        intent = Intent(job["intent"])
        device_id = str(job["device_id"] or "").strip()
        post_url = job["post_url"]
        comment_template = job["comment_template"]
        description = job["description"]

        missing_fields: list[str] = []
        for field in MANDATORY_FIELDS[intent.value]:
            if field == "device_id" and not device_id:
                missing_fields.append(field)
            elif field == "post_url" and not post_url:
                missing_fields.append(field)
            elif field == "comment_template" and not comment_template:
                missing_fields.append(field)
            elif field == "description" and not description:
                missing_fields.append(field)

        if missing_fields:
            _insert_steps(
                int(job["id"]),
                [(1, "skip", f"mandatory data missing: {', '.join(missing_fields)}", 100, 300)],
            )
            execute(
                "UPDATE jobs SET status = 'planned', error_message = ? WHERE id = ?",
                [f"mandatory data missing: {', '.join(missing_fields)}", job["id"]],
            )
            planned_count += 1
            continue

        steps: list[tuple[int, str, str | None, int, int]] = [
            (1, "launch", None, 700, 1800),
            (2, "open_url", post_url, 1200, 2600),
        ]

        if intent == Intent.REVIEW:
            steps.extend([
                (3, "scroll", "2", 600, 1400),
                (4, "capture_evidence", None, 300, 700),
            ])
        elif intent == Intent.LAUNCH:
            pass
        elif intent == Intent.TERMINATE:
            steps = [(1, "terminate", None, 200, 600)]
        elif intent == Intent.POST:
            steps.append((3, "capture_evidence", None, 300, 700))
        elif intent == Intent.SCROLL:
            steps.append((3, "scroll", "4", 900, 1800))
            steps.append((4, "capture_evidence", None, 300, 700))
        elif intent == Intent.LIKE:
            steps.append((3, "like", None, 900, 1800))
            steps.append((4, "capture_evidence", None, 300, 700))
        elif intent == Intent.COMMENT:
            steps.append((3, "like", None, 900, 1800))
            steps.append((4, "comment", comment_template, 1100, 2200))
            steps.append((5, "capture_evidence", None, 300, 700))
        elif intent == Intent.REPOST:
            steps.append((3, "repost", None, 1200, 2600))
            steps.append((4, "capture_evidence", None, 300, 700))
        elif intent == Intent.SHARE:
            steps.append((3, "share", None, 1200, 2600))
            steps.append((4, "capture_evidence", None, 300, 700))
        elif intent == Intent.LIKE_AND_COMMENT:
            steps.append((3, "like", None, 900, 1800))
            ai_comment = f"Thanks for sharing this: {description[:90]}"
            steps.append((4, "comment", ai_comment, 1100, 2200))
            steps.append((5, "capture_evidence", None, 300, 700))

        _insert_steps(int(job["id"]), steps)
        execute("UPDATE jobs SET status = 'planned', error_message = NULL WHERE id = ?", [job["id"]])
        planned_count += 1

    return planned_count
