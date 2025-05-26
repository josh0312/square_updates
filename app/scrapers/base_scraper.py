import yaml
import logging
import os
from urllib.parse import urlparse, urljoin
from app.utils.paths import paths
from app.utils.logger import setup_logger
from app.utils.request_helpers import get_with_ssl_ignore
from bs4 import BeautifulSoup
import time
from typing import Optional, List, Dict
from dataclasses import dataclass, field
from PIL import Image
import io

@dataclass
class ProductData:
    """Data class for product information"""
    name: str
    url: str
    image_url: Optional[str] = None
    sku: Optional[str] = None
    description: Optional[str] = None
    effects: Optional[List[str]] = None
    price: Optional[str] = None
    category: Optional[str] = None
    stock_status: Optional[str] = None

@dataclass
class ScraperStats:
    vendor_name: str
    pages_processed: int = 0
    products_found: int = 0
    images_downloaded: int = 0
    images_existing: int = 0
    db_updates: int = 0
    db_inserts: int = 0
    db_unchanged: int = 0
    errors: int = 0
    
    def print_summary(self, logger):
        logger.info("\n" + "="*50)
        logger.info(f"Summary for {self.vendor_name}")
        logger.info("="*50)
        logger.info(f"Pages Processed: {self.pages_processed}")
        logger.info(f"Products Found: {self.products_found}")
        logger.info("\nImage Statistics:")
        logger.info(f"  • Downloaded: {self.images_downloaded}")
        logger.info(f"  • Already Existed: {self.images_existing}")
        logger.info(f"  • Total Images: {self.images_downloaded + self.images_existing}")
        logger.info("\nDatabase Statistics:")
        logger.info(f"  • New Records: {self.db_inserts}")
        logger.info(f"  • Updated Records: {self.db_updates}")
        logger.info(f"  • Unchanged Records: {self.db_unchanged}")
        logger.info(f"  • Total Records: {self.db_inserts + self.db_updates + self.db_unchanged}")
        if self.errors > 0:
            logger.info(f"\nErrors Encountered: {self.errors}")
        logger.info("="*50 + "\n")

class BaseScraper:
    def __init__(self, scraper_name):
        self.logger = setup_logger(scraper_name)
        self.config = self._load_config(scraper_name)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.stats = ScraperStats(self.config.get('name', scraper_name))
    
    def _load_config(self, scraper_name):
        """Load scraper configuration from websites.yaml"""
        with open(paths.WEBSITES_CONFIG, 'r') as f:
            config = yaml.safe_load(f)
            
        for website in config['websites']:
            if website.get('scraper') == scraper_name:
                return {
                    'enabled': website.get('enabled', False),
                    'limit': website.get('limit', -1),
                    'urls': website.get('urls', [website.get('url')]) if website.get('url') or website.get('urls') else [],
                    'note': website.get('note', '')  # Include notes for reference
                }
        return None
    
    def run(self):
        """Main entry point for scraper"""
        if not self.config:
            self.logger.error("No configuration found for scraper")
            return
            
        if not self.config['enabled']:
            self.logger.info("Scraper is disabled in config")
            return
            
        for url in self.config['urls']:
            self.logger.info(f"\nProcessing URL: {url}")
            self.scrape_website(url, limit=self.config['limit'])
    
    # Utility methods that scrapers can optionally use
    def get_domain_folder(self, url):
        """Create folder name from domain"""
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.replace('www.', '')
        return domain
    
    def make_request(self, url, timeout=30):
        """Make HTTP request with standard error handling"""
        try:
            response = get_with_ssl_ignore(url, headers=self.headers, timeout=timeout)
            response.raise_for_status()
            return response
        except Exception as e:
            self.logger.error(f"Error making request to {url}: {str(e)}")
            return None
    
    def download_image(self, url, filepath, max_retries=3, retry_delay=2):
        """Download image with retry logic and better error handling"""
        for attempt in range(max_retries):
            try:
                # Try HTTPS first
                if url.startswith('http://'):
                    https_url = url.replace('http://', 'https://', 1)
                    response = get_with_ssl_ignore(https_url, headers=self.headers)
                    if response.status_code == 200:
                        url = https_url  # Use HTTPS if it works
                    
                response = get_with_ssl_ignore(url, headers=self.headers)
                if response.status_code == 200:
                    os.makedirs(os.path.dirname(filepath), exist_ok=True)
                    with open(filepath, 'wb') as f:
                        f.write(response.content)
                    return True
                else:
                    self.logger.warning(f"Attempt {attempt + 1}/{max_retries}: Got status code {response.status_code}")
                    
            except Exception as e:
                self.logger.warning(f"Attempt {attempt + 1}/{max_retries} failed: {str(e)}")
                if attempt < max_retries - 1:  # Don't sleep on last attempt
                    time.sleep(retry_delay)
                    continue
                self.logger.error(f"Error downloading image {url}: {str(e)}")
                return False
            
        return False
    
    def count_existing_images(self, directory):
        """Count number of images in directory"""
        if not os.path.exists(directory):
            os.makedirs(directory)
            return 0
        return len([f for f in os.listdir(directory) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp'))])
    
    def download_product_image(self, image_url: str, filepath: str) -> bool:
        """Download and save product image with error handling"""
        try:
            response = get_with_ssl_ignore(image_url, headers=self.headers)
            if response.status_code == 200:
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                
                # Convert image if needed
                image = Image.open(io.BytesIO(response.content))
                
                # Convert to RGB if needed
                if image.mode in ('RGBA', 'LA'):
                    background = Image.new('RGB', image.size, (255, 255, 255))
                    background.paste(image, mask=image.split()[-1])
                    image = background
                
                # Save as PNG
                image.save(filepath, 'PNG', optimize=True)
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error downloading image {image_url}: {str(e)}")
            return False

    def clean_filename(self, name: str) -> str:
        """Create clean filename from product name"""
        return "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).rstrip()

    def get_next_page_url(self, soup: BeautifulSoup, current_url: str) -> Optional[str]:
        """Base implementation for finding next page URL"""
        # Look for common pagination patterns
        next_link = soup.find('a', class_='next') or \
                   soup.find('a', string=lambda x: x and ('Next' in x or '›' in x))
        if next_link and next_link.get('href'):
            return urljoin(current_url, next_link['href'])
        return None

    def extract_product_data(self, product_soup: BeautifulSoup, product_url: str) -> ProductData:
        """To be implemented by each scraper"""
        raise NotImplementedError("Scrapers must implement extract_product_data method")

    def get_product_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """To be implemented by each scraper"""
        raise NotImplementedError("Scrapers must implement get_product_links method") 