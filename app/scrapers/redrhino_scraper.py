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
from app.models.product import Product, Base
from datetime import datetime
import os
from app.utils.logger import setup_logger, log_product_found, log_image_download, log_database_update, log_metadata
from PIL import Image
import io
from app.utils.paths import paths  # Add this import
from app.utils.request_helpers import get_with_ssl_ignore

# Suppress only the specific warning
warnings.filterwarnings('ignore', category=InsecureRequestWarning)

# Set up logger
logger = setup_logger('redrhino_scraper')

# Database setup - Use paths.DB_FILE
engine = create_engine(f'sqlite:///{paths.DB_FILE}')
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

def handle_redrhino_site(current_url, soup, domain_dir, limit, headers):
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
                            was_updated = process_redrhino_product(
                                product_name, product_url, image_url, 
                                product_soup, domain_dir, headers
                            )
                            if was_updated:
                                successful_downloads += 1
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
    """Process a single Red Rhino product"""
    try:
        session = Session()
        log_product_found(logger, product_name, product_url)
        
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
                    else:
                        logger.error(f"Failed to download image, status code: {response.status_code}")
                        log_image_download(logger, "failed", new_filename)
                except Exception as e:
                    logger.error(f"Failed to download image: {str(e)}")
                    local_image_path = None
            else:
                log_image_download(logger, "exists", new_filename)
        
        # Store in database
        product_data = {
            'site_name': 'Red Rhino Fireworks',
            'product_name': product_name,
            'sku': sku,
            'description': description,
            'effects': effects,
            'product_url': product_url,
            'image_url': image_url,
            'local_image_path': local_image_path
        }
        
        # Log metadata found
        log_metadata(logger, product_data)
        
        # Check if product exists and update/insert as needed
        existing_product = session.query(Product).filter_by(
            site_name='Red Rhino Fireworks',
            product_name=product_name
        ).first()
        
        if existing_product:
            changes = {}
            for key, value in product_data.items():
                if getattr(existing_product, key) != value:
                    changes[key] = value
                    setattr(existing_product, key, value)
                    
            if changes:
                existing_product.updated_at = datetime.utcnow()
                session.commit()
                log_database_update(logger, "updated", product_name, changes)
                return True
            else:
                log_database_update(logger, "unchanged", product_name)
                return False
        else:
            new_product = Product(**product_data)
            session.add(new_product)
            session.commit()
            log_database_update(logger, "new", product_name)
            return True
            
    except Exception as e:
        logger.error(f"❌ Error processing Red Rhino product: {str(e)}")
        if session:
            session.rollback()
        return False
    finally:
        if session:
            session.close()

def scrape_website(url, limit=5, base_dir=None, headers=None):
    """Main scraper function for Red Rhino"""
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
            response = get_with_ssl_ignore(current_url, headers=headers)
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

if __name__ == "__main__":
    config = get_scraper_config('redrhino_scraper')
    if config and config['enabled']:
        for url in config['urls']:
            logger.info(f"\nProcessing URL: {url}")
            scrape_website(url, limit=config['limit'], base_dir=paths.DATA_DIR)