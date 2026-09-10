from fastapi import APIRouter
from pydantic import BaseModel

from app.services.database import ping_db

router = APIRouter()


class HealthStatus(BaseModel):
    status: str
    database: str
    version: str


@router.get("/health", response_model=HealthStatus)
async def health() -> HealthStatus:
    db_ok = await ping_db()
    return HealthStatus(
        status="ok" if db_ok else "degraded",
        database="connected" if db_ok else "unavailable",
        version="0.1.0",
    )