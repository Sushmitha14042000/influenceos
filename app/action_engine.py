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
                self._tap_repost(driver)
            self._log(job_id, "Repost action completed")
        elif action == "share":
            if driver:
                self._tap_share(driver)
            self._log(job_id, "Share action completed")
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
    def _tap_like(driver: Any) -> None:
        id_candidates = [
            "com.instagram.android:id/row_feed_button_like",
        ]
        xpath_candidates = [
            "//android.widget.ImageView[contains(@content-desc,'Like')]",
            "//android.widget.Button[contains(@content-desc,'Like')]",
            "//*[contains(@content-desc,'Like')]",
        ]

        last_error: Exception | None = None
        for _ in range(4):
            for element_id in id_candidates:
                elems = driver.find_elements("id", element_id)
                if elems:
                    try:
                        ActionEngine._tap_element(driver, elems[0])
                        return
                    except Exception as exc:
                        last_error = exc

            for xpath in xpath_candidates:
                elems = driver.find_elements("xpath", xpath)
                if elems:
                    try:
                        ActionEngine._tap_element(driver, elems[0])
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
        # After comment flow, keyboard/sheet can block repost controls.
        ActionEngine._navigate_back(driver, attempts=2, delay=0.8)

        xpath_candidates = [
            "(//android.widget.Button[@resource-id='com.instagram.android:id/reposts_ufi_icon']/android.view.ViewGroup/android.widget.ImageView)",
            "//*[@resource-id='com.instagram.android:id/reposts_ufi_icon']",
            "//*[contains(@content-desc,'Repost')]",
        ]

        last_error: Exception | None = None
        for _ in range(4):
            for xpath in xpath_candidates:
                elems = driver.find_elements("xpath", xpath)
                if elems:
                    try:
                        ActionEngine._tap_element(driver, elems[0])
                        # Close repost sheet and return to the post screen.
                        try:
                            time.sleep(0.6)
                            driver.back()
                        except Exception:
                            pass
                        return
                    except Exception as exc:
                        last_error = exc
            time.sleep(0.35)

        if last_error:
            raise RuntimeError(f"Repost button found but click failed: {last_error}") from last_error
        raise RuntimeError("Repost button not found on current screen")

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
        # Try proven Instagram comment button id first.
        opener_tapped = False
        try:
            comment_btn = driver.find_element("id", "com.instagram.android:id/row_feed_button_comment")
            ActionEngine._tap_element(driver, comment_btn)
            opener_tapped = True
        except Exception:
            pass

        if not opener_tapped:
            comment_openers = [
                "//android.widget.ImageView[contains(@content-desc,'Comment')]",
                "//android.widget.Button[contains(@content-desc,'Comment')]",
                "//*[contains(@content-desc,'Comment')]",
                "//*[contains(@text,'Comment')]",
            ]
            for _ in range(4):
                for xpath in comment_openers:
                    elems = driver.find_elements("xpath", xpath)
                    if elems:
                        try:
                            ActionEngine._tap_element(driver, elems[0])
                            opener_tapped = True
                            break
                        except Exception:
                            continue
                if opener_tapped:
                    break
                time.sleep(0.35)

        if not opener_tapped:
            raise RuntimeError("Comment button not found or not tappable")

        # Some Instagram builds open a bottom sheet where we must tap
        # "Add a comment..." before an EditText appears.
        composer_triggers = [
            "//*[contains(@text,'Add a comment')]",
            "//*[contains(@content-desc,'Add a comment')]",
            "//*[contains(@text,'Write a comment')]",
            "//*[contains(@content-desc,'Write a comment')]",
        ]
        for xpath in composer_triggers:
            elems = driver.find_elements("xpath", xpath)
            if elems:
                try:
                    ActionEngine._tap_element(driver, elems[0])
                    break
                except Exception:
                    continue

        editable_candidates = [
            "//android.widget.EditText[@enabled='true']",
            "//*[@class='android.widget.EditText' and @enabled='true']",
            "//*[contains(@resource-id,'comment') and self::android.widget.EditText and @enabled='true']",
        ]
        fallback_candidates = [
            "//*[@focusable='true' and @enabled='true' and (self::android.widget.EditText or self::android.widget.TextView)]",
        ]

        typed = False
        last_type_error: Exception | None = None

        # If keyboard is already up, active element is often the true input field.
        try:
            active = driver.switch_to.active_element
            active.send_keys(text)
            typed = True
        except Exception as exc:
            last_type_error = exc

        for _ in range(8):
            if typed:
                break
            candidate_groups = [editable_candidates, fallback_candidates]
            for group in candidate_groups:
                for xpath in group:
                    elements = driver.find_elements("xpath", xpath)
                    for element in elements:
                        try:
                            ActionEngine._tap_element(driver, element)
                        except Exception:
                            # Keep trying; some elements are visible but not tappable.
                            pass
                        try:
                            element.clear()
                        except Exception:
                            pass
                        try:
                            element.send_keys(text)
                            typed = True
                            break
                        except Exception as exc:
                            last_type_error = exc
                    if typed:
                        break
                if typed:
                    break
            if typed:
                break
            time.sleep(0.3)

        if not typed:
            if last_type_error:
                raise RuntimeError(f"Comment input found but not editable: {last_type_error}") from last_type_error
            raise RuntimeError("Comment input box not found")

        submit_candidates = [
            ("accessibility id", "Post"),
            "//android.widget.Button[@text='Post']",
            "//android.widget.TextView[@text='Post']",
            "//*[contains(@content-desc,'Post')]",
            "//*[contains(@text,'Post')]",
        ]
        for _ in range(4):
            # Accessibility id path.
            try:
                post_btn = driver.find_element("accessibility id", "Post")
                ActionEngine._tap_element(driver, post_btn)
                time.sleep(0.8)
                ActionEngine._navigate_back(driver, attempts=2, delay=0.6)
                return
            except Exception:
                pass

            for xpath in submit_candidates[1:]:
                elems = driver.find_elements("xpath", xpath)
                if elems:
                    try:
                        ActionEngine._tap_element(driver, elems[0])
                        time.sleep(0.8)
                        ActionEngine._navigate_back(driver, attempts=2, delay=0.6)
                        return
                    except Exception:
                        continue
            time.sleep(0.3)

        raise RuntimeError("Post comment submit button not found or not tappable")

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
