import logging

from fastapi import APIRouter, HTTPException, Request, status
from pymongo.errors import PyMongoError

router = APIRouter(prefix="/health", tags=["health"])
logger = logging.getLogger(__name__)


@router.get("/live", status_code=status.HTTP_200_OK)
def live() -> dict[str, str]:
    return {"status": "alive", "service": "survey-system-api"}


@router.get("/ready", status_code=status.HTTP_200_OK)
def ready(request: Request) -> dict[str, str]:
    try:
        request.app.state.mongodb_client.admin.command("ping")
    except (PyMongoError, AttributeError):
        logger.warning("MongoDB readiness check failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB unavailable",
        ) from None
    return {"status": "ready", "database": "connected"}
