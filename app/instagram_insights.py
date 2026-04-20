import os
import requests
import logging
from typing import Optional, Dict
from requests.adapters import HTTPAdapter
try:
    from urllib3.util.retry import Retry
except ImportError:
    from urllib3.util.retry import Retry

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("instagram_insights")

ACCESS_TOKEN = os.getenv("IG_ACCESS_TOKEN")
GRAPH_API_BASE = "https://graph.facebook.com/v18.0"
TIMEOUT = 10
RETRIES = 3


def _get_with_retries(url: str, params: dict) -> dict:
    session = requests.Session()
    retry = Retry(
        total=RETRIES,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"]
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    try:
        logger.debug(f"Requesting URL: {url}")
        logger.debug(f"Request params: {params}")
        resp = session.get(url, params=params, timeout=TIMEOUT)
        logger.debug(f"Response status: {resp.status_code}")
        logger.debug(f"Response text: {resp.text}")
        if resp.status_code != 200:
            logger.error(f"API error: {resp.status_code} {resp.text}")
            raise Exception(resp.json())
        return resp.json()
    except Exception as e:
        logger.error(f"Request failed: {e}")
        raise


def get_instagram_insights(post_shortcode: Optional[str] = None) -> Dict:
    if not ACCESS_TOKEN:
        raise Exception("ACCESS_TOKEN not set in environment.")

    # ✅ HARDCODE (already verified working)
    PAGE_ID = "1120923051094116"
    IG_USER_ID = "17841448829346760"

    # Step 1: Get Media List
    logger.info("Fetching Instagram media...")
    media_url = f"{GRAPH_API_BASE}/{IG_USER_ID}/media"
    media_resp = _get_with_retries(media_url, {
        "fields": "id,caption,media_type,permalink,timestamp",
        "access_token": ACCESS_TOKEN
    })
    media_data = media_resp.get("data", [])
    if not media_data:
        raise Exception("No media found for this Instagram account.")

    # Step 2: Find media_id and media_type
    media_id = None
    media_type = None
    selected_media = None
    if post_shortcode:
        for m in media_data:
            permalink = m.get("permalink", "")
            if f"/{post_shortcode}" in permalink:
                media_id = m["id"]
                media_type = m.get("media_type")
                selected_media = m
                break
        if not media_id:
            raise Exception(f"No media found with shortcode {post_shortcode}")
    else:
        selected_media = media_data[0]
        media_id = selected_media["id"]
        media_type = selected_media.get("media_type")


    logger.info(f"Using media_id: {media_id}, media_type: {media_type}")

    # Step 3: Fetch real-time like_count and comments_count
    counts_url = f"{GRAPH_API_BASE}/{media_id}"
    counts_params = {
        "fields": "like_count,comments_count",
        "access_token": ACCESS_TOKEN
    }
    try:
        counts_resp = _get_with_retries(counts_url, counts_params)
        like_count = counts_resp.get("like_count", 0)
        comments_count = counts_resp.get("comments_count", 0)
        logger.info(f"Fetched like_count={like_count}, comments_count={comments_count}")
    except Exception as e:
        logger.error(f"Failed to fetch like/comment counts: {e}")
        like_count = 0
        comments_count = 0


    # Step 4: Dynamically select metrics based on media_type
    # Reference: https://developers.facebook.com/docs/instagram-api/reference/ig-media/insights
    metrics_map = {
        "IMAGE": ["reach", "saved"],
        "VIDEO": ["reach", "saved", "video_views"],
        "CAROUSEL_ALBUM": ["reach", "saved"],
        "REEL": ["plays", "reach", "shares", "saved"],
        "STORY": ["reach", "impressions", "replies", "exits", "taps_forward", "taps_back"],
    }
    # Default to reach if unknown
    metrics_list = metrics_map.get(media_type, ["reach"])
    metrics_str = ",".join(metrics_list)

    insights_url = f"{GRAPH_API_BASE}/{media_id}/insights"
    insights_resp = _get_with_retries(insights_url, {
        "metric": metrics_str,
        "access_token": ACCESS_TOKEN
    })
    metrics = {
        m["name"]: m["values"][0]["value"]
        for m in insights_resp.get("data", [])
        if m.get("values")
    }

    # Add repost and share if present in metrics
    repost_count = metrics.get("repost", 0) or metrics.get("shares", 0)
    share_count = metrics.get("share", 0) or metrics.get("shares", 0)

    result = {
        "page_id": PAGE_ID,
        "ig_user_id": IG_USER_ID,
        "media_id": media_id,
        "media_type": media_type,
        "like_count": like_count,
        "comments_count": comments_count,
        "repost_count": repost_count,
        "share_count": share_count,
    }
    # Add all returned metrics to result
    result.update(metrics)
    return result
