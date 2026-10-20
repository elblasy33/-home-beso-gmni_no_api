import asyncio
import uuid
from typing import Dict, List, Optional, Callable, Set
from datetime import datetime, timezone

from src.models import Job, JobStatus, LogEntry, LogLevel, SiteConfig
from src.engine.automation_agent import automation_agent
from src.config_manager import config_manager

class JobWorker:
    def __init__(self):
        self._jobs: Dict[str, Job] = {}
        self._queue: asyncio.Queue = asyncio.Queue()
        self._resume_events: Dict[str, asyncio.Event] = {}
        self._subscribers: Dict[str, Set[asyncio.Queue]] = {}
        self._worker_task: Optional[asyncio.Task] = None
        self._is_running: bool = False

    def start(self):
        """Starts the background worker task."""
        if not self._is_running:
            self._is_running = True
            self._worker_task = asyncio.create_task(self._process_queue())

    async def stop(self):
        """Stops the worker cleanly."""
        self._is_running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

    def create_job(self, config_name: str, url: str, prompt: str) -> Job:
        """Instantiates a new job and places it in storage."""
        job = Job(
            config_name=config_name,
            url=url,
            prompt=prompt,
            status=JobStatus.QUEUED
        )
        job.add_log("Queue", "Job created and placed in execution queue.", LogLevel.INFO)
        self._jobs[job.id] = job
        self._resume_events[job.id] = asyncio.Event()
        self._subscribers[job.id] = set()
        return job

    async def enqueue_job(self, job: Job):
        """Enqueues job for background execution."""
        await self._queue.put(job.id)

    def get_job(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    def list_jobs(self, limit: int = 50) -> List[Job]:
        return sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)[:limit]

    def resume_job(self, job_id: str) -> bool:
        """Signals a paused job (waiting for human authentication/OTP) to proceed."""
        event = self._resume_events.get(job_id)
        if event:
            event.set()
            job = self.get_job(job_id)
            if job:
                job.add_log("Resume", "Human authentication confirmed. Resuming automation...", LogLevel.SUCCESS)
                self._broadcast(job)
            return True
        return False

    def cancel_job(self, job_id: str) -> bool:
        """Cancels a job if still queued or pending."""
        job = self.get_job(job_id)
        if job and job.status in [JobStatus.QUEUED, JobStatus.LOGIN_REQUIRED]:
            job.status = JobStatus.CANCELLED
            job.add_log("Cancelled", "Job cancelled by operator.", LogLevel.WARNING)
            self._broadcast(job)
            return True
        return False

    def subscribe(self, job_id: str) -> asyncio.Queue:
        """Returns an asyncio Queue receiving SSE events for a job."""
        q = asyncio.Queue()
        if job_id in self._subscribers:
            self._subscribers[job_id].add(q)
        else:
            self._subscribers[job_id] = {q}
        return q

    def unsubscribe(self, job_id: str, q: asyncio.Queue):
        if job_id in self._subscribers and q in self._subscribers[job_id]:
            self._subscribers[job_id].remove(q)

    def _broadcast(self, job: Job):
        """Pushes updated job state to all active subscribers."""
        if job.id in self._subscribers:
            for q in list(self._subscribers[job.id]):
                try:
                    q.put_nowait(job.model_dump())
                except asyncio.QueueFull:
                    pass

    async def _process_queue(self):
        """Sequential queue processor for browser automation jobs."""
        while self._is_running:
            try:
                job_id = await self._queue.get()
                job = self._jobs.get(job_id)
                if not job or job.status == JobStatus.CANCELLED:
                    self._queue.task_done()
                    continue

                config = config_manager.load_config(job.config_name)
                if not config:
                    job.status = JobStatus.FAILED
                    job.error = f"Configuration '{job.config_name}' not found."
                    job.add_log("Config Error", job.error, LogLevel.ERROR)
                    self._broadcast(job)
                    self._queue.task_done()
                    continue

                resume_event = self._resume_events.get(job_id)

                # Execute automation agent
                await automation_agent.run_job(
                    job=job,
                    config=config,
                    resume_event=resume_event,
                    on_update=self._broadcast
                )

                self._queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Unexpected error in worker loop: {e}")
                await asyncio.sleep(1)

job_worker = JobWorker()
