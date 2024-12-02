import yaml
import logging
import os
from urllib.parse import urlparse
from app.utils.paths import paths
from app.utils.logger import setup_logger
from app.utils.request_helpers import get_with_ssl_ignore
from bs4 import BeautifulSoup
import time

class BaseScraper:
    def __init__(self, scraper_name):
        self.logger = setup_logger(scraper_name)
        self.config = self._load_config(scraper_name)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
    
    def _load_config(self, scraper_name):
        """Load scraper configuration from websites.yaml"""
        with open(paths.WEBSITES_CONFIG, 'r') as f:
            config = yaml.safe_load(f)
            
        for website in config['websites']:
            if website.get('scraper') == scraper_name:
                return {
                    'enabled': website.get('enabled', False),
                    'limit': website.get('limit', -1),
                    'urls': website.get('urls', [website.get('url')]) if website.get('url') or website.get('urls') else []
                }
        return None
    
    def get_domain_folder(self, url):
        """Create folder name from domain"""
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.replace('www.', '')
        return domain
    
    def count_existing_images(self, directory):
        """Count number of images in directory"""
        if not os.path.exists(directory):
            os.makedirs(directory)
            return 0
        return len([f for f in os.listdir(directory) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp'))])
    
    def make_request(self, url, timeout=30):
        """Make HTTP request with standard error handling"""
        try:
            response = get_with_ssl_ignore(url, headers=self.headers, timeout=timeout)
            response.raise_for_status()
            return response
        except Exception as e:
            self.logger.error(f"Error making request to {url}: {str(e)}")
            return None
    
    def download_image(self, url, filepath):
        """Download image with standard error handling"""
        try:
            response = get_with_ssl_ignore(url, headers=self.headers)
            if response.status_code == 200:
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                with open(filepath, 'wb') as f:
                    f.write(response.content)
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error downloading image {url}: {str(e)}")
            return False
    
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
            self.scrape_website(url, limit=self.config['limit'], base_dir=paths.DATA_DIR)
    
    def scrape_website(self, url, limit=-1, base_dir=None):
        """To be implemented by each scraper"""
        raise NotImplementedError("Scrapers must implement scrape_website method") 