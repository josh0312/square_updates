from typing import Dict, Optional
import asyncio
from fastapi import HTTPException
from datetime import datetime
import os

from app.models.product import Product, Base  # Update import path
from app.utils.logger import setup_logger  # Add centralized logger
from app.utils.paths import paths  # Add paths
from app.config import websites
from app.utils.verify_paths import PathVerifier

logger = setup_logger('scraper')

class ScraperService:
    def __init__(self):
        self.BASE_DIR = paths.DATA_DIR  # Use data directory for downloads

if __name__ == "__main__":
    # Verify paths first
    verifier = PathVerifier()
    if not verifier.verify_all():
        logger.error("Path verification failed!")
        sys.exit(1)
    
    # Continue with existing code
    scraper = ScraperService()
    # ... rest of the code ...