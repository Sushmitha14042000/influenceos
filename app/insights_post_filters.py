from fastapi import APIRouter
from typing import List
from app.db import fetch_all

router = APIRouter()

@router.get("/insights/post-ids", response_model=List[str], tags=["filters"])
def get_post_ids():
    rows = fetch_all("SELECT DISTINCT post_url FROM jobs WHERE post_url IS NOT NULL ORDER BY post_url ASC")
    return [r["post_url"] for r in rows]

@router.get("/insights/post-dates", response_model=List[str], tags=["filters"])
def get_post_dates():
    rows = fetch_all("SELECT DISTINCT DATE(created_at) as post_date FROM jobs WHERE created_at IS NOT NULL ORDER BY post_date DESC")
    return [r["post_date"] for r in rows]
