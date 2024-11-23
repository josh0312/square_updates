import requests
from bs4 import BeautifulSoup
import time
from urllib.parse import urljoin, urlparse
import re
import logging
import os
from utils.logger import setup_logger

# Only initialize logger once
logger = logging.getLogger(__name__)

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

def get_next_page_url(soup, base_url, headers=None):
    """Extract the next page URL if it exists"""
    logger.info("Looking for next page...")
    
    # Set default headers if none provided
    if not headers:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
    
    # Debug current URL structure
    logger.info(f"Current URL: {base_url}")
    
    # Look for pagination links in the HTML
    pagination_links = soup.find_all('a', href=lambda x: x and ('currentpage=' in x or 'page=' in x))
    for link in pagination_links:
        logger.info(f"Found pagination link: {link}")
        
    # Get base URL without any currentpage parameter
    base_without_page = base_url.split('currentpage=')[0].rstrip('&')
    
    # Try to find the current page number
    current_page = 1
    if 'currentpage=' in base_url:
        try:
            # Get the last currentpage parameter value
            all_pages = re.findall(r'currentpage=(\d+)', base_url)
            if all_pages:
                current_page = int(all_pages[-1])
            logger.info(f"Current page: {current_page}")
        except:
            pass
            
    # Construct next page URL
    next_page = current_page + 1
    if '?' in base_without_page:
        next_url = f"{base_without_page}&currentpage={next_page}"
    else:
        next_url = f"{base_without_page}?currentpage={next_page}"
        
    logger.info(f"Trying constructed URL: {next_url}")
    
    try:
        response = requests.get(next_url, headers=headers, verify=False)
        if response.status_code == 200:
            # Verify the page has products
            next_soup = BeautifulSoup(response.text, 'html.parser')
            product_links = [link['href'] for link in next_soup.find_all('a', href=True) 
                           if 'productdtls.asp' in link['href']]
            if product_links:
                logger.info(f"Found {len(product_links)} products on next page")
                return next_url
            else:
                logger.info("No products found on next page")
                return None
    except Exception as e:
        logger.error(f"Error checking constructed URL: {str(e)}")
    
    logger.info("No valid next page URL found")
    return None

def get_pyrobuy_product_details(url, headers=None):
    """Extract product details from a PyroBuy product page"""
    try:
        response = requests.get(url, headers=headers, verify=False)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Debug the HTML structure
        logger.debug(f"Product page HTML structure:")
        logger.debug(soup.prettify()[:1000])
        
        # Find product name from meta og:title
        name = None
        title_meta = soup.find('meta', property='og:title')
        if title_meta:
            name = title_meta.get('content')
            
        # Find product image from meta og:image
        image_url = None
        image_meta = soup.find('meta', property='og:image')
        if image_meta:
            image_url = image_meta.get('content')
            if image_url and not image_url.startswith(('http://', 'https://')):
                image_url = urljoin(url, image_url)
        
        if name and image_url:
            logger.info(f"Found product details - Name: {name}, Image: {image_url}")
        else:
            logger.warning(f"Missing details - Name: {name}, Image: {image_url}")
            
        return {
            'name': name,
            'image_url': image_url
        }
        
    except Exception as e:
        logger.error(f"Error getting product details: {str(e)}")
        return {}

def process_pyrobuy_product(name, product_url, image_url, soup, domain_dir, headers):
    """Process a single PyroBuy product"""
    try:
        if not os.path.exists(domain_dir):
            os.makedirs(domain_dir)
            
        # Clean filename
        safe_name = "".join([c for c in name if c.isalnum() or c in (' ', '-', '_')]).rstrip()
        image_ext = os.path.splitext(image_url)[1].lower()
        if not image_ext:
            image_ext = '.png'  # Default to .png if no extension found
            
        filename = f"{safe_name}{image_ext}"
        filepath = os.path.join(domain_dir, filename)
        
        # Download image if it doesn't exist
        if not os.path.exists(filepath):
            logger.info(f"Downloading image to: {filepath}")
            response = requests.get(image_url, headers=headers, verify=False)
            response.raise_for_status()
            
            with open(filepath, 'wb') as f:
                f.write(response.content)
            return True
            
        return False
        
    except Exception as e:
        logger.error(f"Error processing product: {str(e)}")
        return False

def scrape_website(url, limit=5, base_dir=None, headers=None):
    """Main scraping function for PyroBuy"""
    # Create domain directory inside base_dir
    domain = get_domain_folder(url)
    domain_dir = os.path.join(base_dir, domain) if base_dir else domain
    
    logger.info(f"Fetching content from: {url}")
    logger.info(f"Saving images to: {domain_dir}")
    
    response = requests.get(url, headers=headers, verify=False)
    response.raise_for_status()
    logger.debug(f"Response content length: {len(response.text)}")
    logger.debug(f"Response content type: {response.headers.get('content-type')}")
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
        product_links = []
        
        # Look for links to product detail pages
        all_links = soup.find_all('a')
        logger.debug(f"Found {len(all_links)} total links")
        for link in all_links:
            href = link.get('href')
            if href:
                logger.debug(f"Found link: {href}")
                if 'productdtls.asp' in href:
                    product_links.append(href)
                    logger.debug(f"Added product link: {href}")

        unique_product_links = list(set([link for link in product_links if link]))
        logger.info(f"Found {len(unique_product_links)} unique product links")
        
        # Process each product page
        for product_url in unique_product_links:
            if limit != -1 and successful_downloads >= limit:
                break
                
            if not product_url.startswith(('http://', 'https://')):
                product_url = urljoin(current_url, product_url)
            
            logger.info(f"Visiting product page: {product_url}")
            try:
                product_details = get_pyrobuy_product_details(product_url, headers)
                
                if product_details.get('name') and product_details.get('image_url'):
                    logger.info(f"Found product: {product_details['name']}")
                    logger.info(f"Found image URL: {product_details['image_url']}")
                    
                    # Process the product
                    was_updated = process_pyrobuy_product(
                        product_details['name'],
                        product_url,
                        product_details['image_url'],
                        soup,
                        domain_dir,
                        headers
                    )
                    
                    if was_updated:
                        successful_downloads += 1
                        logger.info(f"Successfully processed product {successful_downloads} of {limit if limit != -1 else 'unlimited'}")
                    else:
                        logger.info("Product already exists with no changes")
                else:
                    logger.warning("Could not find product name or image URL")
            
                time.sleep(2)  # Delay between product pages
                
            except Exception as e:
                logger.error(f"Error processing product page: {str(e)}")
                continue

        # Get next page URL
        next_url = get_next_page_url(soup, current_url, headers)
        if next_url:
            logger.info(f"Moving to next page: {next_url}")
            current_url = next_url
            page_number += 1
            time.sleep(2)
        else:
            logger.info("No more pages to process")
            break
    
    logger.info(f"\nFinal Summary:")
    logger.info(f"Pages processed: {page_number}")
    logger.info(f"Existing images found: {existing_count}")
    logger.info(f"New images downloaded: {successful_downloads}")
    logger.info(f"Total images in directory: {count_existing_images(domain_dir)}") 