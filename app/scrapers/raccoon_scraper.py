from app.models.product import BaseProduct, VendorProduct, Base
from app.utils.logger import setup_logger
from app.utils.paths import paths
from app.utils.request_helpers import get_with_ssl_ignore
import requests
from bs4 import BeautifulSoup
import time
from urllib.parse import urljoin, urlparse
import re
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os
from app.scrapers.base_scraper import BaseScraper

# Set up logger
logger = setup_logger('raccoon_scraper')

# Database setup
engine = create_engine(f'sqlite:///{paths.DB_FILE}')
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

class RaccoonFireworksScraper(BaseScraper):
    def __init__(self):
        super().__init__('raccoon_scraper')
        
    def scrape_website(self, url, limit=5, base_dir=None):
        """Main scraping method"""
        # Use centralized images directory structure
        domain = self.get_domain_folder(url)
        domain_dir = os.path.join(paths.IMAGES_DIR, domain)
        
        self.logger.info(f"Fetching content from: {url}")
        self.logger.info(f"Saving images to: {domain_dir}")
        
        response = self.make_request(url)
        if not response:
            return
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        existing_count = self.count_existing_images(domain_dir)
        self.logger.info(f"Found {existing_count} existing images in directory")
        
        successful_downloads = 0
        current_url = url
        page_number = 1
        empty_pages_count = 0  # Track consecutive empty pages
        
        while current_url and (limit == -1 or successful_downloads < limit):
            self.logger.info(f"\nProcessing page {page_number}...")
            response = self.make_request(current_url)
            if not response:
                break
                
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find all product links
            product_links = soup.select('a[href*="/product-page/"]')
            unique_product_links = list(set([link.get('href') for link in product_links if link.get('href')]))
            
            # Check for empty pages
            if len(unique_product_links) == 0:
                empty_pages_count += 1
                self.logger.info(f"Empty page found. {empty_pages_count} consecutive empty pages so far.")
                if empty_pages_count >= 3:
                    self.logger.info("Found 3 consecutive empty pages. Assuming end of catalog reached.")
                    break
            else:
                empty_pages_count = 0  # Reset counter when we find products
                self.stats.pages_processed += 1
                self.stats.products_found += len(unique_product_links)
                
            self.logger.info(f"Found {len(unique_product_links)} unique product links")
            
            # Process each product
            for product_url in unique_product_links:
                if limit != -1 and successful_downloads >= limit:
                    break
                    
                if not product_url.startswith(('http://', 'https://')):
                    product_url = urljoin(current_url, product_url)
                    
                self.logger.info(f"Visiting product page: {product_url}")
                
                try:
                    product_details = self.get_raccoon_product_details(product_url)
                    if product_details and product_details.get('name') and product_details.get('image_url'):
                        was_updated = self.process_raccoon_product(
                            product_details['name'],
                            product_url,
                            product_details['image_url'],
                            soup,
                            domain_dir
                        )
                        if was_updated:
                            successful_downloads += 1
                            
                except Exception as e:
                    self.stats.errors += 1
                    self.logger.error(f"Error processing product page: {str(e)}")
                    continue
                    
                time.sleep(1)  # Polite delay
            
            # Get next page URL
            next_url = self.get_next_page_url(soup, current_url)
            if next_url:
                self.logger.info(f"Moving to next page: {next_url}")
                current_url = next_url
                page_number += 1
                time.sleep(2)
            else:
                self.logger.info("No more pages found")
                break
        
        # Only print summary after all URLs are processed
        if url == self.config['urls'][-1]:  # Only on last URL
            self.stats.print_summary(self.logger)

    def get_raccoon_product_details(self, product_url):
        """Extract product details from a Raccoon product page"""
        try:
            response = self.make_request(product_url)
            if not response:
                return None
                
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Log full HTML for debugging
            logger.info("\nDEBUG: All image URLs found:")
            
            # Find product name
            product_name = None
            name_elem = soup.find('h1', {'data-hook': 'product-title'})
            if name_elem:
                product_name = name_elem.text.strip()
            
            # Find product image
            image_url = None
            # Look for product images while excluding logos, buttons, etc.
            images = soup.find_all('img')
            for img in images:
                img_url = img.get('src', '')
                if img_url:
                    logger.info(f"Found image: {img_url}")
                    if ('wixstatic.com' in img_url and 
                        not any(x in img_url.lower() for x in ['button', 'logo', 'icon'])):
                        # Select this image URL
                        logger.info("Selected this image URL")
                        # Modify URL to get high-res version
                        image_url = re.sub(r'/v1/fill/[^/]+/', '/v1/fill/w_1500,h_1500,al_c/', img_url)
                        logger.info(f"Modified image URL: {image_url}")
                        break
            
            if product_name and image_url:
                logger.info(f"Found product details - Name: {product_name}, Image: {image_url}")
                return {
                    'name': product_name,
                    'image_url': image_url
                }
                
            return {'name': product_name, 'image_url': None}
                
        except Exception as e:
            logger.error(f"Error getting product details: {str(e)}")
            return None

    def process_raccoon_product(self, product_name, product_url, image_url, product_soup, domain_dir):
        """Process a single Raccoon product using new model structure"""
        try:
            session = Session()
            
            # Create sanitized filename
            safe_name = self.clean_filename(product_name)
            image_path = os.path.join(domain_dir, f"{safe_name}.png")
            
            # Find or create BaseProduct
            base_product = session.query(BaseProduct).filter_by(name=product_name).first()
            if not base_product:
                base_product = BaseProduct(name=product_name)
                session.add(base_product)
                session.flush()  # Get the ID
            
            # Check if vendor product exists
            existing_vendor_product = session.query(VendorProduct).filter_by(
                base_product_id=base_product.id,
                vendor_name='Raccoon Fireworks'
            ).first()
            
            # Check file existence
            file_exists = os.path.exists(image_path)
            if file_exists:
                self.logger.info(f"Image file exists at: {image_path}")
            else:
                self.logger.info(f"Image file does not exist at: {image_path}")
            
            # Only skip if both database record exists and file exists
            if existing_vendor_product and existing_vendor_product.vendor_image_url == image_url and file_exists:
                self.stats.images_existing += 1
                self.stats.db_unchanged += 1
                return False
                    
            downloaded = False
            if not file_exists:
                self.logger.info(f"Attempting to download image from: {image_url}")
                if self.download_image(image_url, image_path):
                    self.logger.info(f"Successfully downloaded image to: {image_path}")
                    self.stats.images_downloaded += 1
                    downloaded = True
                else:
                    self.logger.error(f"Failed to download image from: {image_url}")
                    
            # Create or update vendor product in database only if we have the image
            if downloaded or file_exists:
                if existing_vendor_product:
                    # Update existing vendor product
                    existing_vendor_product.vendor_product_url = product_url
                    existing_vendor_product.vendor_image_url = image_url
                    existing_vendor_product.local_image_path = image_path
                    session.commit()
                    self.stats.db_updates += 1
                else:
                    # Create new vendor product
                    new_vendor_product = VendorProduct(
                        base_product_id=base_product.id,
                        vendor_name='Raccoon Fireworks',
                        vendor_product_url=product_url,
                        vendor_image_url=image_url,
                        local_image_path=image_path
                    )
                    session.add(new_vendor_product)
                    session.commit()
                    self.stats.db_inserts += 1
                    
                return True
                
            return False
                
        except Exception as e:
            self.stats.errors += 1
            self.logger.error(f"Error processing product: {str(e)}")
            return False
        finally:
            if 'session' in locals():
                session.close()

def get_domain_folder(url):
    """Create folder name from domain"""
    parsed_url = urlparse(url)
    domain = parsed_url.netloc.replace('www.', '')
    return domain

def count_existing_images(directory):
    """Count number of images in directory"""
    if not os.path.exists(directory):
        os.makedirs(directory)
        return 0
    return len([f for f in os.listdir(directory) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp'))])

def get_next_page_url(soup, current_url):
    """Get URL for next page of products"""
    try:
        # Look for pagination elements
        pagination = soup.find('div', class_='pagination')
        if pagination:
            # Find the active page number
            current_page = pagination.find('span', class_='active')
            if current_page:
                current_num = int(current_page.text)
                next_page = current_num + 1
                
                # Check if next page link exists
                next_link = pagination.find('a', string=str(next_page))
                if next_link:
                    return urljoin(current_url, next_link['href'])
            
        # Alternative: Look for "Next" button
        next_button = soup.find('a', string=re.compile(r'Next|»|>'))
        if next_button and next_button.get('href'):
            return urljoin(current_url, next_button['href'])
                
        # If current URL has page parameter, increment it
        if 'page=' in current_url:
            current_page = int(re.search(r'page=(\d+)', current_url).group(1))
            return re.sub(r'page=\d+', f'page={current_page + 1}', current_url)
                
        # If no page parameter exists, add it
        if '?' in current_url:
            return f"{current_url}&page=2"
        return f"{current_url}?page=2"
                
    except Exception as e:
        logger.error(f"Error getting next page URL: {str(e)}")
        return None 

if __name__ == "__main__":
    scraper = RaccoonFireworksScraper()
    scraper.run() 