from fastapi import APIRouter
from src.api.routes_jobs import router as jobs_router
from src.api.routes_browser import router as browser_router
from src.api.routes_configs import router as configs_router
from src.api.routes_recorder import router as recorder_router

api_router = APIRouter()
api_router.include_router(jobs_router)
api_router.include_router(browser_router)
api_router.include_router(configs_router)
api_router.include_router(recorder_router)
