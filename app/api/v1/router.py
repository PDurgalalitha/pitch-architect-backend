from fastapi import APIRouter

from app.api.v1.endpoints import health, decks, reference, export

api_router = APIRouter()

api_router.include_router(health.router, tags=["Health Check"])
api_router.include_router(decks.router, prefix="/api/v1", tags=["Pitch Decks"])
api_router.include_router(reference.router, prefix="/api/v1", tags=["Reference Decks"])
api_router.include_router(export.router, prefix="/api/v1", tags=["Export Utilities"])