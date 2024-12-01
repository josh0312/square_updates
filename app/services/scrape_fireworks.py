import os
import yaml
import logging
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.product import Base, Product
import importlib
import requests
import asyncio
import aiohttp
from aiohttp import ClientSession
from cachetools import TTLCache
from ratelimit import limits, sleep_and_retry
from app.utils.paths import paths
from app.utils.verify_paths import PathVerifier
from app.utils.logger import setup_logger
from app.config import websites, vendor_directories
from app.scrapers import redrhino_scraper, winco_scraper, raccoon_scraper

logger = setup_logger('scrape_fireworks')

# Base directory from paths
BASE_DIR = paths.DATA_DIR

# Default headers for requests
headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Connection': 'keep-alive',
}

# Database setup
engine = create_engine(f'sqlite:///{paths.DB_FILE}')  # Use path from paths.py
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

# Cache responses for 1 hour
page_cache = TTLCache(maxsize=100, ttl=3600)

def get_cached_page(url, headers):
    if url in page_cache:
        return page_cache[url]
        
    response = requests.get(url, headers=headers, verify=False)
    page_cache[url] = response.text
    return response.text

def load_websites():
    """Load website configurations"""
    return websites.get('websites', [])

async def download_image(session, url, filepath, headers):
    try:
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                content = await response.read()
                with open(filepath, 'wb') as f:
                    f.write(content)
                return True
    except Exception as e:
        logger.error(f"Error downloading {url}: {str(e)}")
    return False

async def process_product_batch(products, session, domain_dir, headers):
    tasks = []
    for product in products:
        if product.get('image_url'):
            filepath = os.path.join(domain_dir, f"{product['name']}.jpg")
            if not os.path.exists(filepath):
                task = download_image(session, product['image_url'], filepath, headers)
                tasks.append(task)
    return await asyncio.gather(*tasks)

def process_product_batch_db(products, session):
    """Process multiple products in a single database transaction"""
    try:
        for product in products:
            existing = session.query(Product).filter_by(
                site_name=product['site_name'],
                product_name=product['name']
            ).first()
            
            if existing:
                # Update if needed
                for key, value in product.items():
                    if getattr(existing, key) != value:
                        setattr(existing, key, value)
            else:
                # Create new
                new_product = Product(**product)
                session.add(new_product)
        
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        logger.error(f"Error processing batch: {str(e)}")
        return False

def scrape_all_websites():
    websites = load_websites()
    
    for website in websites:
        if not website.get('enabled', True):
            continue
            
        try:
            logger.info(f"\nAttempting to scrape {website['name']}...")
            
            # Get appropriate scraper function
            scraper_func = None
            if 'Red Rhino' in website['name']:
                scraper_func = redrhino_scraper.scrape_website
            elif 'Winco' in website['name']:
                scraper_func = winco_scraper.scrape_website
            elif 'Raccoon' in website['name']:
                scraper_func = raccoon_scraper.scrape_website
            else:
                logger.error(f"No scraper found for {website['name']}")
                continue
            
            # Get limit from website config
            limit = website.get('limit', -1)
            logger.info(f"Using limit: {limit if limit != -1 else 'unlimited'}")
            
            # Get URL - handle both single URL and list of URLs
            urls = website.get('urls', [website.get('url')] if website.get('url') else [])
            
            # Process each URL
            for url in urls:
                try:
                    scraper_func(
                        url=url,
                        limit=limit,
                        base_dir=BASE_DIR,
                        headers=headers
                    )
                except Exception as e:
                    logger.error(f"Error scraping URL {url}: {str(e)}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error processing website {website['name']}: {str(e)}")
            continue

@sleep_and_retry
@limits(calls=30, period=60)  # 30 calls per minute
def rate_limited_request(url, headers):
    return requests.get(url, headers=headers, verify=False)

if __name__ == "__main__":
    # Verify paths first
    verifier = PathVerifier()
    if not verifier.verify_all():
        logger.error("Path verification failed!")
        sys.exit(1)
    
    logger.info("Starting scraper...")
    try:
        scrape_all_websites()
    except Exception as e:
        logger.error("Fatal error in main execution", exc_info=True)