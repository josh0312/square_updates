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
    
    # Extract shot count if present
    shot_match = re.search(r'(\d+)\s*(?:shot|shots)', desc_text)
    if shot_match:
        effects.append(f"Shot Count: {shot_match.group(0)}")
    
    # Extract specific effects
    if "effects:" in desc_text:
        effects_section = desc_text.split("effects:")[1].split(".")[0]
        effects.append(effects_section.strip())
        
    return '\n'.join(effects) if effects else None

def process_worldclass_product(product_name, product_url, image_url, product_soup, domain_dir, headers):
    """Process a single World Class product"""
    try:
        session = Session()
        log_product_found(logger, product_name, product_url)
        
        # Get metadata
        sku = None
        description = None
        
        # Look for SKU in product meta
        sku_elem = product_soup.find('div', text=re.compile(r'SKU:', re.I))
        if sku_elem:
            sku = sku_elem.text.replace('SKU:', '').strip()
            
        # Get description
        desc_elem = product_soup.find('div', class_='entry-content')
        if desc_elem:
            description = desc_elem.text.strip()
            
        effects = extract_effects(description)
        
        # Download image
        local_image_path = None
        if image_url:
            # Extract filename from URL
            filename = os.path.basename(image_url.split('?')[0])
            
            # Create full filepath
            filepath = os.path.join(domain_dir, filename)
            local_image_path = filepath
            
            # Only download if file doesn't exist
            if not os.path.exists(filepath):
                try:
                    response = requests.get(image_url, headers=headers, verify=False, timeout=10)
                    if response.status_code == 200:
                        # Ensure directory exists
                        os.makedirs(os.path.dirname(filepath), exist_ok=True)
                        
                        # Write file
                        with open(filepath, 'wb') as f:
                            f.write(response.content)
                        log_image_download(logger, "success", filename)
                    else:
                        logger.error(f"Failed to download image, status code: {response.status_code}")
                        log_image_download(logger, "failed", filename)
                except Exception as e:
                    logger.error(f"Failed to download image: {str(e)}")
                    local_image_path = None
            else:
                log_image_download(logger, "exists", filename)
        
        # Store in database
        product_data = {
            'site_name': 'World Class Fireworks',
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
            site_name='World Class Fireworks',
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
        logger.error(f"❌ Error processing World Class product: {str(e)}")
        if session:
            session.rollback()
        return False
    finally:
        if session:
            session.close()

def handle_worldclass_site(current_url, soup, domain_dir, limit, headers):
    """Handle World Class Fireworks site"""
    logger.info("Using World Class specific approach...")
    
    successful_downloads = 0
    
    try:
        # Start with artillery shells category directly
        artillery_url = "https://www.worldclassfireworks.com/fireworks/artillery-shells/"
        logger.info(f"Processing artillery shells category: {artillery_url}")
        
        try:
            response = requests.get(artillery_url, headers=headers, verify=False, timeout=10)
            category_soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find product links in category page
            product_links = []
            
            # Look for links in the grid
            grid = category_soup.find('div', class_='grid')
            if grid:
                for link in grid.find_all('a', href=True):
                    href = link['href']
                    if '/fireworks/artillery-shells/' in href and href.count('/') >= 4:
                        product_links.append(href)
                        logger.debug(f"Found product link in grid: {href}")
            
            # Also look for links in product-single divs
            product_divs = category_soup.find_all('div', class_='product-single')
            for div in product_divs:
                link = div.find('a', href=True)
                if link and '/fireworks/artillery-shells/' in link['href']:
                    product_links.append(link['href'])
                    logger.debug(f"Found product link in product-single: {link['href']}")
            
            product_links = list(set(product_links))  # Remove duplicates
            logger.info(f"Found {len(product_links)} products in artillery shells category")
            
            # Process each product
            for product_url in product_links:
                if limit != -1 and successful_downloads >= limit:
                    logger.info(f"Reached limit of {limit} successful products")
                    return None
                
                try:
                    logger.info(f"Fetching product page: {product_url}")
                    response = requests.get(product_url, headers=headers, verify=False, timeout=10)
                    product_soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # Get product name
                    product_name = None
                    title_elem = product_soup.find('h2')  # They use h2 for product titles
                    if title_elem:
                        product_name = title_elem.text.strip()
                    
                    if product_name:
                        logger.info(f"Found product: {product_name}")
                        
                        # Find image URL - Try multiple approaches
                        image_url = None
                        
                        # First try: Look in product-detail-image div
                        logger.debug("Looking for product-detail-image...")
                        detail_image_div = product_soup.find('div', class_='product-detail-image')
                        if detail_image_div:
                            img = detail_image_div.find('img')
                            if img:
                                image_url = img.get('src')
                                logger.debug(f"Found detail image: {image_url}")
                        
                        # Second try: Look in data-fancybox
                        if not image_url:
                            logger.debug("Looking for data-fancybox...")
                            fancybox = product_soup.find('a', {'data-fancybox': True})
                            if fancybox:
                                image_url = fancybox.get('data-src') or fancybox.get('href')
                                logger.debug(f"Found fancybox image: {image_url}")
                        
                        # Third try: Look for any wp-content/uploads image
                        if not image_url:
                            logger.debug("Looking for wp-content/uploads images...")
                            for img in product_soup.find_all('img'):
                                src = img.get('src', '')
                                if '/wp-content/uploads/' in src and not src.endswith(('-150x150', '-300x300', '-thumbnail')):
                                    image_url = src
                                    logger.debug(f"Found upload image: {image_url}")
                                    break
                        
                        if image_url:
                            # Clean up the URL if needed
                            if '?' in image_url:
                                image_url = image_url.split('?')[0]
                            
                            logger.info(f"Found image URL: {image_url}")
                            
                            # Download image
                            try:
                                # Extract filename from URL
                                filename = os.path.basename(image_url)
                                filepath = os.path.join(domain_dir, filename)
                                
                                if not os.path.exists(filepath):
                                    logger.info(f"Downloading image to: {filepath}")
                                    img_response = requests.get(image_url, headers=headers, verify=False, timeout=10)
                                    if img_response.status_code == 200:
                                        os.makedirs(os.path.dirname(filepath), exist_ok=True)
                                        with open(filepath, 'wb') as f:
                                            f.write(img_response.content)
                                        logger.info(f"Successfully downloaded image: {filename}")
                                        successful_downloads += 1
                                    else:
                                        logger.error(f"Failed to download image, status code: {img_response.status_code}")
                                else:
                                    logger.info(f"Image already exists: {filename}")
                                    
                            except Exception as e:
                                logger.error(f"Error downloading image: {str(e)}")
                        else:
                            logger.warning(f"No valid product image found for: {product_name}")
                            logger.debug("All img tags found:")
                            for img in product_soup.find_all('img'):
                                logger.debug(f"Image tag: {img}")
                                
                except requests.exceptions.RequestException as e:
                    logger.error(f"Error fetching product {product_url}: {str(e)}")
                    continue
                
                time.sleep(1)  # Polite delay between products
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching artillery shells category: {str(e)}")
        
        logger.info(f"Completed processing {successful_downloads} products")
        
    except Exception as e:
        logger.error(f"Error processing World Class page: {str(e)}")
        logger.error(f"Error details:", exc_info=True)
        
    return None

def scrape_website(url, limit=5, base_dir=None, headers=None):
    """Main scraper function for World Class"""
    if not headers:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    # Create domain directory for images
    domain = urlparse(url).netloc.replace('www.', '')
    domain_dir = os.path.join(base_dir, domain) if base_dir else domain
    os.makedirs(domain_dir, exist_ok=True)
    
    logger.info(f"Fetching content from: {url}")
    logger.info(f"Saving images to: {domain_dir}")
    
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
            
            next_url = handle_worldclass_site(current_url, soup, domain_dir, limit, headers)
            
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