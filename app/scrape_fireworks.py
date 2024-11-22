import os
import yaml
import logging
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models.product import Base, Product
import importlib

# Add logging configuration at the top of the file after imports
def setup_logging():
    logging.basicConfig(
        level=logging.DEBUG,
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

def scrape_all_websites():
    websites = load_websites()
    
    if not websites:
        print("No websites found in configuration file!")
        return
    
    for site in websites:
        if not site.get('enabled', True):
            print(f"\nSkipping disabled website: {site['name']}")
            continue
            
        print(f"\n{'='*50}")
        print(f"Processing: {site['name']}")
        print(f"{'='*50}")
        
        scraper_module = importlib.import_module(f"scrapers.{site['scraper'].replace('.py', '')}")
        scraper_function = getattr(scraper_module, 'scrape_website')
        
        scraper_function(
            url=site['url'],
            limit=site.get('limit', 5),
            base_dir=BASE_DIR,
            headers=headers
        )

if __name__ == "__main__":
    logger.info("Starting scraper...")
    try:
        scrape_all_websites()
    except Exception as e:
        logger.error("Fatal error in main execution", exc_info=True) 