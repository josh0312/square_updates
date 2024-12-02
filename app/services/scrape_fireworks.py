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

def run_scrapers():
    """Run scrapers based on websites.yaml configuration"""
    all_stats = []
    
    # Load website configurations
    with open(paths.WEBSITES_CONFIG, 'r') as f:
        config = yaml.safe_load(f)
    
    # Make sure we have the websites list
    websites = config.get('websites', [])
    if not websites:
        logger.error("No websites found in configuration")
        return
        
    logger.info(f"Found {len(websites)} websites in configuration")
    logger.info("Website order from config:")
    for idx, website in enumerate(websites, 1):
        logger.info(f"{idx}. {website.get('name')} ({website.get('scraper')})")
    
    # Process each website in order
    for website in websites:
        site_name = website.get('name')
        scraper_name = website.get('scraper')
        
        if not site_name or not scraper_name:
            logger.error(f"Missing name or scraper in config: {website}")
            continue
            
        if not website.get('enabled', True):  # Default to enabled if not specified
            logger.info(f"Skipping disabled scraper for {site_name}")
            continue
            
        try:
            # Import the scraper class dynamically
            module_name = f"app.scrapers.{scraper_name}"
            
            # Convert scraper name to class name
            class_name = ''.join(
                word.capitalize() 
                for word in scraper_name.replace('_scraper', '').split('_')
            ) + 'FireworksScraper'
            
            logger.info(f"Scraper name from config: {scraper_name}")
            logger.info(f"Generated class name: {class_name}")
            
            # Import the module first
            module = importlib.import_module(module_name)
            
            # Now we can log module attributes
            logger.info(f"Available attributes in module: {dir(module)}")
            logger.info(f"Attempting to load {class_name} from {module_name}")
            
            # Get the class
            scraper_class = getattr(module, class_name)
            
            # Initialize and run the scraper
            logger.info(f"Starting scrape for {site_name}...")
            scraper = scraper_class()
            scraper.run()
            all_stats.append(scraper.stats)
            logger.info(f"Completed scrape for {site_name}")
            
        except ImportError as e:
            logger.error(f"Could not import scraper module for {site_name} ({module_name}): {str(e)}")
        except AttributeError as e:
            logger.error(f"Could not find scraper class {class_name} for {site_name}: {str(e)}")
        except Exception as e:
            logger.error(f"Error running scraper for {site_name}: {str(e)}")
            
    # Print overall summary
    logger.info("\n" + "="*50)
    logger.info("OVERALL SCRAPING SUMMARY")
    logger.info("="*50)
    
    total_pages = sum(stat.pages_processed for stat in all_stats)
    total_products = sum(stat.products_found for stat in all_stats)
    total_downloads = sum(stat.images_downloaded for stat in all_stats)
    total_existing = sum(stat.images_existing for stat in all_stats)
    total_errors = sum(stat.errors for stat in all_stats)
    
    logger.info(f"Total Pages Processed: {total_pages}")
    logger.info(f"Total Products Found: {total_products}")
    logger.info(f"\nTotal Images:")
    logger.info(f"  • Downloaded: {total_downloads}")
    logger.info(f"  • Already Existed: {total_existing}")
    logger.info(f"  • Total: {total_downloads + total_existing}")
    if total_errors > 0:
        logger.info(f"\nTotal Errors: {total_errors}")
    logger.info("="*50)

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
        run_scrapers()
    except Exception as e:
        logger.error("Fatal error in main execution", exc_info=True)