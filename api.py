

from fastapi import FastAPI

app = FastAPI()

@app.get("/profiles/{profile}")
def get_profile(profile: str):
    from app.db import fetch_one
    row = fetch_one(
        "SELECT * FROM profiles WHERE account_id = ?", [profile]
    )
    if not row:

        raise HTTPException(status_code=404, detail="Profile not found")
    import json
    return {
        "name": row["name"],
        "email": row["email"],
        "phone": row["phone"],
        "birthday": row["birthday"],
        "location": row["location"],
        "role": row["role"],
        "favorites": json.loads(row["favorites_json"] or "[]")
    }

from fastapi import FastAPI, Query, File, Form, HTTPException, UploadFile, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from app.db import fetch_all, init_db

from fastapi.responses import JSONResponse

# Only one FastAPI instance
app = FastAPI(title="Automation Platform API", version="1.0.0")

# --- DEBUG: List jobs and insights for a profile and date range ---
@app.get("/debug/profile-data")
def debug_profile_data(profile: str = Query(...), range: str = Query("7d")):
    where = ["account_id = ?"]
    params = [profile]
    if range == "1d":
        where.append("timestamp >= date('now', '-1 day')")
    elif range == "7d":
        where.append("timestamp >= date('now', '-7 day')")
    elif range == "30d":
        where.append("timestamp >= date('now', '-30 day')")
    where_clause = "WHERE " + " AND ".join(where)

    jobs = fetch_all(f"SELECT * FROM jobs WHERE account_id = ?", [profile])
    insights = fetch_all(f"SELECT * FROM insights i LEFT JOIN jobs j ON i.job_id = j.id {where_clause}", params)
    return JSONResponse(content={
        "jobs": [dict(r) for r in jobs],
        "insights": [dict(r) for r in insights]
    })
from app.appium_servers import list_servers, start_server_for_device, stop_server_for_device
from app.devices import list_devices, sync_devices, validate_batch_device_assignments
from app.importer import import_excel
from app.planner import plan_batch
from app.reports import generate_batch_report
from app.runner import run_batch
from app.insights_api import router as insights_router
from app.insights_post_filters import router as post_filters_router
import datetime
import shutil
from pathlib import Path



# --- TRACK INSIGHTS ENDPOINT ---
@app.get("/dashboard")
def dashboard(
    profile: str = Query("", alias="profile"),
    range: str = Query("7d", alias="range"),
    post_id: str = Query("", alias="post_id"),
    post_date: str = Query("", alias="post_date")
):
    from app.db import fetch_all
    where = []
    params = []
    if profile:
        where.append("j.account_id = ?")
        params.append(profile)
    if range == "1d":
        where.append("timestamp >= date('now', '-1 day')")
    elif range == "7d":
        where.append("timestamp >= date('now', '-7 day')")
    elif range == "30d":
        where.append("timestamp >= date('now', '-30 day')")
    if post_id:
        where.append("j.post_url = ?")
        params.append(post_id)
    if post_date:
        where.append("DATE(j.created_at) = ?")
        params.append(post_date)
    where_clause = "WHERE " + " AND ".join(where) if where else ""

    # Fix total_posts: count unique posts for the profile, using max per post for likes/comments/views
    summary_row = fetch_all(f"""
        SELECT
            COUNT(*) as total_posts,
            SUM(max_likes) as total_likes,
            SUM(max_comments) as total_comments,
            SUM(max_views) as total_views,
            SUM(max_likes + max_comments) as total_engagement
        FROM (
            SELECT
                i.post_id,
                MAX(i.views) as max_views,
                MAX(i.likes) as max_likes,
                MAX(i.comments) as max_comments
            FROM insights i
            LEFT JOIN jobs j ON i.job_id = j.id
            {where_clause}
            GROUP BY i.post_id
        )
    """, params)[0]

    # Top posts with real post_url and profile
    top_posts = fetch_all(f"""
        SELECT
            j.post_url as url,
            j.account_id as profile,
            MAX(i.views) as views,
            MAX(i.likes) as likes,
            MAX(i.comments) as comments,
            MAX(i.likes + i.comments) as engagement,
            MAX(i.timestamp) as timestamp
        FROM insights i
        LEFT JOIN jobs j ON i.job_id = j.id
        {where_clause}
        GROUP BY i.post_id
        ORDER BY engagement DESC
    """, params)

    # Line chart: engagement over time (sum per day)
    line_chart = fetch_all(f"""
        SELECT substr(i.timestamp, 1, 10) as date, SUM(i.likes + i.comments) as engagement
        FROM insights i
        LEFT JOIN jobs j ON i.job_id = j.id
        {where_clause}
        GROUP BY date
        ORDER BY date ASC
    """, params)

    # Bar chart: views, likes, comments per post (top 10)
    bar_chart = fetch_all(f"""
        SELECT j.post_url as url, MAX(i.views) as views, MAX(i.likes) as likes, MAX(i.comments) as comments
        FROM insights i
        LEFT JOIN jobs j ON i.job_id = j.id
        {where_clause}
        GROUP BY i.post_id
        ORDER BY views DESC
        LIMIT 10
    """, params)

    # Donut chart: engagement distribution (likes vs comments)
    donut_chart = fetch_all(f"""
        SELECT 'Likes' as label, SUM(i.likes) as value FROM insights i LEFT JOIN jobs j ON i.job_id = j.id {where_clause}
        UNION ALL
        SELECT 'Comments' as label, SUM(i.comments) as value FROM insights i LEFT JOIN jobs j ON i.job_id = j.id {where_clause}
    """, params * 2 if params else None)

    charts = {
        "line": [dict(r) for r in line_chart],
        "bar": [dict(r) for r in bar_chart],
        "donut": [dict(r) for r in donut_chart],
    }

    return {
        "summary": dict(summary_row),
        "charts": charts,
        "top_posts": [dict(r) for r in top_posts]
    }




# --- INSIGHTS JOB IDS ENDPOINT ---
@app.get("/insights/db-job-ids")
def get_insights_job_ids():
    rows = fetch_all(
        "SELECT DISTINCT job_id FROM insights ORDER BY job_id ASC"
    )
    return [r["job_id"] for r in rows]

# --- INSIGHTS FROM DB ENDPOINT ---
@app.get("/insights/db/job/{job_id}")
def get_insights_db(job_id: int):
    rows = fetch_all(
        """
        SELECT job_id, post_id, event, views, likes, comments, timestamp
        FROM insights
        WHERE job_id = ?
        ORDER BY timestamp ASC
        """,
        [job_id],
    )
    return [dict(r) for r in rows]



# Allow local React dev server to call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(insights_router)
app.include_router(post_filters_router)

@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/batches")
def get_batches() -> list[dict[str, object]]:
    rows = fetch_all("SELECT id, source_file, created_at FROM import_batches ORDER BY id DESC")
    return [dict(r) for r in rows]


@app.post("/batches/import")
def import_batch(file: UploadFile = File(...)) -> dict[str, int]:
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="Only .xlsx files are supported")

    upload_dir = Path("data")
    upload_dir.mkdir(parents=True, exist_ok=True)
    out_file = upload_dir / "upload.xlsx"

    with out_file.open("wb") as handle:
        shutil.copyfileobj(file.file, handle)

    batch_id = import_excel(str(out_file))
    return {"batch_id": batch_id}


@app.post("/batches/{batch_id}/validate")
def validate_batch(batch_id: int) -> dict[str, int]:
    return validate_batch_device_assignments(batch_id)


@app.post("/batches/{batch_id}/plan")
def plan(batch_id: int) -> dict[str, int]:
    return {"planned": plan_batch(batch_id)}


@app.post("/batches/{batch_id}/run")
def run(batch_id: int, live_mode: bool = Form(False)) -> dict[str, int]:
    return run_batch(batch_id, use_mock=(not live_mode))


@app.post("/batches/{batch_id}/report")
def report(batch_id: int) -> dict[str, str]:
    path = generate_batch_report(batch_id)
    return {"report_path": path}


@app.get("/devices")
def get_devices() -> list[dict[str, str]]:
    return list_devices()


@app.post("/devices/sync")
def sync(server_host: str = Form("127.0.0.1"), base_port: int = Form(4723)) -> dict[str, int]:
    return sync_devices(f"http://{server_host}:{base_port}")


@app.get("/servers")
def get_servers() -> list[dict[str, object]]:
    return list_servers()


@app.post("/servers/start")
def start_server(
    device_id: str = Form(...),
    server_host: str = Form("127.0.0.1"),
    port: int = Form(4723),
) -> dict[str, object]:
    return start_server_for_device(device_id, host=server_host, port=port)


@app.post("/servers/stop")
def stop_server(device_id: str = Form(...)) -> dict[str, str]:
    return stop_server_for_device(device_id)


@app.get("/jobs")
def get_jobs(limit: int = 500) -> list[dict[str, object]]:
    rows = fetch_all(
        """
        SELECT j.id, j.batch_id, j.account_id, j.device_id, j.intent, j.status, j.priority,
               j.error_message, j.evidence_path, j.created_at
        FROM jobs j
        ORDER BY j.id DESC
        LIMIT ?
        """,
        [limit],
    )
    return [dict(r) for r in rows]


@app.get("/events")
def get_events(limit: int = 200) -> list[dict[str, object]]:
    rows = fetch_all(
        "SELECT e.id, e.job_id, e.level, e.message, e.created_at FROM run_events e ORDER BY e.id DESC LIMIT ?",
        [limit],
    )
    return [dict(r) for r in rows]


# --- TRACK INSIGHTS ENDPOINT ---
@app.post("/track-insights")
async def track_insights(request: Request):
    data = await request.json()
    # Basic validation
    required = {"post_id", "event", "views", "likes", "comments", "timestamp"}
    if not required.issubset(data):
        raise HTTPException(status_code=400, detail=f"Missing fields: {required - set(data)}")
    # Store as a new file for history
    folder = Path("evidence")
    folder.mkdir(parents=True, exist_ok=True)
    import re
    # Extract only the Instagram shortcode from post_id (which may be a URL)
    def extract_shortcode(post_id):
        if not post_id:
            return "unknown"
        match = re.search(r'/p/([A-Za-z0-9_-]+)', post_id)
        return match.group(1) if match else re.sub(r'[^A-Za-z0-9_-]', '', post_id)

    safe_post_id = extract_shortcode(data['post_id'])
    fname = f"track_{safe_post_id}_{data['event']}_{datetime.datetime.now().strftime('%Y%m%dT%H%M%S')}.json"
    path = folder / fname
    import json

    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return {"status": "ok", "file": str(path)}
