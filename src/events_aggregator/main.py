from fastapi import FastAPI

from .api.router import router as api_router
from events_aggregator.config import settings


app = FastAPI(
    title=settings.app_name,
    debug=settings.debug
)


app.include_router(api_router)
