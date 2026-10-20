import os
from pathlib import Path
from typing import Dict, List, Optional
import yaml
from pydantic import ValidationError

from src.config import settings
from src.models import SiteConfig, ChatConfig, ResponseConfig, AttachmentTargetConfig, AuthConfig

class ConfigManager:
    def __init__(self, configs_dir: Optional[str] = None):
        self.configs_dir = Path(configs_dir or settings.CONFIGS_DIR)
        self.configs_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_default_configs()

    def _ensure_default_configs(self):
        """Create sample configurations if not already present."""
        mock_config_path = self.configs_dir / "mock_site.yaml"
        if not mock_config_path.exists():
            mock_config = {
                "name": "mock_site",
                "title": "Local Mock AI Chat Site",
                "url": f"http://localhost:{settings.APP_PORT}/mock-site/chat",
                "chat": {
                    "input_selector": "textarea#prompt-input",
                    "send_selector": "button#send-btn",
                    "input_method": "fill"
                },
                "attachments": [
                    {
                        "name": "document",
                        "selector": "input#document-upload",
                        "multiple": False,
                        "description": "Primary Document (PDF, TXT, DOCX)"
                    },
                    {
                        "name": "image",
                        "selector": "input#image-upload",
                        "multiple": False,
                        "description": "Reference Image (PNG, JPG, WEBP)"
                    },
                    {
                        "name": "data",
                        "selector": "input#data-upload",
                        "multiple": False,
                        "description": "Dataset / Spreadsheet (CSV, JSON, XLSX)"
                    }
                ],
                "response": {
                    "selector": ".assistant-message.completed",
                    "generating_selector": ".assistant-message.generating",
                    "stop_selector": "button#stop-btn",
                    "wait_until": "completed",
                    "timeout": 120,
                    "min_length": 5
                },
                "auth": {
                    "login_url": f"http://localhost:{settings.APP_PORT}/mock-site/login",
                    "check_selector": "#user-profile-badge",
                    "login_required_selector": "#login-form-container",
                    "auto_pause_for_human": True
                }
            }
            self.save_config("mock_site", mock_config)

        generic_path = self.configs_dir / "generic_chat.yaml"
        if not generic_path.exists():
            generic_config = {
                "name": "generic_chat",
                "title": "Generic Web Chat Template",
                "url": "https://example.com/chat",
                "chat": {
                    "input_selector": "textarea, [contenteditable='true']",
                    "send_selector": "button[type='submit'], button[aria-label='Send message']",
                    "input_method": "fill"
                },
                "attachments": [
                    {
                        "name": "file1",
                        "selector": "input[type='file']",
                        "multiple": False,
                        "description": "Generic File Upload"
                    }
                ],
                "response": {
                    "selector": ".assistant-message, [data-message-author-role='assistant']",
                    "generating_selector": ".typing-indicator, .streaming-text",
                    "stop_selector": "button[aria-label='Stop generating']",
                    "wait_until": "completed",
                    "timeout": 180,
                    "min_length": 1
                },
                "auth": {
                    "login_url": "https://example.com/login",
                    "check_selector": "#user-menu, [aria-label='User menu']",
                    "login_required_selector": "input[type='password'], #login-button",
                    "auto_pause_for_human": True
                }
            }
            self.save_config("generic_chat", generic_config)

    def list_configs(self) -> List[SiteConfig]:
        """List all valid site configurations."""
        configs = []
        for file_path in sorted(self.configs_dir.glob("*.yaml")):
            try:
                cfg = self.load_config(file_path.stem)
                if cfg:
                    configs.append(cfg)
            except Exception as e:
                print(f"Warning: Failed to load config {file_path}: {e}")
        return configs

    def load_config(self, name: str) -> Optional[SiteConfig]:
        """Load and validate a site configuration by name."""
        file_path = self.configs_dir / f"{name}.yaml"
        if not file_path.exists():
            return None
        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            return None
        data["name"] = name
        return SiteConfig(**data)

    def save_config(self, name: str, data: dict) -> SiteConfig:
        """Validate and save a configuration dict to YAML file."""
        data["name"] = name
        site_cfg = SiteConfig(**data)
        file_path = self.configs_dir / f"{name}.yaml"
        with open(file_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(site_cfg.model_dump(), f, sort_keys=False, allow_unicode=True)
        return site_cfg

    def delete_config(self, name: str) -> bool:
        """Delete a configuration file."""
        file_path = self.configs_dir / f"{name}.yaml"
        if file_path.exists():
            file_path.unlink()
            return True
        return False

config_manager = ConfigManager()
