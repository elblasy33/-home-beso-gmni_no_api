from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import uuid

class JobStatus(str, Enum):
    QUEUED = "queued"
    STARTING = "starting"
    LOGIN_REQUIRED = "login_required"
    NAVIGATING = "navigating"
    UPLOADING = "uploading"
    SENDING = "sending"
    WAITING_RESPONSE = "waiting_response"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class AttachmentTargetConfig(BaseModel):
    name: str = Field(..., description="Target identifier, e.g. document, image, file1")
    selector: str = Field(..., description="DOM CSS selector for the file input element")
    multiple: bool = Field(False, description="Whether this input allows multiple files")
    description: Optional[str] = Field(None, description="Human friendly label for the UI")

class ChatConfig(BaseModel):
    input_selector: str = Field(..., description="CSS selector for the text prompt input")
    send_selector: str = Field(..., description="CSS selector for the send/submit button")
    input_method: str = Field("fill", description="Method to enter text: 'fill', 'type', or 'press_enter'")

class ResponseConfig(BaseModel):
    selector: str = Field(..., description="CSS selector for the response message block")
    generating_selector: Optional[str] = Field(None, description="Selector present during generation (typing indicator/loader)")
    stop_selector: Optional[str] = Field(None, description="Selector present when generation can be cancelled/active")
    wait_until: str = Field("completed", description="'completed', 'networkidle', or 'text_stable'")
    timeout: int = Field(180, description="Max seconds to wait for complete response")
    min_length: int = Field(1, description="Minimum expected character length of response")

class AuthConfig(BaseModel):
    login_url: Optional[str] = Field(None, description="Direct URL to login page if different from target")
    check_selector: Optional[str] = Field(None, description="Selector present when authenticated (e.g. avatar, logout button)")
    login_required_selector: Optional[str] = Field(None, description="Selector indicating login is required (e.g. login form, captcha, 2fa)")
    auto_pause_for_human: bool = Field(True, description="Pause execution and notify UI when human authentication is required")

class SiteConfig(BaseModel):
    name: str = Field(..., description="Unique configuration identifier (e.g. mock_chat_site)")
    title: Optional[str] = Field(None, description="Display title for UI")
    url: str = Field(..., description="Target website URL")
    chat: ChatConfig
    attachments: List[AttachmentTargetConfig] = Field(default_factory=list)
    response: ResponseConfig
    auth: Optional[AuthConfig] = None

class AttachmentItem(BaseModel):
    filename: str
    target_name: str
    file_path: str
    size_bytes: int = 0

class LogLevel(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    SUCCESS = "SUCCESS"
    DEBUG = "DEBUG"

class LogEntry(BaseModel):
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    level: LogLevel = LogLevel.INFO
    step: str
    message: str

class Job(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    config_name: str
    url: str
    prompt: str
    status: JobStatus = JobStatus.QUEUED
    attachments: List[AttachmentItem] = Field(default_factory=list)
    logs: List[LogEntry] = Field(default_factory=list)
    response_text: Optional[str] = None
    error: Optional[str] = None
    screenshot_url: Optional[str] = None
    trace_url: Optional[str] = None
    debug_info: Dict[str, Any] = Field(default_factory=dict)

    def add_log(self, step: str, message: str, level: LogLevel = LogLevel.INFO):
        self.updated_at = datetime.now(timezone.utc).isoformat()
        entry = LogEntry(
            timestamp=self.updated_at,
            level=level,
            step=step,
            message=message
        )
        self.logs.append(entry)
        return entry

class BrowserStatusResponse(BaseModel):
    is_active: bool
    headless: bool
    profile_dir: str
    current_url: Optional[str] = None
    last_action: Optional[str] = None
    active_pages_count: int = 0
