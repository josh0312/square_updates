from app.models.product import Product, Base
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

# Set up logger
logger = setup_logger('raccoon_scraper')

# Database setup
engine = create_engine(f'sqlite:///{paths.DB_FILE}')
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

def scrape_website(url, limit=5, base_dir=None, headers=None):
    """Main scraper function"""
    if not headers:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    domain = get_domain_folder(url)
    domain_dir = os.path.join(base_dir, domain) if base_dir else domain
    
    logger.info(f"Fetching content from: {url}")
    logger.info(f"Saving images to: {domain_dir}")
    
    response = get_with_ssl_ignore(url, headers=headers)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    
    existing_count = count_existing_images(domain_dir)
    logger.info(f"Found {existing_count} existing images in directory")
    
    successful_downloads = 0
    current_url = url
    page_number = 1
    empty_pages_count = 0  # Track consecutive empty pages
    
    while current_url and (limit == -1 or successful_downloads < limit):
        logger.info(f"\nProcessing page {page_number}...")
        response = get_with_ssl_ignore(current_url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find all product links
        product_links = soup.select('a[href*="/product-page/"]')
        
        unique_product_links = list(set([link.get('href') for link in product_links if link.get('href')]))
        logger.info(f"Found {len(unique_product_links)} unique product links")
        
        # Check for empty pages
        if len(unique_product_links) == 0:
            empty_pages_count += 1
            logger.info(f"Empty page found. {empty_pages_count} consecutive empty pages so far.")
            if empty_pages_count >= 3:
                logger.info("Found 3 consecutive empty pages. Assuming end of catalog reached.")
                break
        else:
            empty_pages_count = 0  # Reset counter when we find products
            
        # Process each product page
        for product_url in unique_product_links:
            if limit != -1 and successful_downloads >= limit:
                break
                    
            if not product_url.startswith(('http://', 'https://')):
                product_url = urljoin(current_url, product_url)
                
            logger.info(f"Visiting product page: {product_url}")
            try:
                # Get product details
                product_details = get_raccoon_product_details(product_url, headers)
                product_name = product_details.get('name')
                image_url = product_details.get('image_url')
                
                if product_name:
                    logger.info(f"Found product: {product_name}")
                    
                    if image_url:
                        logger.info(f"Found image URL: {image_url}")
                        was_updated = process_raccoon_product(
                            product_name, product_url, image_url, 
                            soup, domain_dir, headers
                        )
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
            logger.info(f"Moving to next page: {current_url}")
            page_number += 1
            time.sleep(2)
        else:
            logger.info("No more pages found.")
            break
    
    logger.info(f"\nFinal Summary:")
    logger.info(f"Pages processed: {page_number}")
    logger.info(f"Existing images found: {existing_count}")
    logger.info(f"New images downloaded: {successful_downloads}")
    logger.info(f"Total images in directory: {count_existing_images(domain_dir)}") 

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

def get_raccoon_product_details(product_url, headers):
    """Extract product details from a Raccoon product page"""
    try:
        response = get_with_ssl_ignore(product_url, headers=headers)
        response.raise_for_status()
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

def process_raccoon_product(product_name, product_url, image_url, soup, domain_dir, headers):
    """Process a single Raccoon product"""
    try:
        # Create sanitized filename
        safe_name = "".join(x for x in product_name.lower() if x.isalnum() or x in "._- ").replace(" ", "_")
        image_path = os.path.join(domain_dir, f"{safe_name}.png")
        
        # Check if product exists in database
        existing = session.query(Product).filter_by(
            site_name="Raccoon Fireworks",
            product_name=product_name
        ).first()
        
        if existing and existing.image_url == image_url:
            return False
                
        # Download image if it doesn't exist
        if not os.path.exists(image_path):
            os.makedirs(os.path.dirname(image_path), exist_ok=True)
            response = get_with_ssl_ignore(image_url, headers=headers)
            if response.status_code == 200:
                with open(image_path, 'wb') as f:
                    f.write(response.content)
            
        # Create or update product in database
        product_data = {
            'site_name': "Raccoon Fireworks",
            'product_name': product_name,
            'product_url': product_url,
            'image_url': image_url,
            'local_image_path': image_path,
            'last_updated': datetime.now()
        }
        
        if existing:
            for key, value in product_data.items():
                setattr(existing, key, value)
        else:
            new_product = Product(**product_data)
            session.add(new_product)
                
        session.commit()
        return True
            
    except Exception as e:
        logger.error(f"Error processing product: {str(e)}")
        if 'session' in locals():
            session.close()
        return False

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