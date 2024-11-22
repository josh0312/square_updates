import requests
from bs4 import BeautifulSoup
import time
from urllib.parse import urljoin
import re
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models.product import Product, Base
from datetime import datetime
import os
from urllib.parse import urlparse
from utils.logger import setup_logger, log_product_found, log_image_download, log_database_update, log_metadata
import sys

def setup_logger(name):
    """Setup logger with single handler to prevent duplicate messages"""
    logger = logging.getLogger(name)
    
    # Clear any existing handlers
    if logger.hasHandlers():
        logger.handlers.clear()
    
    # Set level
    logger.setLevel(logging.DEBUG)
    
    # Create formatter
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    # Create and add file handler
    file_handler = logging.FileHandler('scraper.log')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Create and add console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Prevent propagation to root logger
    logger.propagate = False
    
    return logger

logger = setup_logger(__name__)

# Database setup
engine = create_engine('sqlite:///fireworks.db')
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

def scrape_website(url, limit=5, base_dir=None, headers=None):
    # Set default headers if none provided
    if headers is None:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
        }
    
    # Use the passed base_dir
    BASE_DIR = base_dir
    
    def get_domain_folder(url):
        """Extract domain name from URL and create folder"""
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.replace('www.', '')
        domain_dir = os.path.join(BASE_DIR, domain)
        os.makedirs(domain_dir, exist_ok=True)
        return domain_dir

    def get_filename_from_url(url):
        """Convert image URL to a clean filename"""
        parsed_url = urlparse(url)
        path = parsed_url.path
        original_name = os.path.splitext(os.path.basename(path))[0]
        clean_name = re.sub(r'[^a-zA-Z0-9]', '_', original_name)
        clean_name = re.sub(r'_+', '_', clean_name).strip('_').lower()
        return f"{clean_name}.jpg"

    def download_image(url, domain_dir):
        try:
            filename = get_filename_from_url(url)
            filepath = os.path.join(domain_dir, filename)
            
            if os.path.exists(filepath):
                print(f"Skipping existing file: {filename}")
                return True
            
            response = requests.get(url)
            response.raise_for_status()
            
            with open(filepath, 'wb') as f:
                f.write(response.content)
            print(f"Successfully downloaded: {filename}")
            return True
        except Exception as e:
            print(f"Error downloading {url}: {str(e)}")
            return False

    def get_image_url(img_tag, base_url):
        """Try different attributes to find a valid image URL"""
        possible_attrs = [
            'data-src', 'src', 'data-original', 'data-lazy-src', 
            'data-lazy', 'srcset', 'data-large_image', 'data-bgset'
        ]
        
        for attr in possible_attrs:
            url = img_tag.get(attr)
            if url:
                if attr == 'srcset':
                    srcset_urls = url.split(',')
                    if srcset_urls:
                        url = srcset_urls[-1].split()[0]
                
                if url.startswith('data:'):
                    continue
                
                if any(skip in url.lower() for skip in [
                    'icon', '-50x', '-150x', '-300x', 'thumb', 
                    '50x50', '150x150', '300x300'
                ]):
                    continue
                    
                if not url.startswith(('http://', 'https://')):
                    url = urljoin(base_url, url)
                    
                return url
        
        return None

    def get_next_page_url(soup, base_url):
        """Extract the next page URL if it exists"""
        logger.debug("Looking for next page link...")
        
        next_link = soup.find('a', class_='next') or \
                    soup.find('a', class_='next page-numbers') or \
                    soup.find('link', rel='next') or \
                    soup.find('a', {'rel': 'next'})
        
        if next_link:
            href = next_link.get('href')
            if href and href != '#':
                next_url = href if href.startswith(('http://', 'https://')) else urljoin(base_url, href)
                logger.debug(f"Found next page URL: {next_url}")
                return next_url
        
        logger.debug("No next page URL found")
        return None

    def count_existing_images(domain_dir):
        """Count how many images already exist in the directory"""
        if not os.path.exists(domain_dir):
            return 0
        return len([f for f in os.listdir(domain_dir) if f.endswith(('.jpg', '.png', '.jpeg'))])
    
    def normalize_product_url(url):
        """Normalize product URLs to prevent duplicate processing"""
        # Remove trailing slashes
        url = url.rstrip('/')
        
        # Normalize common variations
        url = url.replace('-inch-', '-')
        url = url.replace('inches-', '-')
        url = url.replace('-in-', '-')
        
        return url

    def extract_effects(description):
        """Extract effects from product description"""
        if not description:
            return None  # Return None instead of empty list
        
        effects = []
        desc_text = description.lower()
        
        # Extract duration
        duration_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:second|sec)', desc_text)
        if duration_match:
            effects.append(f"Duration: {duration_match.group(0)}")
        
        # Extract shot count
        shot_match = re.search(r'(\d+)\s*(?:shot|shots)', desc_text)
        if shot_match:
            effects.append(f"Shot Count: {shot_match.group(0)}")
        
        # Extract specific effects
        effect_patterns = [
            r'(?:effect|effects):\s*([^.]*)',
            r'(?:color|colours):\s*([^.]*)',
            r'(?:burst|bursts):\s*([^.]*)',
        ]
        
        for pattern in effect_patterns:
            matches = re.finditer(pattern, desc_text)
            for match in matches:
                effects.append(match.group(1).strip())
        
        return '\n'.join(effects) if effects else None  # Return None if no effects found

    def process_winco_product(product_name, product_url, image_url, product_soup, domain_dir, headers):
        try:
            session = Session()
            log_product_found(logger, product_name, product_url)
            
            # Get metadata first
            price_elem = product_soup.find('p', class_='price')
            sku_elem = product_soup.find('span', class_='sku')
            desc_elem = product_soup.find('div', class_='woocommerce-product-details__short-description')
            category_elem = product_soup.find('nav', class_='woocommerce-breadcrumb')
            stock_elem = product_soup.find('p', class_='stock')
            
            # Get SKU
            sku = sku_elem.text.strip() if sku_elem else None
            
            # Download image if it exists
            local_image_path = None
            if image_url:
                filename = get_filename_from_url(image_url)
                filepath = os.path.join(domain_dir, filename)
                local_image_path = filepath
                
                if not os.path.exists(filepath):
                    logger.info(f"Downloading image: {image_url}")
                    try:
                        response = requests.get(image_url, headers=headers, verify=False)
                        if response.status_code == 200:
                            with open(filepath, 'wb') as f:
                                f.write(response.content)
                            log_image_download(logger, "success", filename)
                    except Exception as e:
                        logger.error(f"Failed to download image: {str(e)}")
                else:
                    log_image_download(logger, "exists", filename)
            
            # Check if product exists using SKU
            existing_product = session.query(Product).filter(
                Product.site_name == 'Winco Fireworks Texas',
                Product.sku == sku
            ).first() if sku else None
            
            # Log metadata found
            metadata = {
                'Price': price_elem.text.strip() if price_elem else 'Not found',
                'SKU': sku if sku else 'Not found',
                'Category': category_elem.text.strip() if category_elem else 'Not found',
                'Stock Status': stock_elem.text.strip() if stock_elem else 'Not found'
            }
            log_metadata(logger, metadata)
            
            # Store the product data
            product_data = {
                'site_name': 'Winco Fireworks Texas',
                'product_name': product_name,
                'sku': sku,
                'price': float(price_elem.text.strip().replace('$', '')) if price_elem and price_elem.text.strip() else None,
                'description': desc_elem.text.strip() if desc_elem else None,
                'category': category_elem.text.strip() if category_elem else None,
                'stock_status': stock_elem.text.strip() if stock_elem else None,
                'effects': extract_effects(desc_elem.text if desc_elem else None),
                'product_url': product_url,
                'image_url': image_url,
                'local_image_path': local_image_path
            }
            
            if existing_product:
                # Update only if there are actual changes
                changes = []
                for key, value in product_data.items():
                    current_value = getattr(existing_product, key)
                    if current_value != value:
                        changes.append(f"{key}: {current_value} -> {value}")
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
            logger.error(f"❌ Error processing Winco product: {str(e)}")
            if session:
                session.rollback()
            return False
        finally:
            if session:
                session.close()

    def handle_winco_site(current_url, soup, domain_dir, limit, headers):
        """Handle Winco Fireworks WooCommerce site"""
        logger.info("Using Winco Fireworks specific approach...")
        try:
            # Find all product containers first
            product_containers = soup.find_all('li', class_='product')
            logger.info(f"Found {len(product_containers)} product containers")
            
            successful_downloads = 0
            processed_count = 0
            
            for container in product_containers:
                processed_count += 1
                logger.info(f"Checking product {processed_count} of {limit if limit != -1 else 'unlimited'}")
                
                # Check total limit before processing each product
                if limit != -1 and successful_downloads >= limit:
                    logger.info(f"Reached limit of {limit} successful products")
                    return None
                    
                link = container.find('a', href=lambda x: x and '/product/' in x)
                
                if link:
                    product_url = urljoin(current_url, link['href'])
                    response = requests.get(product_url, headers=headers, verify=False)
                    product_soup = BeautifulSoup(response.text, 'html.parser')
                    
                    product_title = product_soup.find('h1', {'itemprop': 'name'})
                    if not product_title:
                        product_title = product_soup.find('h2', class_='product_title')
                    product_name = product_title.text.strip() if product_title else None
                    
                    if product_name:
                        logger.info(f"Found product: {product_name}")
                        
                        image_url = None
                        main_image = product_soup.find('img', class_='wp-post-image')
                        if main_image:
                            image_url = main_image.get('src')
                        if not image_url:
                            main_image = product_soup.find('img', class_='ilightbox-image')
                            if main_image:
                                image_url = main_image.get('src')
                        if not image_url:
                            main_image = product_soup.find('img', src=lambda x: x and '/uploads/' in x)
                            if main_image:
                                image_url = main_image.get('src')
                        
                        if image_url:
                            logger.info(f"Found image URL: {image_url}")
                            was_updated = process_winco_product(product_name, product_url, image_url, product_soup, domain_dir, headers)
                            if was_updated:
                                successful_downloads += 1
                                logger.info(f"Successfully processed product {successful_downloads} of {limit if limit != -1 else 'unlimited'}")
                                # Check limit after successful processing
                                if limit != -1 and successful_downloads >= limit:
                                    logger.info(f"Reached download limit of {limit}")
                                    return None
                            else:
                                logger.info("Product already exists with no changes")
                            
                        time.sleep(1)  # Polite delay between requests
            
            # Only look for next page if we haven't hit the limit
            if limit == -1 or successful_downloads < limit:
                next_link = soup.find('a', class_='next page-numbers')
                if next_link and next_link.get('href'):
                    logger.info("Found next page link")
                    return next_link['href']
            
            logger.info(f"Completed processing {successful_downloads} successful products")
                
        except Exception as e:
            logger.error(f"Error processing Winco page: {str(e)}")
            
        return None
    
    # Call the Winco-specific functions
    domain_dir = get_domain_folder(url)
    logger.info(f"Fetching content from: {url}")
    logger.info(f"Saving images to: {domain_dir}")
    
    response = requests.get(url, headers=headers, verify=False)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    
    existing_count = count_existing_images(domain_dir)
    logger.info(f"Found {existing_count} existing images in directory")
    
    next_url = handle_winco_site(url, soup, domain_dir, limit, headers)
    while next_url:
        response = requests.get(next_url, headers=headers, verify=False)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        next_url = handle_winco_site(next_url, soup, domain_dir, limit, headers) 