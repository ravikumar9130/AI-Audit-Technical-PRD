"""
Main FastAPI application entry point.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
import redis.asyncio as redis

from core.config import get_settings
from core.database import engine, Base
from api.auth import router as auth_router
from api.upload import router as upload_router
from api.calls import router as calls_router
from api.dashboard import router as dashboard_router
from api.templates import router as templates_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    try:
        Base.metadata.create_all(bind=engine)
        print("✓ Database tables ready")
    except Exception as e:
        print(f"⚠ Database init (non-fatal): {e}")
    try:
        redis_client = redis.from_url(settings.REDIS_URL)
        await redis_client.ping()
        print("✓ Redis connection successful")
    except Exception as e:
        print(f"⚠ Redis connection failed: {e}")
    print(f"🚀 {settings.APP_NAME} started in {settings.ENVIRONMENT} mode")
    yield
    print("👋 Shutting down...")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    description="Enterprise speech intelligence platform for automated call QA",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None
)

# CORS middleware (allow frontend from localhost in dev)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Trusted hosts middleware (allow all in dev so localhost works)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"]
)


# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle all unhandled exceptions."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "Internal server error", "detail": str(exc)}
    )


# Health check endpoint
@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT
    }


# Root endpoint
@app.get("/")
def root():
    """Root endpoint."""
    return {
        "name": settings.APP_NAME,
        "version": "1.0.0",
        "docs": "/docs"
    }


# Include routers
app.include_router(auth_router)
app.include_router(upload_router)
app.include_router(calls_router)
app.include_router(dashboard_router)
app.include_router(templates_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )
