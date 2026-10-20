from typing import List
from fastapi import APIRouter, HTTPException
from src.models import SiteConfig
from src.config_manager import config_manager

router = APIRouter(prefix="/api/configs", tags=["Site Configurations"])

@router.get("", response_model=List[SiteConfig])
async def list_configs():
    return config_manager.list_configs()

@router.get("/{name}", response_model=SiteConfig)
async def get_config(name: str):
    cfg = config_manager.load_config(name)
    if not cfg:
        raise HTTPException(status_code=404, detail=f"Configuration '{name}' not found")
    return cfg

@router.post("", response_model=SiteConfig)
async def save_config(config: SiteConfig):
    try:
        saved = config_manager.save_config(config.name, config.model_dump())
        return saved
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{name}")
async def delete_config(name: str):
    if not config_manager.delete_config(name):
        raise HTTPException(status_code=404, detail=f"Configuration '{name}' not found")
    return {"status": "deleted", "name": name}
