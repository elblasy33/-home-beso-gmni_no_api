import asyncio
import os
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Callable

from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from src.config import settings
from src.models import Job, JobStatus, LogLevel, SiteConfig
from src.engine.browser_manager import browser_manager

class AutomationAgent:
    def __init__(self):
        self.browser_manager = browser_manager

    async def run_job(
        self,
        job: Job,
        config: SiteConfig,
        resume_event: Optional[asyncio.Event] = None,
        on_update: Optional[Callable[[Job], None]] = None
    ) -> Job:
        """Executes a complete automation workflow for a single job."""
        page: Optional[Page] = None

        def notify(step: str, message: str, level: LogLevel = LogLevel.INFO):
            job.add_log(step=step, message=message, level=level)
            self.browser_manager.record_action(f"[{job.id[:8]}] {step}: {message}")
            if on_update:
                on_update(job)

        try:
            # Step 1: Initialize Browser
            job.status = JobStatus.STARTING
            notify("Starting", "Initializing persistent browser profile...", LogLevel.INFO)
            page = await self.browser_manager.new_page()

            # Step 2: Navigate to URL
            job.status = JobStatus.NAVIGATING
            notify("Navigating", f"Navigating to {job.url}...", LogLevel.INFO)
            await page.goto(job.url, wait_until="domcontentloaded", timeout=settings.DEFAULT_PAGE_TIMEOUT * 1000)
            await page.wait_for_timeout(1000)  # Brief stabilization

            # Step 3: Check Authentication / 2FA / CAPTCHA
            if config.auth and (config.auth.login_required_selector or config.auth.check_selector):
                notify("Auth Check", "Verifying authentication state...", LogLevel.INFO)
                is_login_needed = False

                if config.auth.login_required_selector:
                    try:
                        login_el = page.locator(config.auth.login_required_selector).first
                        if await login_el.is_visible(timeout=3000):
                            is_login_needed = True
                    except Exception:
                        pass

                if config.auth.check_selector and not is_login_needed:
                    try:
                        auth_el = page.locator(config.auth.check_selector).first
                        if not await auth_el.is_visible(timeout=3000):
                            is_login_needed = True
                    except Exception:
                        is_login_needed = True

                if is_login_needed:
                    job.status = JobStatus.LOGIN_REQUIRED
                    screenshot_url = await self.browser_manager.take_screenshot(page, f"job_{job.id}_auth_required")
                    job.screenshot_url = screenshot_url
                    notify(
                        "Login Required",
                        "Human login / OTP / 2FA / CAPTCHA required. Execution paused. "
                        "Please authenticate in browser and click 'Resume / Confirm Login'.",
                        LogLevel.WARNING
                    )
                    if resume_event:
                        # Wait for human interaction confirmation via API
                        try:
                            # 5 minutes timeout for human interaction
                            await asyncio.wait_for(resume_event.wait(), timeout=300)
                            notify("Auth Resumed", "Operator confirmed login. Continuing workflow...", LogLevel.SUCCESS)
                            # Re-navigate or refresh target if needed
                            await page.goto(job.url, wait_until="domcontentloaded", timeout=settings.DEFAULT_PAGE_TIMEOUT * 1000)
                            await page.wait_for_timeout(1000)
                        except asyncio.TimeoutError:
                            raise RuntimeError("Authentication timeout: User did not confirm login within 5 minutes.")

            # Step 4: Handle Multi-Target File Uploads
            if job.attachments:
                job.status = JobStatus.UPLOADING
                notify("Uploading", f"Processing {len(job.attachments)} attachment(s)...", LogLevel.INFO)

                # Create mapping from target name -> selector
                targets_map = {t.name: t.selector for t in config.attachments}

                for att in job.attachments:
                    selector = targets_map.get(att.target_name)
                    if not selector:
                        # Fallback to first available attachment selector or generic file input
                        if config.attachments:
                            selector = config.attachments[0].selector
                        else:
                            selector = "input[type='file']"
                        notify("Uploading", f"Target '{att.target_name}' not found in config, using fallback: {selector}", LogLevel.WARNING)

                    notify("Uploading", f"Uploading '{att.filename}' to target [{att.target_name}] ({selector})...", LogLevel.INFO)
                    
                    file_path = Path(att.file_path)
                    if not file_path.exists():
                        raise FileNotFoundError(f"Attachment file not found at {att.file_path}")

                    # Locate file input
                    file_input = page.locator(selector).first
                    if not await file_input.count():
                        # Many modern AI portals (like Gemini) mount input[type=file] only after clicking the upload button
                        trigger_btn = page.locator(
                            "button[aria-label*='Upload & tools'], button[aria-label*='Upload'], button[aria-label*='Add files'], button[aria-label*='Add image'], button[aria-label*='Attach']"
                        ).first
                        if await trigger_btn.count() and await trigger_btn.is_visible():
                            notify("Uploading", "Opening upload drawer...", LogLevel.INFO)
                            await trigger_btn.click()
                            await page.wait_for_timeout(1000)

                    await file_input.wait_for(state="attached", timeout=12000)
                    await file_input.set_input_files(str(file_path.resolve()))
                    notify("Uploading", f"File '{att.filename}' set. Waiting for upload preview...", LogLevel.INFO)
                    await page.wait_for_timeout(2500)
                    notify("Uploading", f"Successfully set file '{att.filename}' on [{selector}]", LogLevel.SUCCESS)

            # Step 5: Enter Prompt & Send Message
            job.status = JobStatus.SENDING
            notify("Sending", f"Entering prompt into '{config.chat.input_selector}'...", LogLevel.INFO)
            
            chat_input = page.locator(config.chat.input_selector).first
            await chat_input.wait_for(state="visible", timeout=15000)
            await chat_input.click()

            if config.chat.input_method == "type":
                await chat_input.press_sequentially(job.prompt, delay=15)
            elif config.chat.input_method == "press_enter":
                try:
                    await chat_input.fill(job.prompt)
                except Exception:
                    await page.keyboard.insert_text(job.prompt)
                await page.keyboard.press("Enter")
            else:
                # Default fill with fallback for rich-text / contenteditable
                try:
                    await chat_input.fill(job.prompt)
                except Exception:
                    await page.keyboard.insert_text(job.prompt)

            await page.wait_for_timeout(500)

            # Click send button or press enter
            if config.chat.input_method != "press_enter":
                try:
                    send_btn = page.locator(config.chat.send_selector).first
                    await send_btn.wait_for(state="visible", timeout=8000)
                    await send_btn.click()
                    notify("Sending", f"Clicked send button '{config.chat.send_selector}'", LogLevel.INFO)
                except Exception as click_err:
                    notify("Sending", f"Send button click failed, attempting Enter key: {click_err}", LogLevel.WARNING)
                    await page.keyboard.press("Enter")
                    notify("Sending", "Dispatched message via Enter key.", LogLevel.INFO)

            # Step 6: Wait for and Detect Response
            job.status = JobStatus.WAITING_RESPONSE
            notify("Waiting Response", "Message dispatched. Waiting for response to start...", LogLevel.INFO)

            response_cfg = config.response
            timeout_ms = response_cfg.timeout * 1000

            # If generating selector is configured, optionally wait for it to appear
            if response_cfg.generating_selector:
                try:
                    gen_locator = page.locator(response_cfg.generating_selector).first
                    await gen_locator.wait_for(state="visible", timeout=8000)
                    notify("Waiting Response", "Detected model generating response...", LogLevel.INFO)
                    # Now wait for it to disappear / complete
                    await gen_locator.wait_for(state="hidden", timeout=timeout_ms)
                    notify("Waiting Response", "Generation indicator disappeared (generation finished).", LogLevel.INFO)
                except Exception as e:
                    notify("Waiting Response", f"Generating selector wait skipped or completed: {e}", LogLevel.DEBUG)

            # Wait for response element to be visible
            resp_locator = page.locator(response_cfg.selector).last
            await resp_locator.wait_for(state="visible", timeout=timeout_ms)

            # Detect stability of text (ensure streaming has finished)
            last_text = ""
            stable_count = 0
            for _ in range(60): # up to 30 seconds of stability checks
                try:
                    current_text = (await resp_locator.inner_text()).strip()
                    if current_text and current_text == last_text and len(current_text) >= response_cfg.min_length:
                        stable_count += 1
                        if stable_count >= 2:
                            break
                    else:
                        stable_count = 0
                        last_text = current_text
                except Exception:
                    pass
                await asyncio.sleep(0.5)

            # Step 7: Extract Response
            extracted_text = (await resp_locator.inner_text()).strip()
            job.response_text = extracted_text
            notify("Completed", f"Extracted response ({len(extracted_text)} characters)", LogLevel.SUCCESS)

            # Take final success screenshot
            screenshot_url = await self.browser_manager.take_screenshot(page, f"job_{job.id}_success")
            job.screenshot_url = screenshot_url
            job.status = JobStatus.COMPLETED

            # Trace
            trace_url = await self.browser_manager.stop_tracing(f"job_{job.id}")
            if trace_url:
                job.trace_url = trace_url

        except Exception as err:
            err_msg = str(err)
            job.status = JobStatus.FAILED
            job.error = err_msg
            job.debug_info["traceback"] = traceback.format_exc()
            notify("Error", f"Execution failed: {err_msg}", LogLevel.ERROR)

            if page:
                try:
                    err_screenshot = await self.browser_manager.take_screenshot(page, f"job_{job.id}_error")
                    job.screenshot_url = err_screenshot
                except Exception as ss_err:
                    notify("Error", f"Could not capture error screenshot: {ss_err}", LogLevel.DEBUG)

        finally:
            if on_update:
                on_update(job)

        return job

automation_agent = AutomationAgent()
