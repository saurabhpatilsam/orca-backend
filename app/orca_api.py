from fastapi import FastAPI, Depends
from starlette.middleware.cors import CORSMiddleware

from app.api.health import health_router
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.orca_max_router import max_router
from app.core.config import verify_key, VERSION, BASE_PATH
from app.middlewares.log import LogMiddleware
from app.middlewares.rootpath import RootPathMiddleware


from app.utils.logging_setup import logger

# Initialize FastAPI without root_path for now
api_app = FastAPI(
    title="Trading Bot API",
    description="OrcaBot API Service",
    version=VERSION,
    # Don't use root_path here if you want /docs at the root
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add middlewares correctly
api_app.add_middleware(LogMiddleware, logger=logger)
# If RootPathMiddleware is a class, you need to instantiate it
api_app.add_middleware(RootPathMiddleware)
# Add CORS middleware - THIS IS CRUCIAL

api_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
api_app.include_router(health_router, tags=["Health"])

# Auth router - no dependencies, public access for signup/signin
api_app.include_router(
    auth_router,
    prefix=f"{BASE_PATH}",
)

api_app.include_router(
    max_router,
    prefix=f"{BASE_PATH}",
    # dependencies=[Depends(verify_key)],
)
#
# api_app.include_router(
#     phone_checker_router,
#     prefix=f"{BASE_PATH}/phone",
#     dependencies=[Depends(verify_key)],
# )
#
# api_app.include_router(
#     service_router,
#     prefix=f"{BASE_PATH}/service",
#     tags=["Service"],
#     dependencies=[Depends(verify_key)],
# )


@api_app.get("/")
def read_root():
    return {"service": "Orca bot", "version": VERSION, "documentation": "/docs"}
