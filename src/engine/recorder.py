import asyncio
from typing import Dict, Any, Optional, List
from playwright.async_api import Page

from src.engine.browser_manager import browser_manager
from src.models import SiteConfig, ChatConfig, ResponseConfig, AttachmentTargetConfig, AuthConfig
from src.config_manager import config_manager

INSPECTOR_SCRIPT = """
(() => {
    if (window.__RECORDER_INSTALLED__) return;
    window.__RECORDER_INSTALLED__ = true;
    window.__RECORDED_EVENTS__ = {
        url: window.location.href,
        inputs: [],
        file_inputs: [],
        clicks: [],
        potential_responses: []
    };

    function getUniqueSelector(el) {
        if (!el || el.nodeType !== 1) return '';
        if (el.id) return '#' + CSS.escape(el.id);
        
        let path = [];
        while (el && el.nodeType === 1) {
            let selector = el.nodeName.toLowerCase();
            if (el.id) {
                selector = '#' + CSS.escape(el.id);
                path.unshift(selector);
                break;
            } else {
                let sibling = el, nth = 1;
                while (sibling = sibling.previousElementSibling) {
                    if (sibling.nodeName.toLowerCase() === selector) nth++;
                }
                if (nth !== 1) selector += ":nth-of-type(" + nth + ")";
            }
            path.unshift(selector);
            el = el.parentElement;
        }
        return path.join(' > ');
    }

    // Auto-detect existing file inputs
    document.querySelectorAll('input[type="file"]').forEach(el => {
        let sel = el.id ? '#' + el.id : (el.name ? `input[name="${el.name}"]` : getUniqueSelector(el));
        window.__RECORDED_EVENTS__.file_inputs.push({
            selector: sel,
            id: el.id,
            name: el.name
        });
    });

    // Listen to focus and input
    document.addEventListener('focusin', (e) => {
        const target = e.target;
        if (target.matches('textarea, input[type="text"], [contenteditable="true"]')) {
            const sel = getUniqueSelector(target);
            if (!window.__RECORDED_EVENTS__.inputs.includes(sel)) {
                window.__RECORDED_EVENTS__.inputs.push(sel);
            }
        } else if (target.matches('input[type="file"]')) {
            const sel = getUniqueSelector(target);
            if (!window.__RECORDED_EVENTS__.file_inputs.some(f => f.selector === sel)) {
                window.__RECORDED_EVENTS__.file_inputs.push({ selector: sel, id: target.id, name: target.name });
            }
        }
    }, true);

    // Listen to clicks
    document.addEventListener('click', (e) => {
        const btn = e.target.closest('button, input[type="submit"], [role="button"]');
        if (btn) {
            const sel = getUniqueSelector(btn);
            window.__RECORDED_EVENTS__.clicks.push({
                selector: sel,
                text: btn.innerText ? btn.innerText.trim().slice(0, 30) : ''
            });
        }
    }, true);

    // Observe potential response containers
    const observer = new MutationObserver((mutations) => {
        for (const m of mutations) {
            if (m.target && m.target.nodeType === 1 && m.addedNodes.length > 0) {
                const sel = getUniqueSelector(m.target);
                if (sel && !window.__RECORDED_EVENTS__.potential_responses.includes(sel)) {
                    window.__RECORDED_EVENTS__.potential_responses.push(sel);
                }
            }
        }
    });
    observer.observe(document.body, { childList: true, subtree: true });
})();
"""

class SiteRecorder:
    def __init__(self):
        self._active_session: bool = False
        self._page: Optional[Page] = None
        self._last_url: Optional[str] = None

    @property
    def is_recording(self) -> bool:
        return self._active_session and self._page is not None and not self._page.is_closed()

    async def start_recording(self, target_url: str, headed: bool = True) -> Dict[str, Any]:
        """Launches a browser session with recording script injected."""
        self._page = await browser_manager.new_page(headless=not headed)
        self._active_session = True
        self._last_url = target_url

        await self._page.goto(target_url, wait_until="domcontentloaded")
        await self._inject_inspector()

        return {
            "status": "recording_started",
            "url": target_url,
            "headed": headed,
            "message": "Interact with the target website. The recorder tracks inputs, file targets, and buttons."
        }

    async def _inject_inspector(self):
        if self._page and not self._page.is_closed():
            await self._page.evaluate(INSPECTOR_SCRIPT)

    async def get_recorded_events(self) -> Dict[str, Any]:
        """Retrieves currently recorded DOM events from the active browser page."""
        if not self.is_recording:
            return {"status": "inactive", "events": None}

        try:
            await self._inject_inspector()
            events = await self._page.evaluate("() => window.__RECORDED_EVENTS__ || {}")
            events["current_url"] = self._page.url
            return {"status": "active", "events": events}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def generate_configuration(self, config_name: str, site_title: Optional[str] = None) -> SiteConfig:
        """Synthesizes recorded interactions into a clean SiteConfig YAML."""
        recorded_info = await self.get_recorded_events()
        events = recorded_info.get("events") or {}

        url = events.get("current_url") or self._last_url or "https://example.com"
        
        # Determine chat input selector
        inputs = events.get("inputs") or []
        chat_input = inputs[-1] if inputs else "textarea"

        # Determine send button
        clicks = events.get("clicks") or []
        send_btn = clicks[-1]["selector"] if clicks else "button[type='submit']"

        # Determine file upload inputs
        file_inputs = events.get("file_inputs") or []
        attachments = []
        for idx, fi in enumerate(file_inputs):
            name = fi.get("id") or fi.get("name") or f"file{idx+1}"
            name = name.replace("#", "").replace("-", "_").lower()
            attachments.append(AttachmentTargetConfig(
                name=name,
                selector=fi["selector"],
                multiple=False,
                description=f"Target: {name}"
            ))

        if not attachments:
            attachments.append(AttachmentTargetConfig(
                name="file1",
                selector="input[type='file']",
                multiple=False,
                description="Default file upload"
            ))

        # Determine response container
        potential_resps = events.get("potential_responses") or []
        resp_selector = potential_resps[-1] if potential_resps else ".assistant-response"

        new_config = SiteConfig(
            name=config_name,
            title=site_title or config_name.replace("_", " ").title(),
            url=url,
            chat=ChatConfig(
                input_selector=chat_input,
                send_selector=send_btn,
                input_method="fill"
            ),
            attachments=attachments,
            response=ResponseConfig(
                selector=resp_selector,
                wait_until="completed",
                timeout=180
            ),
            auth=AuthConfig(
                auto_pause_for_human=True
            )
        )

        # Save to YAML
        config_manager.save_config(config_name, new_config.model_dump())
        return new_config

    async def stop_recording(self):
        self._active_session = False
        self._page = None

site_recorder = SiteRecorder()
