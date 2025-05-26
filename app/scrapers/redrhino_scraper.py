import requests
from bs4 import BeautifulSoup
import time
from urllib.parse import urljoin, urlparse
import re
import logging
import warnings
from urllib3.exceptions import InsecureRequestWarning
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.product import BaseProduct, VendorProduct, Base
from datetime import datetime
import os
from app.utils.logger import setup_logger, log_product_found, log_image_download, log_database_update, log_metadata
from PIL import Image
import io
from app.utils.paths import paths  # Add this import
from app.utils.request_helpers import get_with_ssl_ignore
from app.scrapers.base_scraper import BaseScraper

# Suppress only the specific warning
warnings.filterwarnings('ignore', category=InsecureRequestWarning)

# Set up logger
logger = setup_logger('redrhino_scraper')

# Database setup - Use paths.DB_FILE
engine = create_engine(f'sqlite:///{paths.DB_FILE}')
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

class RedrhinoFireworksScraper(BaseScraper):
    def __init__(self):
        super().__init__('redrhino_scraper')
        
    def scrape_website(self, url, limit=5, base_dir=None, headers=None):
        """Main scraper function for Red Rhino"""
        if not headers:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }

        # Use centralized images directory structure
        domain = urlparse(url).netloc.replace('www.', '')
        domain_dir = os.path.join(paths.IMAGES_DIR, domain)
        os.makedirs(domain_dir, exist_ok=True)
        
        # Count existing images
        existing_images = len([f for f in os.listdir(domain_dir) if os.path.isfile(os.path.join(domain_dir, f))])
        logger.info(f"Found {existing_images} existing images in directory")
        
        page = 1
        current_url = url
        
        while current_url:
            logger.info(f"\nProcessing page {page}...")
            
            try:
                response = get_with_ssl_ignore(current_url, headers=headers)
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Call handle_redrhino_site as a method with self
                next_url = self.handle_redrhino_site(current_url, soup, domain_dir, limit, headers)
                
                if not next_url:
                    logger.info("No more product links found and no next page. Stopping scraper.")
                    break
                    
                current_url = next_url
                page += 1
                time.sleep(1)  # Polite delay between pages
                
            except Exception as e:
                logger.error(f"Error processing page {page}: {str(e)}")
                break
        
        # Only print summary after all URLs are processed
        if url == self.config['urls'][-1]:  # Only on last URL
            self.stats.print_summary(self.logger)

    def handle_redrhino_site(self, current_url, soup, domain_dir, limit, headers):
        """Handle Red Rhino Fireworks site"""
        logger.info("Using Red Rhino specific approach...")
        
        # Define images to skip - exact matches
        SKIP_IMAGES = [
            'RR_brass',  # Changed to match any version of the brass logo
            'logo',
            'header',
            'footer',
            'banner',
            'icon'
        ]
        
        successful_downloads = 0
        
        try:
            # Find all product links
            product_links = []
            for link in soup.find_all('a', href=True):
                if '/firework/' in link['href']:
                    # Make sure we have absolute URLs
                    full_url = link['href'] if link['href'].startswith(('http://', 'https://')) else urljoin(current_url, link['href'])
                    product_links.append(full_url)
                    
            product_links = list(set(product_links))  # Remove duplicates
            self.stats.products_found += len(product_links)
            logger.info(f"Found {len(product_links)} unique product links")
            
            # Process each product
            for product_url in product_links:
                if limit != -1 and successful_downloads >= limit:
                    return None  # Stop if we've hit our limit
                    
                try:
                    # Get product page
                    logger.info(f"Fetching product page: {product_url}")
                    response = get_with_ssl_ignore(product_url, headers=headers)
                    product_soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # Get product name
                    product_name = None
                    title_elem = product_soup.find('h1', class_='elementor-heading-title')
                    if title_elem:
                        product_name = title_elem.text.strip()
                        
                    if product_name:
                        logger.info(f"Found product: {product_name}")
                        
                        # Find image URL - Try multiple approaches
                        image_url = None
                        
                        # First try: Look for product images in specific sections
                        product_sections = product_soup.find_all('div', class_='elementor-widget-image')
                        for section in product_sections:
                            img_tags = section.find_all('img')
                            for img in img_tags:
                                src = img.get('src', '')
                                if not src:
                                    continue
                                    
                                # Skip immediately if it's the brass logo
                                if 'RR_brass' in src:
                                    logger.debug(f"Skipping brass logo image: {src}")
                                    continue
                                    
                                # Skip other unwanted images
                                if any(skip in src.lower() for skip in SKIP_IMAGES[1:]):  # Skip first item (RR_brass)
                                    logger.debug(f"Skipping unwanted image: {src}")
                                    continue
                                    
                                if '/wp-content/uploads/202' in src:
                                    image_url = src
                                    logger.debug(f"Found potential product image: {image_url}")
                                    break
                            if image_url:
                                break
                        
                        # Second try: Look for images in figure elements
                        if not image_url:
                            figures = product_soup.find_all('figure')
                            for figure in figures:
                                img = figure.find('img')
                                if img:
                                    src = img.get('src', '')
                                    if not src:
                                        continue
                                        
                                    # Skip brass logo
                                    if 'RR_brass' in src:
                                        logger.debug(f"Skipping brass logo image: {src}")
                                        continue
                                        
                                    if '/wp-content/uploads/202' in src and not any(skip in src.lower() for skip in SKIP_IMAGES[1:]):
                                        image_url = src
                                        logger.debug(f"Found potential product image in figure: {image_url}")
                                        break
                        
                        # Third try: Look for data-src attributes
                        if not image_url:
                            for img in product_soup.find_all('img', {'data-src': True}):
                                src = img['data-src']
                                
                                # Skip brass logo
                                if 'RR_brass' in src:
                                    logger.debug(f"Skipping brass logo image: {src}")
                                    continue
                                    
                                if '/wp-content/uploads/202' in src and not any(skip in src.lower() for skip in SKIP_IMAGES[1:]):
                                    image_url = src
                                    logger.debug(f"Found potential product image from data-src: {image_url}")
                                    break
                        
                        if image_url:
                            # Final check to ensure we're not using the brass logo
                            if 'RR_brass' not in image_url:
                                logger.info(f"Found valid product image URL: {image_url}")
                                was_updated, downloaded = process_redrhino_product(
                                    product_name, product_url, image_url, 
                                    product_soup, domain_dir, headers
                                )
                                if was_updated:
                                    successful_downloads += 1
                                    if downloaded:
                                        self.stats.images_downloaded += 1
                                    else:
                                        self.stats.images_existing += 1
                                    logger.info(f"Successfully processed {successful_downloads} of {limit if limit != -1 else 'unlimited'}")
                                    if limit != -1 and successful_downloads >= limit:
                                        return None
                            else:
                                logger.warning(f"Skipping brass logo image that made it through filters: {image_url}")
                        else:
                            logger.warning(f"No valid product image found for: {product_name}")
                            logger.debug("HTML content around product image area:")
                            image_area = product_soup.find('div', class_='elementor-widget-container')
                            if image_area:
                                logger.debug(image_area.prettify())
                                
                except requests.exceptions.RequestException as e:
                    logger.error(f"Error fetching product {product_url}: {str(e)}")
                    continue
                    
                time.sleep(1)  # Polite delay
                
            logger.info(f"Completed processing {successful_downloads} products")
            
            # Only look for next page if we haven't hit our limit
            if limit == -1 or successful_downloads < limit:
                next_url = get_next_page_url(soup, current_url)
                if next_url and next_url != current_url:  # Make sure we're not stuck on same page
                    logger.info(f"Found next page: {next_url}")
                    return next_url
                    
            logger.info("No more product links found and no next page. Stopping scraper.")
            return None
            
        except Exception as e:
            logger.error(f"Error processing Red Rhino page: {str(e)}")
            logger.error(f"Error details:", exc_info=True)
            return None

def get_next_page_url(soup, current_url):
    """Extract the next page URL if it exists"""
    logger.info("Looking for next page...")
    
    # First check if we're already on a page number
    current_page = 1
    if '/page/' in current_url:
        try:
            current_page = int(current_url.split('/page/')[1].rstrip('/'))
            logger.info(f"Currently on page {current_page}")
        except:
            pass
    
    # Get current products for comparison
    current_products = [link['href'] for link in soup.find_all('a', href=True) 
                       if '/firework/' in link['href']]
    
    if current_products:
        # Try next page
        test_url = current_url
        if '/page/' in test_url:
            # Already on a page, increment the number
            test_url = re.sub(r'/page/\d+/', f'/page/{current_page + 1}/', test_url)
        else:
            # First page, add page number
            test_url = test_url.rstrip('/') + f'/page/{current_page + 1}/'
            
        try:
            logger.info(f"Testing next page URL: {test_url}")
            response = get_with_ssl_ignore(test_url)
            if response.status_code == 200:
                test_soup = BeautifulSoup(response.text, 'html.parser')
                next_products = [link['href'] for link in test_soup.find_all('a', href=True) 
                               if '/firework/' in link['href']]
                
                # Check if next page has products and they're different
                if next_products and set(next_products) != set(current_products):
                    logger.info(f"Found valid page {current_page + 1} with {len(next_products)} different products")
                    return test_url
                else:
                    logger.info(f"Page {current_page + 1} has no new products")
            else:
                logger.info(f"Page {current_page + 1} returned status code {response.status_code}")
        except Exception as e:
            logger.error(f"Error testing next page URL: {str(e)}")
    
    logger.info("No next page found")
    return None

def extract_effects(description):
    """Extract effects from product description"""
    if not description:
        return None
        
    effects = []
    desc_text = description.lower()
    
    # Extract specific effects mentioned
    if "effects:" in desc_text:
        effects_section = desc_text.split("effects:")[1].split(".")[0]
        effects.append(effects_section.strip())
        
    # Extract shot count
    shot_match = re.search(r'(\d+)\s*(?:shot|shots)', desc_text)
    if shot_match:
        effects.append(f"Shot Count: {shot_match.group(0)}")
        
    return effects if effects else None

def process_redrhino_product(product_name, product_url, image_url, product_soup, domain_dir, headers):
    """Process a single Red Rhino product using new model structure"""
    try:
        session = Session()
        downloaded = False  # Track if we downloaded a new image
        
        # Get metadata first
        sku = None
        description = None
        
        # Look for SKU and description in all text elements
        for elem in product_soup.find_all(['div', 'p', 'span']):
            text = elem.get_text(strip=True)
            if text:
                # Look for SKU
                if 'sku:' in text.lower() or 'item #' in text.lower():
                    sku = text.split(':')[-1].strip()
                # Look for description
                elif len(text) > 50 and not text.startswith('http'):
                    description = text
        
        effects = extract_effects(description)
        
        # Download image
        local_image_path = None
        if image_url:
            # Extract original filename from URL
            original_filename = os.path.basename(image_url.split('?')[0])
            
            # Get the code part (usually starts with numbers)
            base_name = original_filename.split('.')[0]  # Get part before first dot
            
            # Clean product name
            clean_product_name = re.sub(r'[^\w\s-]', '', product_name)
            clean_product_name = re.sub(r'\s+', '-', clean_product_name).strip('-')
            
            # Remove dimensions (like 395x1024) from base_name
            base_name = re.sub(r'-\d+x\d+', '', base_name)
            
            # Extract any product code (letters and/or numbers at start)
            product_code = re.match(r'^[A-Za-z0-9]+', base_name)
            
            # Always include both code (if available) and product name
            if product_code:
                new_filename = f"{product_code.group(0)}-{clean_product_name}.png"
            else:
                new_filename = f"{clean_product_name}.png"
            
            # Create full filepath
            filepath = os.path.join(domain_dir, new_filename)
            local_image_path = filepath
            
            # Only download if file doesn't exist
            if not os.path.exists(filepath):
                try:
                    response = get_with_ssl_ignore(image_url, headers=headers)
                    if response.status_code == 200:
                        os.makedirs(os.path.dirname(filepath), exist_ok=True)
                        
                        # Convert webp to PNG if needed
                        image = Image.open(io.BytesIO(response.content))
                        
                        # Convert to RGB if needed (in case of RGBA)
                        if image.mode in ('RGBA', 'LA'):
                            background = Image.new('RGB', image.size, (255, 255, 255))
                            background.paste(image, mask=image.split()[-1])
                            image = background
                        
                        # Save as PNG
                        image.save(filepath, 'PNG', optimize=True)
                        
                        log_image_download(logger, "success", new_filename)
                        downloaded = True  # Set downloaded flag
                    else:
                        logger.error(f"Failed to download image, status code: {response.status_code}")
                        log_image_download(logger, "failed", new_filename)
                except Exception as e:
                    logger.error(f"Failed to download image: {str(e)}")
                    local_image_path = None
            else:
                log_image_download(logger, "exists", new_filename)
        
        # Find or create BaseProduct
        base_product = session.query(BaseProduct).filter_by(name=product_name).first()
        if not base_product:
            base_product = BaseProduct(name=product_name)
            session.add(base_product)
            session.flush()  # Get the ID
        
        # Check if vendor product exists
        existing_vendor_product = session.query(VendorProduct).filter_by(
            base_product_id=base_product.id,
            vendor_name='Red Rhino Fireworks'
        ).first()
        
        if existing_vendor_product:
            # Update existing vendor product
            changes = {}
            updates = {
                'vendor_sku': sku,
                'vendor_description': description,
                'vendor_product_url': product_url,
                'vendor_image_url': image_url,
                'local_image_path': local_image_path
            }
            
            for field, value in updates.items():
                if getattr(existing_vendor_product, field) != value:
                    changes[field] = value
                    setattr(existing_vendor_product, field, value)
                    
            if changes:
                session.commit()
                log_database_update(logger, "updated", product_name, changes)
                return True, downloaded
            else:
                log_database_update(logger, "unchanged", product_name)
                return False, downloaded
        else:
            # Create new vendor product
            new_vendor_product = VendorProduct(
                base_product_id=base_product.id,
                vendor_name='Red Rhino Fireworks',
                vendor_sku=sku,
                vendor_description=description,
                vendor_product_url=product_url,
                vendor_image_url=image_url,
                local_image_path=local_image_path
            )
            session.add(new_vendor_product)
            session.commit()
            log_database_update(logger, "new", product_name)
            return True, downloaded
            
    except Exception as e:
        logger.error(f"❌ Error processing Red Rhino product: {str(e)}")
        if 'session' in locals():
            session.rollback()
        return False, False
    finally:
        if 'session' in locals():
            session.close()

if __name__ == "__main__":
    scraper = RedrhinoFireworksScraper()
    scraper.run()