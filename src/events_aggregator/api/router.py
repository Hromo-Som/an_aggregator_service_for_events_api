from fastapi import APIRouter

from .endpoints.events import router as events_router
from .endpoints.health import router as health_router
from .endpoints.sync import router as sync_router
from .endpoints.tickets import router as tickets_router

router = APIRouter(prefix="/api")


router.include_router(events_router)
router.include_router(health_router)
router.include_router(sync_router)
router.include_router(tickets_router)
