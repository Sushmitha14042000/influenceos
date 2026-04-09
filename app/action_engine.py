from __future__ import annotations

import random
import time
from pathlib import Path
from typing import Any

from app.db import execute

try:
    from appium import webdriver
    from appium.options.android import UiAutomator2Options
except ImportError:  # pragma: no cover - optional dependency during static checks
    webdriver = None
    UiAutomator2Options = None

INSTAGRAM_PACKAGE = "com.instagram.android"


class ActionEngine:
    """Execution engine with optional Appium hookup.

    Default mode is mock for safe local validation. Replace _mock with real driver
    calls when your Appium endpoints are configured.
    """

    def __init__(self, use_mock: bool = True) -> None:
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

        if action == "launch":
            if driver:
                driver.activate_app(INSTAGRAM_PACKAGE)
            self._log(job_id, "App launched")
        elif action == "terminate":
            if driver:
                driver.terminate_app(INSTAGRAM_PACKAGE)
            self._log(job_id, "App terminated")
        elif action == "open_url":
            if driver and value:
                try:
                    driver.execute_script("mobile: deepLink", {"url": value, "package": INSTAGRAM_PACKAGE})
                except Exception:
                    pass
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
            if driver:
                self._tap_like(driver)
            self._log(job_id, "Like action completed")
        elif action == "comment":
            if driver and value:
                self._post_comment(driver, value)
            self._log(job_id, f"Comment action completed: {value}")
        elif action == "repost":
            if driver:
                self._tap_share(driver)
            self._log(job_id, "Repost action completed")
        elif action == "share":
            if driver:
                self._tap_share(driver)
            self._log(job_id, "Share action completed")
        elif action == "save":
            if driver:
                self._tap_save(driver)
            self._log(job_id, "Save action completed")
        elif action == "watch_reel":
            watch_secs = int(value or 15)
            if driver:
                self._watch_reel(driver, watch_secs)
            self._log(job_id, f"Watched reel for {watch_secs}s")
        elif action == "profile_visit":
            if driver and value:
                driver.execute_script("mobile: deepLink", {"url": value, "package": INSTAGRAM_PACKAGE})
            self._log(job_id, f"Profile visit: {value}")
        elif action == "skip":
            self._log(job_id, f"Step skipped: {value}")
        elif action == "capture_evidence":
            path = self._capture_evidence(job_id, driver)
            self._log(job_id, f"Evidence captured: {path}")
            return path
        else:
            raise ValueError(f"Unsupported action: {action}")
        return None

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
        self._drivers[device_id] = driver
        return driver

    @staticmethod
    def _tap_save(driver: Any) -> None:
        candidates = [
            "//android.widget.ImageView[contains(@content-desc,'Save')]",
            "//android.widget.Button[contains(@content-desc,'Save')]",
        ]
        for xpath in candidates:
            elems = driver.find_elements("xpath", xpath)
            if elems:
                elems[0].click()
                return

    @staticmethod
    def _watch_reel(driver: Any, watch_seconds: int = 15) -> None:
        """Keep the Reel open for watch_seconds to boost completion-rate signal."""
        time.sleep(max(1, watch_seconds))

    @staticmethod
    def _tap_like(driver: Any) -> None:
        candidates = [
            "//android.widget.ImageView[contains(@content-desc,'Like')]",
            "//android.widget.Button[contains(@content-desc,'Like')]",
        ]
        for xpath in candidates:
            elems = driver.find_elements("xpath", xpath)
            if elems:
                elems[0].click()
                return

    @staticmethod
    def _tap_share(driver: Any) -> None:
        candidates = [
            "//android.widget.ImageView[contains(@content-desc,'Share')]",
            "//android.widget.Button[contains(@content-desc,'Share')]",
        ]
        for xpath in candidates:
            elems = driver.find_elements("xpath", xpath)
            if elems:
                elems[0].click()
                return

    @staticmethod
    def _post_comment(driver: Any, text: str) -> None:
        comment_buttons = driver.find_elements("xpath", "//android.widget.ImageView[contains(@content-desc,'Comment')]")
        if comment_buttons:
            comment_buttons[0].click()

        text_boxes = driver.find_elements("xpath", "//android.widget.EditText")
        if text_boxes:
            text_boxes[0].send_keys(text)

        post_buttons = driver.find_elements("xpath", "//android.widget.Button[@text='Post']")
        if post_buttons:
            post_buttons[0].click()

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
