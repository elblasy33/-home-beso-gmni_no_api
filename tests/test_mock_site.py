import pytest
from httpx import AsyncClient, ASGITransport
from src.app import app

@pytest.mark.asyncio
async def test_mock_site_pages():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Check login page loads
        resp = await client.get("/mock-site/login")
        assert resp.status_code == 200
        assert "login-form-container" in resp.text
        assert "Security 2FA / OTP" in resp.text

        # Check chat page loads
        resp_chat = await client.get("/mock-site/chat")
        assert resp_chat.status_code == 200
        assert "document-upload" in resp_chat.text
        assert "image-upload" in resp_chat.text
        assert "data-upload" in resp_chat.text
        assert "prompt-input" in resp_chat.text
        assert "send-btn" in resp_chat.text

@pytest.mark.asyncio
async def test_mock_login_action():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/mock-site/api/login",
            data={"username": "testuser", "password": "secretpassword", "otp": "123456"}
        )
        assert resp.status_code == 200
        assert "mock_session" in resp.cookies
