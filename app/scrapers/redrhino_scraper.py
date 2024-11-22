import requests
from bs4 import BeautifulSoup
import time
from urllib.parse import urljoin, urlparse
import re
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models.product import Product, Base
from datetime import datetime
import os
from utils.logger import log_product_found, log_image_download, log_database_update, log_metadata

logger = logging.getLogger(__name__)

# Database setup
engine = create_engine('sqlite:///fireworks.db')
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

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
        
        # Get metadata - Red Rhino uses specific text patterns
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
            filename = os.path.basename(image_url).split('?')[0]  # Remove query parameters
            filepath = os.path.join(domain_dir, filename)
            local_image_path = filepath
            
            if not os.path.exists(filepath):
                try:
                    response = requests.get(image_url, headers=headers, verify=False, timeout=10)
                    if response.status_code == 200:
                        with open(filepath, 'wb') as f:
                            f.write(response.content)
                        log_image_download(logger, "success", filename)
                    else:
                        log_image_download(logger, "failed", filename)
                except Exception as e:
                    logger.error(f"Failed to download image: {str(e)}")
            else:
                log_image_download(logger, "exists", filename)
        
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

def handle_redrhino_site(current_url, soup, domain_dir, limit, headers):
    """Handle Red Rhino Fireworks site"""
    logger.info("Using Red Rhino specific approach...")
    
    # Define images to skip
    SKIP_IMAGES = [
        'RR_brass.png',
        'RR_brass.png.webp',
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
                product_links.append(link['href'])
                
        product_links = list(set(product_links))  # Remove duplicates
        logger.info(f"Found {len(product_links)} unique product links")
        
        for product_url in product_links:
            if limit != -1 and successful_downloads >= limit:
                logger.info(f"Reached limit of {limit} successful products")
                return None
                
            try:
                # Get product page
                logger.info(f"Fetching product page: {product_url}")
                response = requests.get(product_url, headers=headers, verify=False, timeout=10)
                product_soup = BeautifulSoup(response.text, 'html.parser')
                
                # Get product name
                product_name = None
                title_elem = product_soup.find('h1', class_='elementor-heading-title')
                if title_elem:
                    product_name = title_elem.text.strip()
                    
                if product_name:
                    logger.info(f"Found product: {product_name}")
                    
                    # Find image URL - Red Rhino uses lazy loading
                    image_url = None
                    img_elements = product_soup.find_all('img')
                    for img in img_elements:
                        # Check various attributes for the real image URL
                        possible_urls = [
                            img.get('data-src'),
                            img.get('data-lazy-src'),
                            img.get('src')
                        ]
                        
                        for url in possible_urls:
                            if url and not url.startswith('data:'):
                                # Skip common site images and small thumbnails
                                if any(skip in url.lower() for skip in SKIP_IMAGES):
                                    continue
                                    
                                # Only accept image URLs that look like product images
                                if ('.jpg' in url.lower() or '.png' in url.lower() or '.webp' in url.lower()):
                                    image_url = url
                                    break
                        
                        if image_url:
                            break
                    
                    if image_url:
                        logger.info(f"Found image URL: {image_url}")
                        was_updated = process_redrhino_product(
                            product_name, product_url, image_url, 
                            product_soup, domain_dir, headers
                        )
                        if was_updated:
                            successful_downloads += 1
                            logger.info(f"Successfully processed {successful_downloads} of {limit if limit != -1 else 'unlimited'}")
                            if limit != -1 and successful_downloads >= limit:
                                return None
                                
            except requests.exceptions.RequestException as e:
                logger.error(f"Error fetching product {product_url}: {str(e)}")
                continue
                
            time.sleep(1)  # Polite delay
            
        logger.info(f"Completed processing {successful_downloads} products")
        
    except Exception as e:
        logger.error(f"Error processing Red Rhino page: {str(e)}")
        logger.error(f"Error details:", exc_info=True)
        
    return None

def scrape_website(url, limit=5, base_dir=None, headers=None):
    """Main scraper function for Red Rhino"""
    if not headers:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    # Create domain directory for images
    domain = urlparse(url).netloc
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