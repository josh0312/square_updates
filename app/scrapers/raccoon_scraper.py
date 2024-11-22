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
        
        next_link = soup.find('a', string=lambda x: x and 'Next' in x)
        
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
    
    def get_raccoon_product_details(product_url):
        response = requests.get(product_url, headers=headers, verify=False)
        soup = BeautifulSoup(response.text, 'html.parser')

        product_name = soup.select_one('h1[data-hook="product-title"]').text.strip()
        price = soup.select_one('span[data-hook="product-price"]').text.strip()
        sku = soup.select_one('span[data-hook="product-sku"]').text.strip()
        description = soup.select_one('div[data-hook="product-description"]').text.strip()
        category = soup.select_one('div[data-hook="breadcrumbs"]').text.strip()
        stock_status = soup.select_one('span[data-hook="product-inventory-status"]').text.strip()
        
        # Extract other product details as needed
        
        return {
            'name': product_name,
            'price': price,
            'sku': sku,
            'description': description,
            'category': category,
            'stock_status': stock_status,
            # Add other extracted details
        }

    def process_raccoon_product(product_name, product_url, image_url, product_soup, domain_dir, headers):
        try:
            session = Session()
            logger.info(f"Processing Raccoon product: {product_name}")
            
            # Get metadata
            product_details = get_raccoon_product_details(product_url)
            
            # Process image if URL found
            filepath = None
            image_downloaded = False
            if image_url:
                clean_name = re.sub(r'[^a-zA-Z0-9]', '_', product_name)
                clean_name = re.sub(r'_+', '_', clean_name).strip('_').lower()
                filename = f"{clean_name}.jpg"
                filepath = os.path.join(domain_dir, filename)
                
                if not os.path.exists(filepath):
                    image_response = requests.get(image_url, headers=headers, verify=False)
                    if image_response.status_code == 200 and len(image_response.content) > 5000:
                        with open(filepath, 'wb') as f:
                            f.write(image_response.content)
                        logger.info(f"Downloaded image: {filename}")
                        image_downloaded = True
            
            # Check if product exists
            existing_product = session.query(Product).filter_by(
                site_name='Raccoon Fireworks',
                product_name=product_name
            ).first()
            
            product_data = {
                'site_name': 'Raccoon Fireworks',
                'product_name': product_name,
                'price': product_details.get('price'),
                'sku': product_details.get('sku'),
                'description': product_details.get('description'),
                'category': product_details.get('category'),
                'stock_status': product_details.get('stock_status'),
                'product_url': product_url,
                'image_url': image_url,
                'local_image_path': filepath
            }
            
            if existing_product:
                # Update if needed
                has_changes = False
                for key, value in product_data.items():
                    if getattr(existing_product, key) != value:
                        setattr(existing_product, key, value)
                        has_changes = True
                
                if has_changes:
                    existing_product.updated_at = datetime.utcnow()
                    session.commit()
                    logger.info(f"Updated product: {product_name}")
                    return True
                return image_downloaded
            else:
                # Create new product
                new_product = Product(**product_data)
                session.add(new_product)
                session.commit()
                logger.info(f"Added new product: {product_name}")
                return True
                
        except Exception as e:
            logger.error(f"Error processing Raccoon product: {str(e)}")
            if session:
                session.rollback()
            return False
        finally:
            if session:
                session.close()
    
    # Call the Raccoon-specific functions
    domain_dir = get_domain_folder(url)
    logger.info(f"Fetching content from: {url}")
    logger.info(f"Saving images to: {domain_dir}")
    
    response = requests.get(url, headers=headers, verify=False)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    
    existing_count = count_existing_images(domain_dir)
    logger.info(f"Found {existing_count} existing images in directory")
    
    successful_downloads = 0
    current_url = url
    page_number = 1
    
    while current_url and (limit == -1 or successful_downloads < limit):
        logger.info(f"\nProcessing page {page_number}...")
        response = requests.get(current_url, headers=headers, verify=False)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find all product links
        product_links = soup.select('a[href*="/product-page/"]')
        
        unique_product_links = list(set([link.get('href') for link in product_links if link.get('href')]))
        logger.info(f"Found {len(unique_product_links)} unique product links")
        
        if len(unique_product_links) == 0:
            # Get next page URL
            next_url = get_next_page_url(soup, current_url)
            if next_url:
                logger.info(f"No product links found on current page. Moving to next page: {next_url}")
                current_url = next_url
                page_number += 1
                time.sleep(2)
                continue
            else:
                logger.info("No more product links found and no next page. Stopping scraper.")
                break
        
        # Process each product page
        for product_url in unique_product_links:
            if limit != -1 and successful_downloads >= limit:
                break
                
            if not product_url.startswith(('http://', 'https://')):
                product_url = urljoin(current_url, product_url)
            
            logger.info(f"Visiting product page: {product_url}")
            try:
                product_response = requests.get(product_url, headers=headers, verify=False)
                product_response.raise_for_status()
                product_soup = BeautifulSoup(product_response.text, 'html.parser')
                
                product_details = get_raccoon_product_details(product_url)
                product_name = product_details.get('name')
                
                if product_name:
                    logger.info(f"Found product: {product_name}")
                    
                    # Get product image
                    image_url = None
                    main_image = product_soup.select_one('img[id="comp-image"]')
                    if not main_image:
                        main_image = product_soup.select_one('div[data-mesh-id*="SITE_PAGES"] img')
                    if not main_image:
                        main_image = product_soup.select_one('img[src*="wixstatic.com/media"]')
                    
                    if main_image:
                        image_url = main_image.get('src')
                        if 'fill' in image_url:
                            image_url = re.sub(r'/v1/fill/[^/]+/', '/v1/fill/w_1500,h_1500,al_c/', image_url)
                        image_url = image_url.split('?')[0]  # Remove query parameters
                    
                    if image_url:
                        logger.info(f"Found image URL: {image_url}")
                        # Process the product and check if anything was updated
                        was_updated = process_raccoon_product(product_name, product_url, image_url, product_soup, domain_dir, headers)
                        if was_updated:
                            successful_downloads += 1
                            logger.info(f"Successfully processed product {successful_downloads} of {limit if limit != -1 else 'unlimited'}")
                        else:
                            logger.info("Product already exists with no changes")
                    else:
                        logger.warning(f"No image found for product: {product_name}")
            
                time.sleep(2)  # Delay between product pages
                
            except Exception as e:
                logger.error(f"Error processing product page: {str(e)}")
                continue
        
        # Get next page URL
        current_url = get_next_page_url(soup, current_url)
        if current_url:
            logger.info(f"Found next page: {current_url}")
            page_number += 1
            time.sleep(2)
        else:
            logger.info("No more pages found.")
    
    logger.info(f"\nFinal Summary:")
    logger.info(f"Pages processed: {page_number}")
    logger.info(f"Existing images found: {existing_count}")
    logger.info(f"New images downloaded: {successful_downloads}")
    logger.info(f"Total images in directory: {count_existing_images(domain_dir)}") 