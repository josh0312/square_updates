import requests
from bs4 import BeautifulSoup
import time
import os
from urllib.parse import urljoin, urlparse
import logging

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

def get_category_links(soup, base_url):
    """Get all category links from the main page"""
    categories = []
    for link in soup.find_all('a', href=True):
        href = link['href']
        if '/fireworks/' in href and href != base_url:
            full_url = urljoin(base_url, href)
            if full_url not in categories:
                categories.append(full_url)
    return categories

def get_product_links(soup):
    """Extract all product links from the page"""
    product_links = []
    
    # Look for product links in the product grid
    for link in soup.find_all('a', href=True):
        href = link['href']
        if '/fireworks/' in href and not href.endswith('/fireworks/'):
            # Make sure it's a product page by checking URL structure
            parts = href.strip('/').split('/')
            if len(parts) >= 3 and parts[-2] in [
                'artillery-shells', 'fountains', 'finales', 
                'family-packs', 'firecrackers', 'novelties',
                'sparklers', 'roman-candles', 'show-to-go-cartons'
            ]:
                if href not in product_links:
                    product_links.append(href)
                    
    return list(set(product_links))  # Remove duplicates

def get_product_name_from_url(url):
    """Extract product name from URL when page title not found"""
    parts = url.strip('/').split('/')
    if len(parts) > 0:
        name = parts[-1].replace('-', ' ').title()
        # Clean up common URL artifacts
        name = name.replace('0', '').replace('1', '').replace('2', '')
        return name.strip()
    return None

def get_next_page_url(soup, current_url):
    """Find the next page URL"""
    # Try pagination links
    pagination = soup.find('nav', class_='pagination') or \
                soup.find('div', class_='pagination')
    if pagination:
        next_link = pagination.find('a', class_='next') or \
                   pagination.find('a', string=lambda x: x and ('Next' in x or '›' in x))
        if next_link and next_link.get('href'):
            return next_link['href']
    
    # Try page numbers
    current_page = 1
    if '/page/' in current_url:
        try:
            current_page = int(current_url.split('/page/')[1].strip('/'))
        except:
            pass
    
    # Try constructing next page URL
    base_url = current_url.split('/page/')[0].rstrip('/')
    next_url = f"{base_url}/page/{current_page + 1}/"
    
    # Verify next page exists and has different products
    try:
        current_products = set(link['href'] for link in soup.find_all('a', href=True) 
                             if '/fireworks/' in link['href'])
        
        response = requests.get(next_url, verify=False)
        if response.status_code == 200:
            next_soup = BeautifulSoup(response.text, 'html.parser')
            next_products = set(link['href'] for link in next_soup.find_all('a', href=True) 
                              if '/fireworks/' in link['href'])
            
            # Only return next URL if it has different products
            if next_products and next_products != current_products:
                return next_url
    except:
        pass
        
    return None

def scrape_website(url, limit=5, base_dir=None, headers=None):
    """Main scraper function"""
    if not headers:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    domain = get_domain_folder(url)
    domain_dir = os.path.join(base_dir, domain) if base_dir else domain
    if not os.path.exists(domain_dir):
        os.makedirs(domain_dir)
    
    logger.info(f"Fetching content from: {url}")
    logger.info(f"Saving images to: {domain_dir}")
    
    existing_count = count_existing_images(domain_dir)
    logger.info(f"Found {existing_count} existing images in directory")
    
    successful_downloads = 0
    processed_urls = set()
    current_url = url
    page_number = 1
    
    while current_url and (limit == -1 or successful_downloads < limit):
        if current_url in processed_urls:
            logger.info(f"Already processed URL: {current_url}")
            break
            
        logger.info(f"\nProcessing page {page_number}...")
        
        try:
            response = requests.get(current_url, headers=headers, verify=False)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Process each product
            product_links = get_product_links(soup)
            logger.info(f"Found {len(product_links)} product links")
            
            for product_url in product_links:
                if limit != -1 and successful_downloads >= limit:
                    break
                    
                full_url = urljoin(current_url, product_url)
                if full_url in processed_urls:
                    continue
                    
                # Skip category pages
                if full_url.endswith(('/fireworks/', '/fountains/', '/artillery-shells/', 
                                    '/finales/', '/family-packs/', '/firecrackers/',
                                    '/novelties/', '/sparklers/', '/roman-candles/',
                                    '/show-to-go-cartons/')):
                    continue
                    
                logger.info(f"Fetching product page: {full_url}")
                
                try:
                    product_response = requests.get(full_url, headers=headers, verify=False)
                    product_soup = BeautifulSoup(product_response.text, 'html.parser')
                    
                    # Get product name
                    name_elem = (
                        product_soup.find('h1', class_='product_title') or
                        product_soup.find('h1', class_='entry-title') or
                        product_soup.find('h1', {'data-elementor-setting-key': 'title'}) or
                        product_soup.find('h1')  # Fallback to any h1
                    )
                    
                    product_name = None
                    if name_elem:
                        product_name = name_elem.text.strip()
                    if not product_name:
                        product_name = get_product_name_from_url(full_url)
                        
                    if product_name:
                        logger.info(f"Found product: {product_name}")
                        
                        # Try multiple ways to find the product image
                        image_url = None
                        
                        # Try main product image
                        img = product_soup.find('img', class_='wp-post-image')
                        if img:
                            image_url = img.get('src') or img.get('data-src')
                            
                        # Try product gallery
                        if not image_url:
                            gallery = product_soup.find('div', class_='product-gallery') or \
                                    product_soup.find('div', class_='woocommerce-product-gallery')
                            if gallery:
                                img = gallery.find('img')
                                if img:
                                    image_url = img.get('src') or img.get('data-src')
                                    
                        # Try any product image
                        if not image_url:
                            for img in product_soup.find_all('img'):
                                src = img.get('src', '')
                                if '/wp-content/uploads/' in src and not any(x in src.lower() for x in ['icon', 'logo', 'placeholder', 'fullsize_anim']):
                                    image_url = src
                                    break
                                    
                        # Try data-src attributes
                        if not image_url:
                            for img in product_soup.find_all('img', {'data-src': True}):
                                src = img['data-src']
                                if not any(x in src.lower() for x in ['icon', 'logo', 'placeholder', 'fullsize_anim']):
                                    image_url = src
                                    break
                        
                        if image_url:
                            logger.info(f"Found image URL: {image_url}")
                            
                            # Clean filename and download image
                            clean_name = "".join(c for c in product_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
                            image_ext = os.path.splitext(image_url)[1].lower()
                            if not image_ext:
                                image_ext = '.jpg'  # Default extension
                            filename = f"{clean_name}{image_ext}"
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
                                    logger.error(f"Error downloading image {image_url}: {str(e)}")
                            else:
                                logger.info("Image already exists")
                        else:
                            logger.warning(f"No image found for product: {product_name}")
                    else:
                        logger.warning(f"No product name found for URL: {full_url}")
                        
                    processed_urls.add(full_url)
                    time.sleep(1)  # Polite delay between products
                    
                except Exception as e:
                    logger.error(f"Error processing product {full_url}: {str(e)}")
                    continue
                    
            # Get next page URL
            next_url = get_next_page_url(soup, current_url)
            if next_url and next_url not in processed_urls:
                logger.info(f"Moving to next page: {next_url}")
                current_url = next_url
                page_number += 1
                time.sleep(1)  # Polite delay between pages
            else:
                logger.info("No more pages to process")
                break
                
        except Exception as e:
            logger.error(f"Error in main scraping process: {str(e)}")
            break
            
    logger.info(f"\nFinal Summary:")
    logger.info(f"Pages processed: {len(processed_urls)}")
    logger.info(f"Existing images found: {existing_count}")
    logger.info(f"New images downloaded: {successful_downloads}")
    logger.info(f"Total images in directory: {count_existing_images(domain_dir)}") 