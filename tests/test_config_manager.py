import pytest
import os
import shutil
from pathlib import Path

from src.config_manager import ConfigManager
from src.models import SiteConfig, ChatConfig, ResponseConfig, AttachmentTargetConfig

@pytest.fixture
def temp_config_manager(tmp_path):
    mgr = ConfigManager(configs_dir=str(tmp_path))
    yield mgr
    if tmp_path.exists():
        shutil.rmtree(tmp_path, ignore_errors=True)

def test_default_configs_created(temp_config_manager):
    configs = temp_config_manager.list_configs()
    names = [c.name for c in configs]
    assert "mock_site" in names
    assert "generic_chat" in names

def test_save_and_load_config(temp_config_manager):
    data = {
        "name": "custom_portal",
        "title": "Custom Test Portal",
        "url": "https://portal.example.com",
        "chat": {
            "input_selector": "#user-query",
            "send_selector": "#submit-btn",
            "input_method": "fill"
        },
        "attachments": [
            {
                "name": "pdf_doc",
                "selector": "#upload-pdf",
                "multiple": False,
                "description": "PDF Document"
            }
        ],
        "response": {
            "selector": "#bot-reply",
            "timeout": 60,
            "min_length": 5
        }
    }
    
    saved = temp_config_manager.save_config("custom_portal", data)
    assert saved.name == "custom_portal"
    assert saved.chat.input_selector == "#user-query"
    assert len(saved.attachments) == 1
    assert saved.attachments[0].selector == "#upload-pdf"

    loaded = temp_config_manager.load_config("custom_portal")
    assert loaded is not None
    assert loaded.title == "Custom Test Portal"
    assert loaded.response.timeout == 60

def test_delete_config(temp_config_manager):
    assert temp_config_manager.delete_config("mock_site") is True
    assert temp_config_manager.load_config("mock_site") is None
