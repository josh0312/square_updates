import os
import logging
import urllib3
import requests
from bs4 import BeautifulSoup
import time

# Disable SSL warnings for testing
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Set up logging
logger = logging.getLogger('winco_scraper_test')
logger.setLevel(logging.INFO)

# Create handlers
file_handler = logging.FileHandler('winco_test.log', mode='w')
console_handler = logging.StreamHandler()

# Create formatters
log_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(log_format)
console_handler.setFormatter(log_format)

# Add handlers
logger.addHandler(file_handler)
logger.addHandler(console_handler)

def test_winco_scraper():
    """Test getting product URLs from Winco site"""
    logger.info("=== Starting Winco Scraper Test ===")
    
    # Test parameters
    test_url = "https://www.wincofireworks.com/fireworks/"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    logger.info(f"Test URL: {test_url}")
    
    try:
        current_url = test_url
        pages_processed = 0
        
        while pages_processed < 3:
            # Get page
            response = requests.get(current_url, headers=headers, verify=False)
            logger.info(f"\nPage {pages_processed + 1} status code: {response.status_code}")
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Find all product containers
                products = soup.find_all('li', class_='product')
                logger.info(f"Found {len(products)} products on page {pages_processed + 1}")
                
                # Get first 3 product details from this page
                for i, product in enumerate(products[:3], 1):
                    logger.info(f"\nProduct {i} details (Page {pages_processed + 1}):")
                    
                    # Get product title from h3.product-title
                    title = product.find('h3', class_='product-title')
                    if title:
                        title_link = title.find('a')
                        if title_link:
                            product_name = title_link.text.strip()
                            product_url = title_link['href']
                            logger.info(f"Name: {product_name}")
                            logger.info(f"URL: {product_url}")
                
                # Look for next page link
                next_link = soup.find('a', class_='next page-numbers')
                if next_link and next_link.get('href'):
                    current_url = next_link['href']
                    pages_processed += 1
                    logger.info(f"Moving to page {pages_processed + 1}")
                    time.sleep(2)  # Polite delay between pages
                else:
                    logger.info("No more pages found")
                    break
            else:
                logger.error(f"Failed to get page, status code: {response.status_code}")
                break
            
        logger.info("\nTest completed successfully")
        logger.info(f"Total pages processed: {pages_processed + 1}")
            
    except Exception as e:
        logger.error(f"Test failed: {str(e)}")

if __name__ == "__main__":
    test_winco_scraper() 