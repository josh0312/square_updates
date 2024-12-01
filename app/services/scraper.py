from typing import Dict, Optional
import asyncio
from fastapi import HTTPException
import logging
from datetime import datetime
import importlib
import os
import yaml
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.config import settings
from app.utils.logger import setup_logger
from app.config import websites  # Import from config package

logger = setup_logger(__name__)

class ScraperService:
    _instance = None
    _status: Dict[str, any] = {
        "is_running": False,
        "last_run": None,
        "current_vendor": None,
        "items_processed": 0,
        "errors": []
    }
    
    # Your existing configuration
    BASE_DIR = '/Users/joshgoble/Downloads/firework_pics'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive',
    }

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ScraperService, cls).__new__(cls)
        return cls._instance

    def load_websites(self):
        """Load website configurations from yaml file"""
        return websites.get('websites', [])

    @classmethod
    def get_status(cls) -> Dict[str, any]:
        return cls._status

    async def start_scraping(self):
        """Start the scraping process"""
        if self._status["is_running"]:
            raise HTTPException(
                status_code=400,
                detail="Scraping process already running"
            )

        try:
            self._status.update({
                "is_running": True,
                "last_run": datetime.now(),
                "items_processed": 0,
                "errors": []
            })

            # Use your existing scraping logic
            await self._run_scraping()

        except Exception as e:
            self._status["errors"].append(str(e))
            logger.error(f"Scraping error: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Scraping failed: {str(e)}"
            )
        finally:
            self._status["is_running"] = False

    async def _run_scraping(self):
        """Main scraping logic using your existing code"""
        websites = self.load_websites()
        
        for website in websites:
            if not website.get('enabled', True):
                continue
                
            try:
                self._status["current_vendor"] = website['name']
                logger.info(f"\nAttempting to scrape {website['name']}...")
                
                # Remove .py extension if it exists in the scraper name
                scraper_name = website['scraper'].replace('.py', '')
                scraper_module = importlib.import_module(f"app.scrapers.{scraper_name}")
                scraper_function = getattr(scraper_module, 'scrape_website')
                
                # Get limit from website config
                limit = website.get('limit', -1)
                
                # Get URL - handle both single URL and list of URLs
                urls = website.get('urls', [website.get('url')] if website.get('url') else [])
                
                # Process each URL
                for url in urls:
                    try:
                        await self._scrape_url(scraper_function, url, limit)
                        self._status["items_processed"] += 1
                    except Exception as e:
                        error_msg = f"Error scraping URL {url}: {str(e)}"
                        self._status["errors"].append(error_msg)
                        logger.error(error_msg)
                        
            except Exception as e:
                error_msg = f"Error processing website {website['name']}: {str(e)}"
                self._status["errors"].append(error_msg)
                logger.error(error_msg)

    async def _scrape_url(self, scraper_function, url: str, limit: int):
        """Execute scraping for a single URL"""
        try:
            # Convert your synchronous scraper to async if needed
            await asyncio.to_thread(
                scraper_function,
                url=url,
                limit=limit,
                base_dir=self.BASE_DIR,
                headers=self.headers
            )
        except Exception as e:
            raise Exception(f"Failed to scrape {url}: {str(e)}")