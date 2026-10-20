import pytest
import threading
import time
import urllib.request
from pathlib import Path
import uvicorn

from src.app import create_app
from src.models import Job, AttachmentItem, SiteConfig, ChatConfig, ResponseConfig, AttachmentTargetConfig, JobStatus
from src.engine.automation_agent import automation_agent
from src.engine.browser_manager import browser_manager

TEST_PORT = 8899

@pytest.fixture(scope="module")
def mock_server():
    """Starts the FastAPI application on a dedicated test port in a background thread."""
    server_app = create_app()
    server_config = uvicorn.Config(server_app, host="127.0.0.1", port=TEST_PORT, log_level="error")
    server = uvicorn.Server(server_config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    # Wait until server responds
    for _ in range(30):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{TEST_PORT}/mock-site/api/status", timeout=1) as resp:
                if resp.status == 200:
                    break
        except Exception:
            time.sleep(0.2)
    else:
        raise RuntimeError("Test server failed to start within timeout")

    yield f"http://127.0.0.1:{TEST_PORT}"

    server.should_exit = True
    thread.join(timeout=2)

@pytest.mark.asyncio
async def test_full_automation_workflow(mock_server, tmp_path):
    """
    Tests the complete end-to-end automation workflow:
    1. Spawns persistent browser context in headless mode.
    2. Navigates to mock site chat page.
    3. Multi-uploads distinct files to distinct target selectors (#document-upload, #image-upload).
    4. Fills prompt and triggers send.
    5. Detects streaming/generating indicator.
    6. Waits for completion and extracts response text.
    """
    # Create sample files
    doc_file = tmp_path / "sample_contract.txt"
    doc_file.write_text("Confidential NDA Agreement terms...")

    img_file = tmp_path / "diagram.png"
    img_file.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82")

    config = SiteConfig(
        name="test_mock_site",
        title="Test Mock Site",
        url=f"{mock_server}/mock-site/chat",
        chat=ChatConfig(
            input_selector="textarea#prompt-input",
            send_selector="button#send-btn",
            input_method="fill"
        ),
        attachments=[
            AttachmentTargetConfig(
                name="document",
                selector="input#document-upload",
                multiple=False,
                description="Doc upload"
            ),
            AttachmentTargetConfig(
                name="image",
                selector="input#image-upload",
                multiple=False,
                description="Image upload"
            )
        ],
        response=ResponseConfig(
            selector=".assistant-message.completed",
            generating_selector=".assistant-message.generating",
            stop_selector="button#stop-btn",
            wait_until="completed",
            timeout=30,
            min_length=10
        )
    )

    job = Job(
        config_name="test_mock_site",
        url=f"{mock_server}/mock-site/chat",
        prompt="Please summarize the attached contract and explain the architecture diagram."
    )

    job.attachments = [
        AttachmentItem(
            filename="sample_contract.txt",
            target_name="document",
            file_path=str(doc_file.resolve()),
            size_bytes=doc_file.stat().st_size
        ),
        AttachmentItem(
            filename="diagram.png",
            target_name="image",
            file_path=str(img_file.resolve()),
            size_bytes=img_file.stat().st_size
        )
    ]

    # Force headless for automated test
    browser_manager.set_headless(True)

    # Execute workflow
    result_job = await automation_agent.run_job(job=job, config=config)

    # Assertions
    assert result_job.status == JobStatus.COMPLETED, f"Job failed with error: {result_job.error}"
    assert result_job.response_text is not None
    assert "Please summarize the attached contract" in result_job.response_text
    assert "sample_contract.txt" in result_job.response_text
    assert "diagram.png" in result_job.response_text
    assert result_job.screenshot_url is not None

    # Clean up browser
    await browser_manager.close()

@pytest.mark.asyncio
async def test_human_in_the_loop_login_flow(mock_server):
    """
    Tests Human-in-the-loop authentication pause & resume:
    1. Navigation hits a page requiring login/2FA (#login-form-container).
    2. Agent detects requirement and transitions to JobStatus.LOGIN_REQUIRED.
    3. Workflow pauses safely without failing or using brittle captcha bypasses.
    4. Operator confirms login (resume_event.set()).
    5. Agent resumes and continues workflow.
    """
    from src.models import AuthConfig
    import asyncio

    config = SiteConfig(
        name="test_login_pause",
        title="Test Login Pause",
        url=f"{mock_server}/mock-site/chat",
        chat=ChatConfig(
            input_selector="textarea#prompt-input",
            send_selector="button#send-btn",
            input_method="fill"
        ),
        attachments=[],
        response=ResponseConfig(
            selector=".assistant-message.completed",
            generating_selector=".assistant-message.generating",
            wait_until="completed",
            timeout=30,
            min_length=5
        ),
        auth=AuthConfig(
            login_url=f"{mock_server}/mock-site/login",
            login_required_selector="#login-form-container",
            auto_pause_for_human=True
        )
    )

    # Direct job to login URL initially to trigger auth requirement
    job = Job(
        config_name="test_login_pause",
        url=f"{mock_server}/mock-site/login",
        prompt="Hello after authentication!"
    )

    resume_event = asyncio.Event()

    async def simulate_human_login():
        # Wait until job enters LOGIN_REQUIRED (up to 30 seconds)
        for _ in range(150):
            if job.status == JobStatus.LOGIN_REQUIRED:
                break
            await asyncio.sleep(0.2)
        
        assert job.status == JobStatus.LOGIN_REQUIRED, f"Job did not enter LOGIN_REQUIRED, status was: {job.status}"
        assert any("human login" in log.message.lower() for log in job.logs)
        # Operator completes authentication, changes URL to chat
        job.url = f"{mock_server}/mock-site/chat"
        # Operator clicks "Resume / Confirm Login"
        resume_event.set()

    # Run operator simulation concurrently
    sim_task = asyncio.create_task(simulate_human_login())

    browser_manager.set_headless(True)
    res_job = await automation_agent.run_job(job=job, config=config, resume_event=resume_event)
    await sim_task

    assert res_job.status == JobStatus.COMPLETED
    assert "Hello after authentication!" in res_job.response_text
    await browser_manager.close()

