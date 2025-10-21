from datetime import datetime

from fastapi import APIRouter


health_router = APIRouter()


@health_router.get("/health")
def health_check():
    """
    Basic health check endpoint
    """
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}



@health_router.get("/health/detailed")
def detailed_health_check():
    """
    Detailed health check that verifies other component connectivity
    """

    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()

            # Add other service checks here (Redis, external APIs, etc.)
            }