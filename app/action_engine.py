from __future__ import annotations

import random
import time
from pathlib import Path
from typing import Any

from app.db import execute
import os
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


ACCESS_TOKEN = os.getenv('IG_ACCESS_TOKEN')
PASSWORD = os.getenv('IG_PASSWORD')
print(f"[DEBUG] ACCESS_TOKEN loaded: {'SET' if ACCESS_TOKEN else 'NOT SET'}")

try:
    from appium import webdriver
    from appium.options.android import UiAutomator2Options
    from appium.webdriver.common.appiumby import AppiumBy
except ImportError:  # pragma: no cover - optional dependency during static checks
    webdriver = None
    UiAutomator2Options = None
    AppiumBy = None
    TouchAction = None

INSTAGRAM_PACKAGE = "com.instagram.android"


class ActionEngine:
    # ...existing code...
    @staticmethod
    def _safe_filename(s: str) -> str:
        import re
        return re.sub(r'[^A-Za-z0-9_-]', '_', s)
    """Execution engine with optional Appium hookup.

    Default mode is mock for safe local validation. Replace _mock with real driver
    calls when your Appium endpoints are configured.
        """

    def __init__(self, use_mock: bool = False) -> None:
        self.use_mock = use_mock
        self._drivers: dict[str, Any] = {}

    def run_step(
        self,
        job_id: int,
        device_id: str,
        appium_server_url: str,
        action: str,
        value: str | None,
        min_wait_ms: int,
        max_wait_ms: int,
    ) -> str | None:
        delay_ms = random.randint(min_wait_ms, max_wait_ms)
        time.sleep(delay_ms / 1000.0)

        driver = None
        if not self.use_mock and action != "skip":
            driver = self._get_driver(device_id, appium_server_url)

        if action == "wait":
            self._log(job_id, f"Waiting for {min_wait_ms}–{max_wait_ms} ms ({value})")
            time.sleep(random.randint(min_wait_ms, max_wait_ms) / 1000.0)
            return None
        if action == "back":
            if driver:
                try:
                    driver.back()
                except Exception as e:
                    print(f"[ERROR] driver.back() failed: {e}")
            self._log(job_id, "Back navigation performed")
            return None
            self._log(job_id, f"Waiting for {min_wait_ms}–{max_wait_ms} ms ({value})")
            time.sleep(random.randint(min_wait_ms, max_wait_ms) / 1000.0)
            return None
        if action == "launch":
            if driver:
                driver.activate_app(INSTAGRAM_PACKAGE)
            self._log(job_id, "App launched")
        elif action == "terminate":
            if driver:
                driver.terminate_app(INSTAGRAM_PACKAGE)
            self._log(job_id, "App terminated")
        elif action == "open_url":
            print(f"[DEBUG] Action=open_url, job_id={job_id}, value={value}")
            if not value or not str(value).strip():
                self._log(job_id, "Skipped open_url: missing or empty URL value")
                return None
            if driver:
                try:
                    print(f"[DEBUG] deepLink(open_url) value: {value}")
                    driver.execute_script("mobile: deepLink", {"url": value, "package": INSTAGRAM_PACKAGE})
                    time.sleep(3)  # Wait for post to load
                except Exception as e:
                    print(f"[ERROR] Failed to open URL via deepLink: {e}")
            self._log(job_id, f"Opened URL: {value}")
        elif action == "scroll":
            if driver:
                size = driver.get_window_size()
                driver.execute_script(
                    "mobile: scrollGesture",
                    {
                        "left": 10,
                        "top": 10,
                        "width": max(size.get("width", 100) - 20, 50),
                        "height": max(size.get("height", 200) - 20, 80),
                        "direction": "down",
                        "percent": 0.7,
                    },
                )
            self._log(job_id, f"Scrolled count={value or '1'}")
        elif action == "like":
            print(f"[DEBUG] Action=like, job_id={job_id}, value={value}")
            if not value or not str(value).strip():
                self._log(job_id, "Skipped like: missing or empty URL value")
                return None
            if driver:
                try:
                    print(f"[DEBUG] deepLink(like) value: {value}")
                    driver.execute_script("mobile: deepLink", {"url": value, "package": INSTAGRAM_PACKAGE})
                    time.sleep(3)
                except Exception as e:
                    print(f"[ERROR] Failed to deepLink before like: {e}")
                try:
                    self._tap_like(driver)
                except Exception as e:
                    print(f"[ERROR] Like action failed: {e}")
                try:
                    driver.back()
                except Exception as e:
                    print(f"[ERROR] driver.back() after like failed: {e}")
            self._log(job_id, "Like action completed")
        elif action == "comment":
            print(f"[DEBUG] Action=comment, job_id={job_id}, value={value}")
            # value should be a dict: {"url": ..., "text": ...} (may be JSON string from DB)
            import json
            if isinstance(value, str):
                try:
                    value = json.loads(value)
                except Exception:
                    pass
            if not value or not isinstance(value, dict) or not value.get("url"):
                self._log(job_id, "Skipped comment: missing or empty URL value")
                return None
            post_url = value["url"]
            comment_text = value.get("text", "Nice 🔥")
            if driver:
                try:
                    print(f"[DEBUG] deepLink(comment) url: {post_url}")
                    driver.execute_script("mobile: deepLink", {"url": post_url, "package": INSTAGRAM_PACKAGE})
                    time.sleep(3)
                except Exception as e:
                    print(f"[ERROR] Failed to deepLink before comment: {e}")
                try:
                    self._post_comment(driver, comment_text)
                except Exception as e:
                    print(f"[ERROR] Comment action failed: {e}")
                try:
                    driver.back()
                except Exception as e:
                    print(f"[ERROR] driver.back() after comment failed: {e}")
            self._log(job_id, f"Comment action completed: {comment_text}")
        elif action == "repost":
            if driver:
                if value:
                    try:
                        driver.execute_script("mobile: deepLink", {"url": value, "package": INSTAGRAM_PACKAGE})
                        time.sleep(3)  # Wait for post to load
                    except Exception:
                        pass
                self._tap_repost(driver)
                try:
                    driver.back()
                except Exception as e:
                    print(f"[ERROR] driver.back() after repost failed: {e}")
            self._log(job_id, "Repost action completed")
        elif action == "share":
            if driver:
                self._tap_share(driver)
                try:
                    driver.back()
                except Exception as e:
                    print(f"[ERROR] driver.back() after share failed: {e}")
            self._log(job_id, "Share action completed")
        elif action == "skip":
            self._log(job_id, f"Step skipped: {value}")
        elif action == "capture_evidence":
            path = self._capture_evidence(job_id, driver)
            self._log(job_id, f"Evidence captured: {path}")
            return path
        elif action == "capture_insights":
            # value is the event type (e.g., created, like, comment, repost)

            path = self._capture_insights(job_id, value)
            self._log(job_id, f"Insights captured: {path}")
            return path
        elif action == "open_instagram":
            if driver:
                self.open_instagram(driver)
            self._log(job_id, "Instagram app opened")
        elif action == "scroll_randomly":
            if driver:
                duration = int(value) if value else 120
                self.scroll_randomly(driver, duration)
            self._log(job_id, f"Scrolled randomly for {value or 120} sec")
        elif action == "scroll_reels":
            if driver:
                duration = int(value) if value else 60
                self.scroll_reels(driver, duration)
            self._log(job_id, f"Scrolled reels for {value or 60} sec")
        elif action == "close_instagram":
            if driver:
                self.close_instagram(driver)
            self._log(job_id, "Instagram app closed")
        elif action == "redirect_url":
            print(f"[DEBUG] Action=redirect_url, job_id={job_id}, value={value}")
            if not value or not str(value).strip():
                self._log(job_id, "Skipped redirect_url: missing or empty URL value")
                return None
            if driver:
                try:
                    print(f"[DEBUG] deepLink(redirect_url) value: {value}")
                    driver.execute_script("mobile: deepLink", {"url": value, "package": INSTAGRAM_PACKAGE})
                    time.sleep(3)
                except Exception as e:
                    print(f"[ERROR] Failed to redirect via deepLink: {e}")
            self._log(job_id, f"Redirected to URL: {value}")
        else:
            raise ValueError(f"Unsupported action: {action}")
        return None
    def _capture_insights(self, job_id: int, event: str) -> str:
        """
        Fetch post insights, send to /track-insights API, store as evidence file.
        """
        import requests
        import json
        from datetime import datetime, timezone
        from app.db import fetch_one

        # Fetch job info for post_url and post_id
        job = fetch_one("SELECT post_url FROM jobs WHERE id = ?", [job_id])
        post_url = job["post_url"] if job else None
        post_id = self._extract_post_id(post_url) if post_url else str(job_id)

        # --- Fetch real Instagram insights if possible ---

        # --- Fetch real Instagram insights using Graph API module ---

        insights = None
        if ACCESS_TOKEN and post_url:
            import re
            from app.instagram_insights import get_instagram_insights
            m = re.search(r"/p/([\w-]+)/", post_url)
            shortcode = m.group(1) if m else None
            try:
                result = get_instagram_insights(shortcode)
                # Prefer real-time counts if present
                likes = result.get("like_count")
                comments = result.get("comments_count")
                reposts = result.get("repost_count")
                shares = result.get("share_count")
                # Fallbacks for backward compatibility
                if likes is None:
                    likes = result.get("engagement") or result.get("likes") or 0
                if comments is None:
                    comments = result.get("comments") or 0
                if reposts is None:
                    reposts = result.get("repost") or result.get("shares") or 0
                if shares is None:
                    shares = result.get("share") or result.get("shares") or 0
                insights = {
                    "views": result.get("impressions", 0),
                    "likes": likes,
                    "comments": comments,
                    "reposts": reposts,
                    "shares": shares
                }
            except Exception as e:
                print(f"[DEBUG] Instagram API error: {e}")
                import traceback
                traceback.print_exc()
                insights = None
        # Always write a row, even if API fails
        if not insights:
            print(f"[DEBUG] ACCESS_TOKEN at failure: {ACCESS_TOKEN}")
            insights = {
                "views": 0,
                "likes": 0,
                "comments": 0,
                "reposts": 0,
                "shares": 0
            }
            # Optionally, add a field to payload to indicate failure
            # payload["api_error"] = "Failed to fetch real Instagram insights. Check ACCESS_TOKEN and API response."

        payload = {
            "job_id": job_id,
            "post_id": post_id,
            "event": event,
            "views": insights["views"],
            "likes": insights["likes"],
            "comments": insights["comments"],
            "reposts": insights["reposts"],
            "shares": insights["shares"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Send to backend API
        try:
            response = requests.post("http://127.0.0.1:8000/track-insights", json=payload)
            response.raise_for_status()
        except Exception as e:
            payload["api_error"] = str(e)

        # Store in insights DB table with debug logging
        try:
            print(f"[DEBUG] Writing insights to DB: job_id={job_id}, event={event}, views={insights['views']}, likes={insights['likes']}, comments={insights['comments']}, timestamp={payload['timestamp']}")
            execute(
                """
                INSERT INTO insights (job_id, post_id, event, views, likes, comments, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    job_id,
                    post_id,
                    event,
                    insights["views"],
                    insights["likes"],
                    insights["comments"],
                    payload["timestamp"]
                ]
            )
            print(f"[DEBUG] Successfully wrote insights for job_id={job_id}, event={event}")
        except Exception as e:
            print(f"[ERROR] Failed to write insights for job_id={job_id}, event={event}: {e}")
            payload["db_error"] = str(e)

        # Store locally for history
        folder = Path("evidence")
        folder.mkdir(parents=True, exist_ok=True)
        safe_post_id = self._safe_filename(post_id)
        path = folder / f"job_{job_id}_insights_{event}_{safe_post_id}_{int(time.time())}.json"
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        self._log(job_id, f"Insights: {payload}")
        return str(path)

    @staticmethod
    def _extract_post_id(post_url: str | None) -> str:
        # Simple extraction logic; customize as needed
        if not post_url:
            return "unknown"
        # Example: https://instagram.com/p/POSTID/ -> POSTID
        parts = post_url.rstrip("/").split("/")
        return parts[-1] if parts else "unknown"

    def _capture_evidence(self, job_id: int, driver: Any | None) -> str:
        folder = Path("evidence")
        folder.mkdir(parents=True, exist_ok=True)
        if driver:
            path = folder / f"job_{job_id}_{int(time.time())}.png"
            driver.get_screenshot_as_file(str(path))
        else:
            path = folder / f"job_{job_id}_{int(time.time())}.txt"
            path.write_text("evidence placeholder\n", encoding="utf-8")
        return str(path)

    def _get_driver(self, device_id: str, appium_server_url: str) -> Any:
        if self.use_mock:
            return None
        if device_id in self._drivers:
            return self._drivers[device_id]
        if webdriver is None or UiAutomator2Options is None:
            raise RuntimeError("Appium Python client not installed. Install appium-python-client.")

        options = UiAutomator2Options()
        options.set_capability("platformName", "Android")
        options.set_capability("automationName", "UiAutomator2")
        options.set_capability("udid", device_id)
        options.set_capability("deviceName", device_id)
        options.set_capability("newCommandTimeout", 300)

        driver = webdriver.Remote(command_executor=appium_server_url, options=options)
        # Debug print to check driver type and perform_actions presence
        print("[DEBUG] Driver type:", type(driver))
        print("[DEBUG] Has perform_actions:", hasattr(driver, "perform_actions"))
        self._drivers[device_id] = driver
        return driver

    @staticmethod
    def _tap_like(driver: Any) -> None:
        """
        Tap the like button only if the post is not already liked.
        If already liked, do nothing (just view the post).
        """
        id_candidates = [
            "com.instagram.android:id/row_feed_button_like",
        ]
        xpath_candidates = [
            "//android.widget.ImageView[contains(@content-desc,'Like')]",
            "//android.widget.Button[contains(@content-desc,'Like')]",
            "//*[contains(@content-desc,'Like')]",
        ]

        def is_liked(element):
            # Try to detect if the button is already in liked state
            # This logic may need to be adapted for your Instagram version
            try:
                desc = element.get_attribute('content-desc') or ""
                # Common patterns: 'Unlike', 'Liked', 'Like'
                if "unlike" in desc.lower() or "liked" in desc.lower():
                    return True
                # Sometimes resource-id or selected state can help
                if hasattr(element, 'is_selected') and element.is_selected():
                    return True
            except Exception:
                pass
            return False

        last_error: Exception | None = None
        for _ in range(4):
            for element_id in id_candidates:
                elems = driver.find_elements("id", element_id)
                for elem in elems:
                    if is_liked(elem):
                        # Already liked, do nothing
                        return
                    try:
                        ActionEngine._tap_element(driver, elem)
                        return
                    except Exception as exc:
                        last_error = exc

            for xpath in xpath_candidates:
                elems = driver.find_elements("xpath", xpath)
                for elem in elems:
                    if is_liked(elem):
                        # Already liked, do nothing
                        return
                    try:
                        ActionEngine._tap_element(driver, elem)
                        return
                    except Exception as exc:
                        last_error = exc

            # If not yet visible/clickable, try a short scroll and retry.
            try:
                size = driver.get_window_size()
                driver.execute_script(
                    "mobile: scrollGesture",
                    {
                        "left": 10,
                        "top": 10,
                        "width": max(size.get("width", 100) - 20, 50),
                        "height": max(size.get("height", 200) - 20, 80),
                        "direction": "down",
                        "percent": 0.45,
                    },
                )
            except Exception as exc:
                last_error = exc
            time.sleep(0.4)

        if last_error:
            raise RuntimeError(f"Like button found but click failed: {last_error}") from last_error
        raise RuntimeError("Like button not found on current screen")

    @staticmethod
    def _tap_repost(driver: Any) -> None:
        try:
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC

            wait = WebDriverWait(driver, 10)

            repost_btn = wait.until(
                EC.presence_of_element_located(
                    (AppiumBy.XPATH, "//android.widget.Button[@resource-id='com.instagram.android:id/reposts_ufi_icon']/android.view.ViewGroup/android.widget.ImageView")
                )
            )

            repost_btn.click()
            print("✅ Repost button clicked")

        except Exception as e:
            print("❌ Repost button click failed:", e)

    @staticmethod
    def _navigate_back(driver: Any, attempts: int = 1, delay: float = 0.5) -> None:
        for _ in range(attempts):
            try:
                driver.back()
                time.sleep(delay)
            except Exception:
                break

    @staticmethod
    def _tap_element(driver: Any, element: Any) -> None:
        try:
            element.click()
            return
        except Exception:
            pass

        rect = element.rect or {}
        x = int(rect.get("x", 0) + rect.get("width", 0) / 2)
        y = int(rect.get("y", 0) + rect.get("height", 0) / 2)
        if x <= 0 or y <= 0:
            raise RuntimeError("Element tap fallback failed: invalid bounds")
        driver.execute_script("mobile: clickGesture", {"x": x, "y": y})

    @staticmethod
    def _tap_share(driver: Any) -> None:
        candidates = [
            "//android.widget.ImageView[contains(@content-desc,'Share')]",
            "//android.widget.Button[contains(@content-desc,'Share')]",
            "//*[contains(@content-desc,'Share')]",
            "//*[contains(@text,'Share')]",
            "//*[contains(@content-desc,'Repost')]",
            "//*[contains(@text,'Repost')]",
        ]
        last_error: Exception | None = None
        for _ in range(4):
            for xpath in candidates:
                elems = driver.find_elements("xpath", xpath)
                if elems:
                    try:
                        ActionEngine._tap_element(driver, elems[0])
                        return
                    except Exception as exc:
                        last_error = exc
            time.sleep(0.35)

        if last_error:
            raise RuntimeError(f"Share/Repost button found but click failed: {last_error}") from last_error
        raise RuntimeError("Share/Repost button not found on current screen")

    @staticmethod
    def _post_comment(driver: Any, text: str) -> None:
        import time
        from appium.webdriver.common.appiumby import AppiumBy
        try:
            comment_btn = driver.find_element(AppiumBy.ID, "com.instagram.android:id/row_feed_button_comment")
            comment_btn.click()
            print("✅ Clicked comment button")
        except Exception as e:
            print(f"[ERROR] Comment button not found: {e}")
            raise
        time.sleep(2)
        try:
            active_element = driver.switch_to.active_element
            active_element.send_keys(text)
            print("✅ Entered comment")
            driver.find_element(AppiumBy.ACCESSIBILITY_ID, "Post").click()
            print("✅ Comment posted successfully!")
        except Exception as e:
            print(f"[ERROR] Could not enter/post comment: {e}")
            raise

    def close(self) -> None:
        for driver in self._drivers.values():
            try:
                driver.quit()
            except Exception:
                pass
        self._drivers.clear()

    @staticmethod
    def _log(job_id: int, message: str) -> None:
        execute(
            "INSERT INTO run_events(job_id, level, message, created_at) VALUES (?, ?, ?, datetime('now'))",
            [job_id, "INFO", message],
        )



    def open_instagram(self, driver):
        try:
            driver.activate_app(INSTAGRAM_PACKAGE)
            time.sleep(3)
        except Exception as e:
            print("❌ Could not open Instagram app:", e)

    def scroll_randomly(self, driver, duration_sec=120):
        print(f"🤖 Scrolling randomly for {duration_sec} seconds...")
        end_time = time.time() + duration_sec
        size = driver.get_window_size()
        while time.time() < end_time:
            start_x = random.randint(int(size['width']*0.3), int(size['width']*0.7))
            start_y = random.randint(int(size['height']*0.6), int(size['height']*0.8))
            end_x = start_x
            end_y = random.randint(int(size['height']*0.2), int(size['height']*0.4))
            driver.swipe(start_x, start_y, end_x, end_y, duration=random.randint(400, 900))
            time.sleep(random.uniform(1.5, 4.0))

    def scroll_reels(self, driver, duration_sec=60):
        print(f"🤖 Scrolling through reels for {duration_sec} seconds...")
        try:
            reels_tab = driver.find_element(AppiumBy.ACCESSIBILITY_ID, "Reels")
            reels_tab.click()
            time.sleep(3)
        except Exception:
            print("⚠️ Could not find Reels tab, scrolling anyway.")
        self.scroll_randomly(driver, duration_sec)

    def close_instagram(self, driver):
        try:
            driver.terminate_app(INSTAGRAM_PACKAGE)
            time.sleep(2)
        except Exception as e:
            print("❌ Could not close Instagram app:", e)

    def redirect_url(self, driver, url):
        try:
            driver.execute_script("mobile: deepLink", {"url": url, "package": INSTAGRAM_PACKAGE})
            time.sleep(3)
        except Exception as e:
            print(f"[ERROR] redirect_url deepLink failed: {e}")
