from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException

from src.models import SiteConfig
from src.engine.recorder import site_recorder

router = APIRouter(prefix="/api/recorder", tags=["Site Recorder & Debugger"])

class StartRecordingRequest(BaseModel):
    url: str
    headed: bool = True

class GenerateConfigRequest(BaseModel):
    config_name: str
    title: Optional[str] = None

@router.post("/start")
async def start_recording(req: StartRecordingRequest):
    try:
        res = await site_recorder.start_recording(req.url, headed=req.headed)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/events")
async def get_recorded_events():
    return await site_recorder.get_recorded_events()

@router.post("/generate-config", response_model=SiteConfig)
async def generate_configuration(req: GenerateConfigRequest):
    try:
        cfg = await site_recorder.generate_configuration(
            config_name=req.config_name,
            site_title=req.title
        )
        return cfg
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/stop")
async def stop_recording():
    await site_recorder.stop_recording()
    return {"status": "stopped"}
