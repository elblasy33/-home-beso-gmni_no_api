import asyncio
import json
import os
import shutil
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from fastapi.responses import JSONResponse, StreamingResponse

from src.config import settings
from src.models import Job, JobStatus, AttachmentItem, LogLevel
from src.queue.job_worker import job_worker
from src.config_manager import config_manager

router = APIRouter(prefix="/api/jobs", tags=["Automation Jobs"])

@router.post("", response_model=dict)
async def create_job(
    config_name: str = Form(...),
    url: str = Form(...),
    prompt: str = Form(...),
    files: List[UploadFile] = File(default=[]),
    targets: str = Form(default="[]")  # JSON encoded list of target names
):
    """Submits a new browser automation task with configurable multi-attachment routing."""
    # Check config exists
    cfg = config_manager.load_config(config_name)
    if not cfg:
        raise HTTPException(status_code=404, detail=f"Configuration '{config_name}' not found")

    job = job_worker.create_job(
        config_name=config_name,
        url=url or cfg.url,
        prompt=prompt
    )

    # Parse target mapping
    try:
        targets_list = json.loads(targets)
    except Exception:
        targets_list = []

    # Process file uploads
    uploads_dir = Path(settings.UPLOADS_DIR) / job.id
    uploads_dir.mkdir(parents=True, exist_ok=True)

    for idx, upload_file in enumerate(files):
        if not upload_file.filename:
            continue
        
        # Save file to uploads folder
        safe_filename = Path(upload_file.filename).name
        dest_path = uploads_dir / safe_filename
        with open(dest_path, "wb") as f:
            shutil.copyfileobj(upload_file.file, f)

        # Match target
        target_name = targets_list[idx] if idx < len(targets_list) and targets_list[idx] else "default"
        
        job.attachments.append(AttachmentItem(
            filename=safe_filename,
            target_name=target_name,
            file_path=str(dest_path.resolve()),
            size_bytes=dest_path.stat().st_size
        ))

    # Enqueue job to background worker
    await job_worker.enqueue_job(job)

    return {
        "job_id": job.id,
        "status": job.status,
        "created_at": job.created_at,
        "attachments_count": len(job.attachments)
    }

@router.get("", response_model=List[dict])
async def list_jobs(limit: int = 20):
    jobs = job_worker.list_jobs(limit=limit)
    return [j.model_dump() for j in jobs]

@router.get("/{job_id}", response_model=dict)
async def get_job(job_id: str):
    job = job_worker.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.model_dump()

@router.get("/{job_id}/logs", response_model=List[dict])
async def get_job_logs(job_id: str):
    job = job_worker.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return [log.model_dump() for log in job.logs]

@router.get("/{job_id}/response", response_model=dict)
async def get_job_response(job_id: str):
    job = job_worker.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "job_id": job.id,
        "status": job.status,
        "response_text": job.response_text,
        "error": job.error,
        "screenshot_url": job.screenshot_url
    }

@router.post("/{job_id}/resume", response_model=dict)
async def resume_job(job_id: str):
    """Resume a job waiting for human interaction (2FA / CAPTCHA / Login)."""
    job = job_worker.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    success = job_worker.resume_job(job_id)
    return {"job_id": job_id, "resumed": success}

@router.post("/{job_id}/cancel", response_model=dict)
async def cancel_job(job_id: str):
    job = job_worker.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    success = job_worker.cancel_job(job_id)
    return {"job_id": job_id, "cancelled": success}

@router.get("/{job_id}/stream")
async def stream_job_events(job_id: str):
    """Server-Sent Events (SSE) stream for real-time job log and state changes."""
    job = job_worker.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    q = job_worker.subscribe(job_id)

    async def event_generator():
        # Send initial state
        yield f"data: {json.dumps(job.model_dump())}\n\n"

        try:
            while True:
                try:
                    data = await asyncio.wait_for(q.get(), timeout=15.0)
                    yield f"data: {json.dumps(data)}\n\n"
                    # If job reached terminal state, stop streaming
                    if data.get("status") in [JobStatus.COMPLETED.value, JobStatus.FAILED.value, JobStatus.CANCELLED.value]:
                        break
                except asyncio.TimeoutError:
                    # Send keep-alive ping
                    yield f": keepalive\n\n"
        finally:
            job_worker.unsubscribe(job_id, q)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
