import asyncio
import aiohttp
import requests
from bs4 import BeautifulSoup
from app.models.product import BaseProduct, VendorProduct, Base
from urllib.parse import urljoin, urlparse
import time
import re
from PIL import Image
import io
import os
from app.scrapers.base_scraper import BaseScraper
from app.utils.paths import paths
from app.utils.logger import setup_logger
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import logging
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Dict, Optional, Tuple
from app.utils.request_helpers import get_with_ssl_ignore

class NytexFireworksScraper(BaseScraper):
    def __init__(self):
        super().__init__('nytex_scraper')
        
    def scan_for_videos(self, url: str, headers: Optional[Dict] = None) -> None:
        """Scan NyTex website for products and their video status"""
        if not headers:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
        self.logger.info(f"Starting video scan of {url}")
        
        try:
            # Get main page
            response = get_with_ssl_ignore(url, headers=headers)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find all product links
            products = self._get_product_links(soup)
            
            for product_url in products:
                try:
                    has_video = self._check_product_video(product_url, headers)
                    self._update_product_video_status(product_url, has_video)
                except Exception as e:
                    self.logger.error(f"Error processing product {product_url}: {str(e)}")
                    continue
                    
        except Exception as e:
            self.logger.error(f"Error scanning website: {str(e)}")
            
    def _get_product_links(self, soup: BeautifulSoup) -> list:
        """Extract all product links from the page"""
        product_links = []
        # Implement product link extraction logic here
        # This will need to be customized based on NyTex's site structure
        return product_links
        
    def _check_product_video(self, product_url: str, headers: Dict) -> bool:
        """Check if a product page has a video"""
        try:
            response = get_with_ssl_ignore(product_url, headers=headers)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for common video elements
            video_elements = soup.find_all(['video', 'iframe'])
            youtube_links = soup.find_all('a', href=lambda x: x and 'youtube.com' in x)
            vimeo_links = soup.find_all('a', href=lambda x: x and 'vimeo.com' in x)
            
            return bool(video_elements or youtube_links or vimeo_links)
            
        except Exception as e:
            self.logger.error(f"Error checking video for {product_url}: {str(e)}")
            return False
            
    def _update_product_video_status(self, product_url: str, has_video: bool) -> None:
        """Update the product's video status in the database using new model structure"""
        try:
            # Create database session
            engine = create_engine(f'sqlite:///{paths.DB_FILE}')
            Session = sessionmaker(bind=engine)
            session = Session()
            
            # Find vendor product by URL (assuming it's a NyTex product)
            vendor_product = session.query(VendorProduct).filter_by(
                vendor_product_url=product_url,
                vendor_name='NyTex Fireworks'
            ).first()
            
            if vendor_product:
                vendor_product.vendor_video_url = product_url if has_video else None
                session.commit()
                
                # Get the base product name for logging
                base_product = session.query(BaseProduct).filter_by(
                    id=vendor_product.base_product_id
                ).first()
                
                product_name = base_product.name if base_product else "Unknown"
                self.logger.info(f"Updated video status for {product_name}: {'Has video' if has_video else 'No video'}")
            else:
                self.logger.warning(f"Product not found in database for URL: {product_url}")
            
        except Exception as e:
            self.logger.error(f"Error updating video status in database: {str(e)}")
            if 'session' in locals():
                session.rollback()
        finally:
            if 'session' in locals():
                session.close() 