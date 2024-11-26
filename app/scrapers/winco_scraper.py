import requests
from bs4 import BeautifulSoup
import time
from urllib.parse import urljoin, urlparse
import re
import logging
import os

# Set up logging
logger = logging.getLogger('winco_scraper')
logger.setLevel(logging.INFO)

def scrape_website(url, limit=5, base_dir=None, headers=None):
    """Main scraper function"""
    if not headers:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
        }

    # Create domain directory for images
    domain = urlparse(url).netloc.replace('www.', '')
    domain_dir = os.path.join(base_dir, domain) if base_dir else domain
    os.makedirs(domain_dir, exist_ok=True)
    
    logger.info(f"Fetching content from: {url}")
    logger.info(f"Saving images to: {domain_dir}")
    
    successful_downloads = 0
    current_url = url
    pages_processed = 0
    
    while True:  # Changed to while True with explicit breaks
        try:
            # Get initial page
            logger.info(f"Making request to: {current_url}")
            response = requests.get(current_url, headers=headers, verify=False)
            logger.info(f"Response status code: {response.status_code}")
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Find all product containers
                products = soup.find_all('li', class_='product')
                logger.info(f"Found {len(products)} products")
                
                # Process products
                for product in products:
                    if limit != -1 and successful_downloads >= limit:
                        return
                    
                    # Get product title from h3.product-title
                    title = product.find('h3', class_='product-title')
                    if title:
                        title_link = title.find('a')
                        if title_link:
                            product_name = title_link.text.strip()
                            product_url = title_link['href']
                            logger.info(f"\nProcessing product: {product_name}")
                            logger.info(f"URL: {product_url}")
                            
                            # Get product page
                            product_response = requests.get(product_url, headers=headers, verify=False)
                            if product_response.status_code == 200:
                                product_soup = BeautifulSoup(product_response.text, 'html.parser')
                                
                                # Find product image
                                image = product_soup.find('img', class_='wp-post-image')
                                if image:
                                    image_url = image.get('data-src') or image.get('src')
                                    if image_url:
                                        # Clean filename
                                        clean_name = re.sub(r'[^\w\s-]', '', product_name)
                                        clean_name = re.sub(r'\s+', '-', clean_name).strip('-')
                                        filename = f"{clean_name}.png"
                                        filepath = os.path.join(domain_dir, filename)
                                        
                                        if not os.path.exists(filepath):
                                            try:
                                                img_response = requests.get(image_url, headers=headers, verify=False)
                                                if img_response.status_code == 200:
                                                    with open(filepath, 'wb') as f:
                                                        f.write(img_response.content)
                                                    successful_downloads += 1
                                                    logger.info(f"Downloaded image: {filename}")
                                            except Exception as e:
                                                logger.error(f"Error downloading image: {str(e)}")
                                        else:
                                            logger.info(f"Image already exists: {filename}")
                            
                            time.sleep(1)  # Polite delay between products
                
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
                
        except Exception as e:
            logger.error(f"Error processing page: {str(e)}")
            break
    
    logger.info("\nFinal Summary:")
    logger.info(f"Total pages processed: {pages_processed + 1}")
    logger.info(f"Images downloaded: {successful_downloads}") 