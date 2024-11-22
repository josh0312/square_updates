import os
import yaml
import logging
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models.product import Base, Product
import importlib
import requests
import asyncio
import aiohttp
from aiohttp import ClientSession
from cachetools import TTLCache
from ratelimit import limits, sleep_and_retry

# Add logging configuration at the top of the file after imports
def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('scraper.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logging()

# Base directory
BASE_DIR = '/Users/joshgoble/Downloads/firework_pics'

# Default headers for requests
headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Connection': 'keep-alive',
}

# Add at top of file with other imports
engine = create_engine('sqlite:///fireworks.db')  # You can change to PostgreSQL or MySQL later
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
    """Load website configurations from yaml file"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, 'websites.yaml')
    
    try:
        with open(config_path, 'r') as file:
            config = yaml.safe_load(file)
            return config.get('websites', [])
    except Exception as e:
        print(f"Error loading websites.yaml: {str(e)}")
        return []

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
            logging.info(f"\nAttempting to scrape {website['name']}...")
            
            # Remove .py extension if it exists in the scraper name
            scraper_name = website['scraper'].replace('.py', '')
            scraper_module = importlib.import_module(f"scrapers.{scraper_name}")
            scraper_function = getattr(scraper_module, 'scrape_website')
            
            # Create website-specific directory
            website_dir = BASE_DIR
            
            scraper_function(
                website['url'],
                limit=website.get('limit', -1),
                base_dir=website_dir,
                headers=headers
            )
            
        except requests.exceptions.ConnectionError as e:
            logging.error(f"Failed to connect to {website['name']}: {str(e)}")
            continue
        except Exception as e:
            logging.error(f"Error scraping {website['name']}: {str(e)}")
            continue

@sleep_and_retry
@limits(calls=30, period=60)  # 30 calls per minute
def rate_limited_request(url, headers):
    return requests.get(url, headers=headers, verify=False)

if __name__ == "__main__":
    logger.info("Starting scraper...")
    try:
        scrape_all_websites()
    except Exception as e:
        logger.error("Fatal error in main execution", exc_info=True) 