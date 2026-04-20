
import os
import json
import requests
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from app.db import fetch_all

# --- Instagram Insights via Graph API ---
router = APIRouter()

@router.get("/insights/profiles")
def get_profiles():
    rows = fetch_all("SELECT DISTINCT account_id FROM jobs ORDER BY account_id ASC")
    return [r["account_id"] for r in rows]


ACCESS_TOKEN = os.getenv("IG_ACCESS_TOKEN")

# --- Instagram Media Counts via Graph API ---
@router.get("/instagram/media_counts")
def fetch_instagram_media_counts(media_id: str):
    """
    Fetch like_count and comments_count for a given Instagram media_id.
    """
    if not ACCESS_TOKEN:
        raise HTTPException(status_code=500, detail="IG_ACCESS_TOKEN not set in environment.")
    url = f"https://graph.facebook.com/v18.0/{media_id}"
    params = {
        "fields": "like_count,comments_count",
        "access_token": ACCESS_TOKEN
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code != 200:
            raise Exception(resp.text)
        return JSONResponse(content=resp.json())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

from app.instagram_insights import get_instagram_insights

# --- Instagram Insights via Graph API ---
@router.get("/instagram/insights")
def fetch_instagram_insights(shortcode: str = None):
    try:
        result = get_instagram_insights(shortcode)
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

EVIDENCE_DIR = os.path.join(os.path.dirname(__file__), '..', 'evidence')

@router.get("/insights/by-job-id/{job_id}")
def get_insights(job_id: int):
    """
    Return all insights JSON files for a given job_id.
    """
    try:
        files = [f for f in os.listdir(EVIDENCE_DIR) if f.startswith(f"job_{job_id}_insights_") and f.endswith(".json")]
        if not files:
            raise HTTPException(status_code=404, detail="No insights found for this job_id.")
        insights = []
        for fname in sorted(files):
            with open(os.path.join(EVIDENCE_DIR, fname), encoding="utf-8") as f:
                data = json.load(f)
                data['file'] = fname
                insights.append(data)
        return JSONResponse(content=insights)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
