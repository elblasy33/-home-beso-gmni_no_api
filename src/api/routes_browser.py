import asyncio
from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException

from src.models import BrowserStatusResponse
from src.engine.browser_manager import browser_manager

router = APIRouter(prefix="/api/browser", tags=["Browser Control"])

class ModeRequest(BaseModel):
    headless: bool

class LoginSessionRequest(BaseModel):
    url: str

@router.get("/status", response_model=BrowserStatusResponse)
async def get_browser_status():
    return await browser_manager.get_status()

@router.post("/mode")
async def toggle_browser_mode(req: ModeRequest):
    browser_manager.set_headless(req.headless)
    return {"headless": browser_manager.headless, "message": f"Browser mode set to {'Headless' if req.headless else 'Headed'}"}

@router.post("/login")
async def open_interactive_login(req: LoginSessionRequest):
    """
    Launches a Headed browser window pointing to the login page.
    The human operator can complete 2FA, OTP, or CAPTCHA manually.
    All cookies and state are saved automatically in the persistent context.
    """
    try:
        # Launch browser in headed mode for human interaction
        page = await browser_manager.new_page(headless=False)
        await page.goto(req.url, wait_until="domcontentloaded")
        browser_manager.record_action(f"Opened interactive login session for {req.url}")
        return {
            "status": "interactive_session_opened",
            "url": req.url,
            "message": "Browser opened in Headed mode. Complete login manually in the browser window."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/close")
async def close_browser_context():
    await browser_manager.close()
    return {"status": "closed", "message": "Browser persistent context closed"}
