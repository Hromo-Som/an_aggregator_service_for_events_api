from fastapi import FastAPI

from events_aggregator.config import settings

from .api.router import router as api_router

app = FastAPI(title=settings.app_name, debug=settings.debug)


app.include_router(api_router)
