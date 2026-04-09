from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Intent(str, Enum):
    REVIEW = "review"
    LAUNCH = "launch"
    TERMINATE = "terminate"
    POST = "post"
    SCROLL = "scroll"
    LIKE = "like"
    COMMENT = "comment"
    REPOST = "repost"
    SHARE = "share"
    LIKE_AND_COMMENT = "like_and_comment"
    # Virality-specific intents
    SAVE = "save"
    WATCH_REEL = "watch_reel"
    PROFILE_VISIT = "profile_visit"


class Status(str, Enum):
    PENDING = "pending"
    PLANNED = "planned"
    WAITING_DEVICE_ONLINE = "waiting_device_online"
    BLOCKED_NO_DEVICE = "blocked_no_device"
    BLOCKED_UNKNOWN_DEVICE = "blocked_unknown_device"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"
    SKIPPED = "skipped"


@dataclass
class JobInput:
    account_id: str
    device_id: str
    post_url: str
    intent: Intent
    sentiment_tag: str
    comment_template: Optional[str]
    priority: int
    description: Optional[str]


@dataclass
class PlannedStep:
    step_order: int
    action: str
    value: Optional[str] = None
    min_wait_ms: int = 500
    max_wait_ms: int = 1800
