from __future__ import annotations

import json
import random
import time
from datetime import datetime, timezone
from typing import Any

from app.db import execute, fetch_all, fetch_one


def _last_id(table: str) -> int:
    row = fetch_one(f"SELECT id FROM {table} ORDER BY id DESC LIMIT 1")  # noqa: S608
    if not row:
        raise RuntimeError(f"Failed to obtain last id from {table}")
    return int(row["id"])


# ---------------------------------------------------------------------------
# Campaign creation
# ---------------------------------------------------------------------------

def create_campaign(
    name: str,
    target_url: str,
    accounts: list[dict[str, str]],
    wave_count: int = 3,
    wave_gap_seconds: int = 600,
    action_mix: dict[str, int] | None = None,
    comment_bank: list[str] | None = None,
) -> int:
    """Create a virality campaign and distribute accounts into waves.

    Args:
        name: Human-readable campaign label.
        target_url: Instagram post / reel URL to target.
        accounts: List of {account_id, device_id} dicts.
        wave_count: How many waves to split execution into.
        wave_gap_seconds: Pause between waves (mimics natural traffic pattern).
        action_mix: Percentage breakdown, e.g. {"like": 60, "comment": 20, "save": 15, "share": 5}.
        comment_bank: Pool of comment strings; one is picked randomly per comment assignment.
    """
    if action_mix is None:
        action_mix = {"like": 60, "comment": 20, "save": 15, "share": 5}
    if comment_bank is None:
        comment_bank = [
            "Amazing! 🔥", "Love this! ❤️", "This is incredible!",
            "So good!", "Absolutely stunning!", "Can't stop watching this!",
            "This deserves more attention!", "Saved for later 🙌",
        ]

    now = datetime.now(timezone.utc).isoformat()

    execute(
        """
        INSERT INTO virality_campaigns
            (name, target_url, total_accounts, wave_count, wave_gap_seconds,
             action_mix, comment_bank, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'draft', ?)
        """,
        [
            name, target_url, len(accounts), wave_count, wave_gap_seconds,
            json.dumps(action_mix), json.dumps(comment_bank), now,
        ],
    )
    campaign_id = _last_id("virality_campaigns")

    # Build a shuffled action list proportional to the mix percentages
    actions = _build_action_list(action_mix, len(accounts))
    random.shuffle(accounts)

    # Split accounts round-robin across waves
    waves: list[list[dict[str, str]]] = [[] for _ in range(wave_count)]
    for idx, account in enumerate(accounts):
        waves[idx % wave_count].append(account)

    action_cursor = 0
    for wave_num, wave_accounts in enumerate(waves, 1):
        for account in wave_accounts:
            action = actions[action_cursor % len(actions)]
            action_cursor += 1
            comment_text = random.choice(comment_bank) if action in ("comment", "like_and_comment") else None
            execute(
                """
                INSERT INTO campaign_waves
                    (campaign_id, wave_number, device_id, account_id, action, comment_text, status)
                VALUES (?, ?, ?, ?, ?, ?, 'pending')
                """,
                [campaign_id, wave_num, account["device_id"], account["account_id"], action, comment_text],
            )

    return campaign_id


def _build_action_list(action_mix: dict[str, int], total: int) -> list[str]:
    """Return a list of action strings sized to 'total', honouring % weights."""
    pool: list[str] = []
    for action, pct in action_mix.items():
        count = max(1, round(total * pct / 100))
        pool.extend([action] * count)
    # Trim or pad to exactly 'total' entries
    while len(pool) < total:
        pool.append(max(action_mix, key=lambda a: action_mix[a]))  # pad with dominant action
    random.shuffle(pool)
    return pool[:total]


# ---------------------------------------------------------------------------
# Campaign execution
# ---------------------------------------------------------------------------

def launch_campaign(campaign_id: int, use_mock: bool = True) -> dict[str, Any]:
    """Execute a virality campaign wave by wave.

    Each wave creates a temporary import_batch, plans it, and runs it.
    Gaps between waves simulate organic activity patterns.
    """
    from app.planner import plan_batch
    from app.runner import run_batch

    campaign = fetch_one("SELECT * FROM virality_campaigns WHERE id = ?", [campaign_id])
    if not campaign:
        raise ValueError(f"Campaign {campaign_id} not found")

    campaign = dict(campaign)
    wave_count: int = campaign["wave_count"]
    wave_gap: int = campaign["wave_gap_seconds"]
    target_url: str = campaign["target_url"]

    now = datetime.now(timezone.utc).isoformat()
    execute(
        "UPDATE virality_campaigns SET status='running', started_at=? WHERE id=?",
        [now, campaign_id],
    )

    total_done = 0
    total_error = 0

    for wave_num in range(1, wave_count + 1):
        assignments = fetch_all(
            """
            SELECT * FROM campaign_waves
            WHERE campaign_id=? AND wave_number=? AND status='pending'
            """,
            [campaign_id, wave_num],
        )

        if not assignments:
            continue

        # Create a temporary batch for this wave
        batch_ts = datetime.now(timezone.utc).isoformat()
        execute(
            "INSERT INTO import_batches (source_file, created_at) VALUES (?, ?)",
            [f"virality_campaign_{campaign_id}_wave_{wave_num}", batch_ts],
        )
        wave_batch_id = _last_id("import_batches")

        for a in assignments:
            a = dict(a)
            execute(
                """
                INSERT INTO jobs
                    (batch_id, account_id, device_id, post_url, intent,
                     sentiment_tag, comment_template, priority, status, created_at)
                VALUES (?, ?, ?, ?, ?, 'virality', ?, 1, 'pending', ?)
                """,
                [
                    wave_batch_id, a["account_id"], a["device_id"], target_url,
                    a["action"], a.get("comment_text"), batch_ts,
                ],
            )
            execute(
                "UPDATE campaign_waves SET status='running' WHERE id=?",
                [a["id"]],
            )

        plan_batch(wave_batch_id)
        results = run_batch(wave_batch_id, use_mock=use_mock)

        wave_done = results.get("done", 0)
        wave_error = results.get("error", 0)
        total_done += wave_done
        total_error += wave_error

        wave_ts = datetime.now(timezone.utc).isoformat()
        execute(
            """
            UPDATE campaign_waves
            SET status='done', executed_at=?
            WHERE campaign_id=? AND wave_number=?
            """,
            [wave_ts, campaign_id, wave_num],
        )

        # Pause between waves — skipped on last wave
        if wave_num < wave_count and wave_gap > 0:
            time.sleep(wave_gap)

    finish_ts = datetime.now(timezone.utc).isoformat()
    execute(
        "UPDATE virality_campaigns SET status='done', finished_at=? WHERE id=?",
        [finish_ts, campaign_id],
    )

    return {
        "campaign_id": campaign_id,
        "waves_executed": wave_count,
        "done": total_done,
        "error": total_error,
    }


# ---------------------------------------------------------------------------
# Progress & listing helpers
# ---------------------------------------------------------------------------

def list_campaigns() -> list[dict[str, Any]]:
    rows = fetch_all(
        "SELECT * FROM virality_campaigns ORDER BY id DESC",
    )
    return [dict(r) for r in rows]


def get_campaign_progress(campaign_id: int) -> dict[str, Any]:
    campaign = fetch_one("SELECT * FROM virality_campaigns WHERE id=?", [campaign_id])
    if not campaign:
        return {}

    waves = fetch_all(
        """
        SELECT wave_number, action, status, COUNT(*) as count
        FROM campaign_waves
        WHERE campaign_id=?
        GROUP BY wave_number, action, status
        ORDER BY wave_number, action
        """,
        [campaign_id],
    )

    summary = fetch_all(
        """
        SELECT status, COUNT(*) as count
        FROM campaign_waves
        WHERE campaign_id=?
        GROUP BY status
        """,
        [campaign_id],
    )

    return {
        "campaign": dict(campaign),
        "wave_breakdown": [dict(w) for w in waves],
        "summary": {r["status"]: r["count"] for r in summary},
    }
