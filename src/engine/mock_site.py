import asyncio
import os
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Request, Response, Form, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse

mock_router = APIRouter(prefix="/mock-site", tags=["Mock Target Site"])

# In-memory session store for mock authentication
VALID_SESSIONS = set()

MOCK_LOGIN_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mock AI Portal - Login</title>
    <style>
        :root {
            --bg: #0f172a;
            --card: #1e293b;
            --accent: #3b82f6;
            --text: #f8fafc;
            --text-dim: #94a3b8;
            --border: #334155;
        }
        body {
            font-family: system-ui, -apple-system, sans-serif;
            background: var(--bg);
            color: var(--text);
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            margin: 0;
        }
        .card {
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 32px;
            width: 100%;
            max-width: 400px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.5);
        }
        h2 { margin-top: 0; color: #60a5fa; }
        .form-group { margin-bottom: 18px; }
        label { display: block; font-size: 14px; margin-bottom: 6px; color: var(--text-dim); }
        input[type="text"], input[type="password"] {
            width: 100%;
            padding: 10px 12px;
            background: #0f172a;
            border: 1px solid var(--border);
            border-radius: 6px;
            color: white;
            box-sizing: border-box;
        }
        .btn {
            width: 100%;
            padding: 12px;
            background: var(--accent);
            border: none;
            border-radius: 6px;
            color: white;
            font-weight: 600;
            cursor: pointer;
            transition: background 0.2s;
        }
        .btn:hover { background: #2563eb; }
        .notice {
            background: #1e3a5f;
            border-left: 4px solid var(--accent);
            padding: 10px;
            margin-bottom: 20px;
            font-size: 13px;
        }
    </style>
</head>
<body>
    <div class="card" id="login-form-container">
        <h2>Mock AI Portal</h2>
        <div class="notice">
            <strong>Interactive Authentication Simulator:</strong><br>
            Enter any username & password, or enter OTP <code>123456</code> to verify human login flow.
        </div>
        <form method="POST" action="/mock-site/api/login">
            <div class="form-group">
                <label>Username / Email</label>
                <input type="text" id="login-username" name="username" value="demo_user" required>
            </div>
            <div class="form-group">
                <label>Password</label>
                <input type="password" id="login-password" name="password" value="demo_pass" required>
            </div>
            <div class="form-group">
                <label>Security 2FA / OTP (Optional Simulator)</label>
                <input type="text" id="login-otp" name="otp" placeholder="Enter 123456">
            </div>
            <button type="submit" id="login-submit-btn" class="btn">Sign In to Dashboard</button>
        </form>
    </div>
</body>
</html>
"""

MOCK_CHAT_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mock AI Assistant</title>
    <style>
        :root {
            --bg: #0b0f19;
            --panel: #111827;
            --card: #1f2937;
            --accent: #6366f1;
            --accent-hover: #4f46e5;
            --text: #f9fafb;
            --text-dim: #9ca3af;
            --border: #374151;
            --success: #10b981;
        }
        body {
            font-family: system-ui, -apple-system, sans-serif;
            background: var(--bg);
            color: var(--text);
            margin: 0;
            padding: 24px;
            display: flex;
            flex-direction: column;
            align-items: center;
        }
        .container {
            width: 100%;
            max-width: 900px;
        }
        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border);
            padding-bottom: 16px;
            margin-bottom: 24px;
        }
        .badge {
            background: #064e3b;
            color: #6ee7b7;
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 13px;
            font-weight: 500;
        }
        .upload-section {
            background: var(--panel);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 16px;
            margin-bottom: 20px;
        }
        .upload-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 16px;
            margin-top: 12px;
        }
        .upload-card {
            background: var(--card);
            border: 1px dashed var(--border);
            border-radius: 8px;
            padding: 14px;
            display: flex;
            flex-direction: column;
            gap: 8px;
        }
        .upload-card label {
            font-size: 13px;
            font-weight: 600;
            color: #a5b4fc;
        }
        .upload-card input[type="file"] {
            font-size: 12px;
            color: var(--text-dim);
        }
        .file-status {
            font-size: 12px;
            color: var(--success);
            min-height: 16px;
        }
        .chat-section {
            background: var(--panel);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 20px;
            display: flex;
            flex-direction: column;
            gap: 16px;
        }
        textarea#prompt-input {
            width: 100%;
            height: 110px;
            background: #0b0f19;
            border: 1px solid var(--border);
            border-radius: 8px;
            color: white;
            padding: 12px;
            font-size: 15px;
            box-sizing: border-box;
            resize: vertical;
        }
        .controls {
            display: flex;
            gap: 12px;
            justify-content: flex-end;
        }
        button#send-btn {
            background: var(--accent);
            color: white;
            border: none;
            padding: 10px 24px;
            border-radius: 6px;
            font-weight: 600;
            cursor: pointer;
        }
        button#send-btn:hover { background: var(--accent-hover); }
        button#stop-btn {
            background: #ef4444;
            color: white;
            border: none;
            padding: 10px 18px;
            border-radius: 6px;
            cursor: pointer;
            display: none;
        }
        .conversation {
            margin-top: 24px;
            display: flex;
            flex-direction: column;
            gap: 16px;
        }
        .assistant-message {
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 18px;
            line-height: 1.6;
        }
        .assistant-message.generating {
            border-color: var(--accent);
            animation: pulse 1.5s infinite;
        }
        .assistant-message.completed {
            border-color: #059669;
        }
        @keyframes pulse {
            0% { opacity: 0.7; }
            50% { opacity: 1; }
            100% { opacity: 0.7; }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h2>Mock AI Laboratory</h2>
            <div id="user-profile-badge" class="badge">● Authenticated Session</div>
        </header>

        <!-- Configurable Multi-Target File Upload Section -->
        <div class="upload-section">
            <h4 style="margin:0 0 8px 0;">Configured Attachment Inputs</h4>
            <div class="upload-grid">
                <!-- Target A: Document -->
                <div class="upload-card">
                    <label for="document-upload">Target: Document (#document-upload)</label>
                    <input type="file" id="document-upload" name="doc_file" onchange="markUploaded(this, 'doc-status')">
                    <div id="doc-status" class="file-status"></div>
                </div>
                <!-- Target B: Image -->
                <div class="upload-card">
                    <label for="image-upload">Target: Image (#image-upload)</label>
                    <input type="file" id="image-upload" name="img_file" onchange="markUploaded(this, 'img-status')">
                    <div id="img-status" class="file-status"></div>
                </div>
                <!-- Target C: Data -->
                <div class="upload-card">
                    <label for="data-upload">Target: Dataset (#data-upload)</label>
                    <input type="file" id="data-upload" name="data_file" onchange="markUploaded(this, 'data-status')">
                    <div id="data-status" class="file-status"></div>
                </div>
            </div>
        </div>

        <!-- Chat Input Section -->
        <div class="chat-section">
            <textarea id="prompt-input" placeholder="Type your prompt here... (e.g. Please analyze the attached files)"></textarea>
            <div class="controls">
                <button id="stop-btn" onclick="stopGeneration()">Stop</button>
                <button id="send-btn" onclick="triggerChat()">Send Message</button>
            </div>
        </div>

        <!-- Conversation Output Area -->
        <div class="conversation" id="conversation-container">
            <!-- Dynamically populated messages -->
        </div>
    </div>

    <script>
        function markUploaded(input, statusId) {
            const statusEl = document.getElementById(statusId);
            if (input.files && input.files.length > 0) {
                const names = Array.from(input.files).map(f => f.name).join(', ');
                statusEl.textContent = '✓ Attached: ' + names;
            } else {
                statusEl.textContent = '';
            }
        }

        let isGenerating = false;
        let generationTimer = null;

        function triggerChat() {
            const promptInput = document.getElementById('prompt-input');
            const promptText = promptInput.value.trim();
            if (!promptText) return;

            const docFile = document.getElementById('document-upload').files[0];
            const imgFile = document.getElementById('image-upload').files[0];
            const dataFile = document.getElementById('data-upload').files[0];

            const attachments = [];
            if (docFile) attachments.push({ target: 'document', name: docFile.name, size: docFile.size });
            if (imgFile) attachments.push({ target: 'image', name: imgFile.name, size: imgFile.size });
            if (dataFile) attachments.push({ target: 'data', name: dataFile.name, size: dataFile.size });

            const container = document.getElementById('conversation-container');
            
            // Create assistant message element with 'generating' status
            const msgEl = document.createElement('div');
            msgEl.className = 'assistant-message generating';
            msgEl.innerHTML = '<strong>Assistant:</strong> <em>Thinking and processing prompt...</em>';
            container.innerHTML = '';
            container.appendChild(msgEl);

            const sendBtn = document.getElementById('send-btn');
            const stopBtn = document.getElementById('stop-btn');
            sendBtn.disabled = true;
            stopBtn.style.display = 'inline-block';
            isGenerating = true;

            // Simulate streaming delay (1.5 seconds)
            generationTimer = setTimeout(() => {
                let reply = 'Here is the detailed response for your request:\\n\\n';
                reply += `Prompt: "${promptText}"\\n\\n`;
                if (attachments.length > 0) {
                    reply += 'Uploaded Attachments detected:\\n';
                    attachments.forEach((att, idx) => {
                        reply += `${idx + 1}. [${att.target}] ${att.name} (${att.size} bytes)\\n`;
                    });
                    reply += '\\nAll attachments were successfully verified and processed by the model.';
                } else {
                    reply += 'No attachments were uploaded with this prompt.';
                }

                msgEl.className = 'assistant-message completed';
                msgEl.innerHTML = '<strong>Assistant:</strong><br>' + reply.replace(/\\n/g, '<br>');
                sendBtn.disabled = false;
                stopBtn.style.display = 'none';
                isGenerating = false;
            }, 1500);
        }

        function stopGeneration() {
            if (generationTimer) clearTimeout(generationTimer);
            const msg = document.querySelector('.assistant-message.generating');
            if (msg) {
                msg.className = 'assistant-message completed';
                msg.innerHTML = '<strong>Assistant:</strong> <em>(Generation stopped by user)</em>';
            }
            document.getElementById('send-btn').disabled = false;
            document.getElementById('stop-btn').style.display = 'none';
            isGenerating = false;
        }
    </script>
</body>
</html>
"""

@mock_router.get("/login", response_class=HTMLResponse)
async def mock_login_page(request: Request):
    return HTMLResponse(content=MOCK_LOGIN_HTML)

@mock_router.post("/api/login")
async def mock_login_action(
    username: str = Form(...),
    password: str = Form(...),
    otp: Optional[str] = Form(None)
):
    token = f"session_{username}_{os.urandom(4).hex()}"
    VALID_SESSIONS.add(token)
    res = HTMLResponse(
        content="<script>alert('Login successful!'); window.location.href='/mock-site/chat';</script>"
    )
    res.set_cookie(key="mock_session", value=token, max_age=86400, httponly=False)
    return res

@mock_router.get("/chat", response_class=HTMLResponse)
async def mock_chat_page(request: Request):
    # Check session cookie
    token = request.cookies.get("mock_session")
    # If no session, allow simulation or render login redirect
    # If the user visits without session, they can still view or test login
    return HTMLResponse(content=MOCK_CHAT_HTML)

@mock_router.get("/api/status")
async def mock_status():
    return {"status": "ok", "active_sessions": len(VALID_SESSIONS)}
