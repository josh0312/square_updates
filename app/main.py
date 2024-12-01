from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError

from api.endpoints import catalog, images, scraping
from core.config import settings
from middleware.error_handler import (
    error_handler_middleware,
    validation_exception_handler,
    sqlalchemy_exception_handler
)

app = FastAPI(
    title="NyTex Fireworks API",
    description="API for managing NyTex Fireworks Square catalog and images",
    version="1.0.0"
)

# Add middleware
app.middleware("http")(error_handler_middleware)

# Add exception handlers
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(catalog.router, prefix="/api/catalog", tags=["catalog"])
app.include_router(images.router, prefix="/api/images", tags=["images"])
app.include_router(scraping.router, prefix="/api/scraping", tags=["scraping"])

@app.get("/")
async def root():
    return {"message": "Welcome to NyTex Fireworks API"}