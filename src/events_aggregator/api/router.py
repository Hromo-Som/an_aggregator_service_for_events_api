from fastapi import APIRouter

from .endpoints.events import router as events_router
from .health import router as health_router

router = APIRouter(prefix="/api")


router.include_router(events_router)
router.include_router(health_router)
