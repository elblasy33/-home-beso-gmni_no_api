import asyncio
import os
from pathlib import Path
from typing import Optional, List, Dict, Any
from playwright.async_api import async_playwright, BrowserContext, Page, Playwright

from src.config import settings
from src.models import BrowserStatusResponse

class BrowserManager:
    def __init__(self):
        self._playwright: Optional[Playwright] = None
        self._context: Optional[BrowserContext] = None
        self._headless: bool = settings.HEADLESS
        self._active_page: Optional[Page] = None
        self._last_action: Optional[str] = "Initialized"
        self._lock = asyncio.Lock()

    @property
    def is_active(self) -> bool:
        return self._context is not None

    @property
    def headless(self) -> bool:
        return self._headless

    def set_headless(self, headless: bool):
        self._headless = headless

    async def get_or_create_context(self, headless: Optional[bool] = None) -> BrowserContext:
        """Get the active persistent context, or create a new one."""
        async with self._lock:
            target_headless = self._headless if headless is None else headless
            
            # If context exists and headless setting matches, verify it's still alive
            if self._context is not None:
                try:
                    # Test if context is still open
                    pages = self._context.pages
                    if self._headless == target_headless:
                        return self._context
                except Exception:
                    pass
                # Close mismatching or dead context
                await self._close_internal()

            self._headless = target_headless
            if self._playwright is None:
                self._playwright = await async_playwright().start()

            profile_dir = Path(settings.BROWSER_PROFILE_DIR)
            profile_dir.mkdir(parents=True, exist_ok=True)

            # Clean stale singleton locks if browser isn't running
            for lock_name in ["SingletonLock", "SingletonCookie", "SingletonSocket"]:
                lock_file = profile_dir / lock_name
                if lock_file.exists():
                    try:
                        if lock_file.is_symlink() or lock_file.is_file():
                            lock_file.unlink()
                    except Exception:
                        pass

            # Launch persistent context
            self._context = await self._playwright.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                headless=self._headless,
                viewport={"width": 1280, "height": 800},
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-infobars",
                ],
                user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                ),
            )

            # Auto-cleanup when user closes the browser window manually
            self._context.on("close", lambda: self._on_context_closed())

            if settings.ENABLE_TRACING:
                try:
                    await self._context.tracing.start(
                        screenshots=True, snapshots=True, sources=True
                    )
                except Exception as e:
                    print(f"Warning: Failed to start tracing: {e}")

            self._last_action = "Launched persistent browser context"
            return self._context

    def _on_context_closed(self):
        """Callback when Chromium is closed by user or system."""
        self._context = None
        self._active_page = None
        self._last_action = "Browser window closed by operator"

    async def new_page(self, headless: Optional[bool] = None) -> Page:
        """Create or get a usable page in the persistent context with self-healing."""
        for attempt in range(2):
            try:
                context = await self.get_or_create_context(headless=headless)
                page = None
                for p in context.pages:
                    if not p.is_closed():
                        page = p
                        break
                if page is None:
                    page = await context.new_page()

                self._active_page = page

                # Hook console messages and errors
                page.on("console", lambda msg: print(f"[Browser Console] {msg.type}: {msg.text}"))
                page.on("pageerror", lambda err: print(f"[Browser PageError] {err}"))

                return page
            except Exception as e:
                print(f"Retrying new_page due to error: {e}")
                await self.close()
                if attempt == 1:
                    raise e

    async def take_screenshot(self, page: Page, name: str) -> str:
        """Capture screenshot and save to artifacts directory, returning relative URL."""
        artifacts_dir = Path(settings.ARTIFACTS_DIR)
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{name}.png"
        filepath = artifacts_dir / filename
        await page.screenshot(path=str(filepath), full_page=True)
        return f"/artifacts/{filename}"

    async def stop_tracing(self, name: str) -> Optional[str]:
        """Stop tracing and return relative path if enabled."""
        if not settings.ENABLE_TRACING or not self._context:
            return None
        artifacts_dir = Path(settings.ARTIFACTS_DIR)
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        trace_file = artifacts_dir / f"{name}_trace.zip"
        try:
            await self._context.tracing.stop(path=str(trace_file))
            return f"/artifacts/{trace_file.name}"
        except Exception as e:
            print(f"Warning: Failed to save trace: {e}")
            return None

    async def close(self):
        """Public method to close context cleanly."""
        async with self._lock:
            await self._close_internal()

    async def _close_internal(self):
        if self._context:
            try:
                await self._context.close()
            except Exception as e:
                print(f"Warning closing browser context: {e}")
            self._context = None
            self._active_page = None

        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception as e:
                print(f"Warning stopping playwright: {e}")
            self._playwright = None

        self._last_action = "Browser context closed"

    async def get_status(self) -> BrowserStatusResponse:
        """Return real-time browser status info."""
        current_url = None
        active_pages = 0
        if self._context:
            try:
                active_pages = len(self._context.pages)
                if self._active_page and not self._active_page.is_closed():
                    current_url = self._active_page.url
            except Exception:
                pass

        return BrowserStatusResponse(
            is_active=self.is_active,
            headless=self._headless,
            profile_dir=settings.BROWSER_PROFILE_DIR,
            current_url=current_url,
            last_action=self._last_action,
            active_pages_count=active_pages,
        )

    def record_action(self, action: str):
        self._last_action = action

browser_manager = BrowserManager()
