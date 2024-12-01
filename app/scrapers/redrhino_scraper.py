from app.models.product import Product, Base
from app.utils.logger import setup_logger
from app.utils.paths import paths
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import os
from PIL import Image
import io
import re
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine

# Set up logger
logger = setup_logger('redrhino_scraper')

# Database setup
engine = create_engine(f'sqlite:///{paths.DB_FILE}')
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

def scrape_website(url, limit=5, base_dir=None, headers=None):
    if not headers:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    # Create domain directory for images - remove www. prefix
    domain = urlparse(url).netloc.replace('www.', '')
    domain_dir = os.path.join(base_dir, domain) if base_dir else domain
    os.makedirs(domain_dir, exist_ok=True)
    
    # Count existing images
    existing_images = len([f for f in os.listdir(domain_dir) if os.path.isfile(os.path.join(domain_dir, f))])
    logger.info(f"Found {existing_images} existing images in directory")
    
    page = 1
    current_url = url
    
    while current_url:
        logger.info(f"\nProcessing page {page}...")
        
        try:
            response = requests.get(current_url, headers=headers, verify=False)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            next_url = handle_redrhino_site(current_url, soup, domain_dir, limit, headers)
            
            if not next_url:
                logger.info("No more product links found and no next page. Stopping scraper.")
                break
                
            current_url = next_url
            page += 1
            time.sleep(1)  # Polite delay between pages
            
        except Exception as e:
            logger.error(f"Error processing page {page}: {str(e)}")
            break
            
    # Log final summary
    final_image_count = len([f for f in os.listdir(domain_dir) if os.path.isfile(os.path.join(domain_dir, f))])
    logger.info("\nFinal Summary:")
    logger.info(f"Pages processed: {page}")
    logger.info(f"Existing images found: {existing_images}")
    logger.info(f"New images downloaded: {final_image_count - existing_images}")
    logger.info(f"Total images in directory: {final_image_count}")