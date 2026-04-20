
from __future__ import annotations
import re

from app.db import execute, fetch_all
import json
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
        value = step[2]
        if isinstance(value, dict):
            value = json.dumps(value)
        execute(
            """
            INSERT INTO planned_steps(job_id, step_order, action, value, min_wait_ms, max_wait_ms)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [job_id, step[0], step[1], value, step[3], step[4]],
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





        # Custom workflow: open, scroll randomly, scroll reels, close, open, scroll, redirect, perform intent
        steps: list[tuple[int, str, str | None, int, int]] = [
            (1, "open_instagram", None, 700, 1800),
            (2, "scroll_randomly", "60", 1000, 2000),
            (3, "scroll_reels", "30", 1000, 2000),
            (4, "close_instagram", None, 700, 1800),
            (5, "open_instagram", None, 700, 1800),
            (6, "scroll_randomly", "30", 1000, 2000),
            (7, "redirect_url", post_url, 1200, 2600),
            (8, "wait", "post_load", 3000, 4000),
        ]

        main_action_idx = len(steps) + 1
        insights_idx = main_action_idx + 1
        profile_idx = insights_idx + 1
        wait_idx = profile_idx + 1
        scroll_idx = wait_idx + 1
        close_idx = scroll_idx + 1

        def add_profile_steps():
            steps.append((profile_idx, "view_profile", post_url, 1000, 2000))
            steps.append((wait_idx, "wait", "profile_load", 2000, 3000))
            steps.append((scroll_idx, "scroll_randomly", "30", 1000, 2000))
            steps.append((close_idx, "close_instagram", None, 700, 1800))

        def add_back_step(idx):
            steps.append((idx, "back", None, 200, 400))

        if intent == Intent.LIKE:
            steps.append((main_action_idx, "like", None, 900, 1800))
            add_back_step(main_action_idx + 0.1)
            steps.append((insights_idx, "capture_insights", "like", 300, 700))
            add_profile_steps()
        elif intent == Intent.COMMENT:
            steps.append((main_action_idx, "comment", {"url": post_url, "text": comment_template}, 1100, 2200))
            add_back_step(main_action_idx + 0.1)
            steps.append((insights_idx, "capture_insights", "comment", 300, 700))
            add_profile_steps()
        elif intent == Intent.REPOST:
            steps.append((main_action_idx, "repost", post_url, 1200, 2600))
            add_back_step(main_action_idx + 0.1)
            steps.append((insights_idx, "capture_insights", "repost", 300, 700))
            add_profile_steps()
        elif intent == Intent.SHARE:
            steps.append((main_action_idx, "share", None, 1200, 2600))
            add_back_step(main_action_idx + 0.1)
            steps.append((insights_idx, "capture_insights", "share", 300, 700))
            add_profile_steps()
        elif intent == Intent.LIKE_AND_COMMENT:
            steps.append((main_action_idx, "like", None, 900, 1800))
            add_back_step(main_action_idx + 0.1)
            steps.append((insights_idx, "comment", {"url": post_url, "text": comment_template}, 1100, 2200))
            add_back_step(insights_idx + 0.1)
            steps.append((scroll_idx, "capture_insights", "like_and_comment", 300, 700))
            add_profile_steps()
        elif intent == Intent.TERMINATE:
            steps = [(1, "terminate", None, 200, 600)]
        # Add evidence step for all except terminate
        if intent != Intent.TERMINATE:
            steps.append((199, "capture_evidence", None, 300, 700))

        _insert_steps(int(job["id"]), steps)
        execute("UPDATE jobs SET status = 'planned', error_message = NULL WHERE id = ?", [job["id"]])
        planned_count += 1

    return planned_count
