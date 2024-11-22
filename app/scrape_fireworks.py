import os
import requests
from bs4 import BeautifulSoup
import time
from urllib.parse import urljoin, urlparse
import re
import yaml
import logging
import sys

# Add logging configuration at the top of the file after imports
def setup_logging():
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('scraper.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logging()

# Base directory
BASE_DIR = '/Users/joshgoble/Downloads/firework_pics'

def load_websites():
    """Load website configurations from yaml file"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, 'websites.yaml')
    
    try:
        with open(config_path, 'r') as file:
            config = yaml.safe_load(file)
            return config.get('websites', [])
    except Exception as e:
        print(f"Error loading websites.yaml: {str(e)}")
        return []

def get_domain_folder(url):
    """Extract domain name from URL and create folder"""
    parsed_url = urlparse(url)
    # Remove www. if present and get domain name
    domain = parsed_url.netloc.replace('www.', '')
    domain_dir = os.path.join(BASE_DIR, domain)
    os.makedirs(domain_dir, exist_ok=True)
    return domain_dir

def get_filename_from_url(url):
    """Convert image URL to a clean filename"""
    # Parse the URL and get the path
    parsed_url = urlparse(url)
    path = parsed_url.path
    
    # Get the original filename without extension
    original_name = os.path.splitext(os.path.basename(path))[0]
    
    # Clean the filename: replace special chars with underscore
    clean_name = re.sub(r'[^a-zA-Z0-9]', '_', original_name)
    clean_name = re.sub(r'_+', '_', clean_name)  # Replace multiple underscores with single
    clean_name = clean_name.strip('_').lower()  # Remove leading/trailing underscores
    
    return f"{clean_name}.jpg"

def download_image(url, domain_dir):
    try:
        filename = get_filename_from_url(url)
        filepath = os.path.join(domain_dir, filename)
        
        # Check if file already exists
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
        'data-lazy', 'srcset', 'data-large_image', 'data-bgset'  # Added data-bgset for Shopify
    ]
    
    # Check for background image in parent container (Shopify specific)
    parent_container = img_tag.find_parent(class_='product-item__image-container')
    if parent_container and parent_container.get('data-bgset'):
        bgset = parent_container['data-bgset']
        # Get highest resolution image from bgset
        urls = [url.strip().split(' ')[0] for url in bgset.split(',')]
        if urls:
            return urls[-1]  # Return the last (typically highest res) URL
    
    for attr in possible_attrs:
        url = img_tag.get(attr)
        if url:
            # Handle srcset attribute (get the largest image)
            if attr == 'srcset':
                srcset_urls = url.split(',')
                if srcset_urls:
                    # Get the last URL which is typically the largest image
                    url = srcset_urls[-1].split()[0]
            
            # Skip base64 encoded images
            if url.startswith('data:'):
                continue
            
            # Skip small icons and thumbnails
            if any(skip in url.lower() for skip in [
                'icon', '-50x', '-150x', '-300x', 'thumb', 
                '50x50', '150x150', '300x300'
            ]):
                continue
                
            # Make relative URLs absolute
            if not url.startswith(('http://', 'https://')):
                url = urljoin(base_url, url)
                
            return url
    
    return None

def get_next_page_url(soup, base_url):
    """Extract the next page URL if it exists"""
    logger.debug("Looking for next page link...")
    
    # Method 1: Standard pagination (Winco)
    next_link = soup.find('a', class_='next') or \
                soup.find('a', class_='next page-numbers') or \
                soup.find('link', rel='next') or \
                soup.find('a', {'rel': 'next'})
    
    # Method 2: Elementor pagination (Red Rhino)
    if not next_link:
        logger.debug("Trying to find Elementor next page button...")
        next_buttons = soup.find_all('a', class_='elementor-button-link')
        for button in next_buttons:
            button_text = button.get_text(strip=True)
            if 'Next Page' in button_text:
                logger.debug(f"Found Elementor next button: {button}")
                next_link = button
                break
    
    # Method 3: Shopify Load More (World Class)
    if not next_link:
        logger.debug("Trying to find Shopify load more button...")
        load_more = soup.find('button', {'data-load-more': True}) or \
                   soup.find('button', class_=lambda x: x and 'load-more' in x.lower())
        if load_more:
            data_url = load_more.get('data-url')
            if data_url:
                next_url = urljoin(base_url, data_url)
                logger.debug(f"Found Shopify load more URL: {next_url}")
                return next_url
    
    # Method 3: Generic "Next" text links
    if not next_link:
        logger.debug("Trying to find generic next page link...")
        next_link = soup.find('a', string=lambda x: x and any(term in str(x).lower() for term in ['next', 'next page', '›', '»']))
    
    if next_link:
        # Get the href attribute
        href = next_link.get('href')
        if href and href != '#':  # Make sure href exists and isn't just a '#'
            next_url = href if href.startswith(('http://', 'https://')) else urljoin(base_url, href)
            logger.debug(f"Found next page URL: {next_url}")
            return next_url
        else:
            # For Red Rhino's case where we need to construct the URL
            current_page = int(base_url.split('page/')[1].split('/')[0]) if 'page/' in base_url else 1
            next_page = current_page + 1
            next_url = base_url.split('page/')[0].rstrip('/') + f'/page/{next_page}/'
            logger.debug(f"Constructed next page URL: {next_url}")
            return next_url
    
    logger.debug("No next page URL found")
    return None

def count_existing_images(domain_dir):
    """Count how many images already exist in the directory"""
    if not os.path.exists(domain_dir):
        return 0
    return len([f for f in os.listdir(domain_dir) if f.endswith(('.jpg', '.png', '.jpeg'))])

def scrape_firework_images(url, limit=5):
    # Update headers to include more browser-like values
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
        'Accept-Encoding': 'gzip, deflate',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://www.pyrobuy.com/',
        'Connection': 'keep-alive'
    }
    
    try:
        domain_dir = get_domain_folder(url)
        logger.info(f"Fetching content from: {url}")
        logger.info(f"Saving images to: {domain_dir}")
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        existing_count = count_existing_images(domain_dir)
        logger.info(f"Found {existing_count} existing images in directory")
        
        successful_downloads = 0
        skipped = 0
        skipped_existing = 0
        current_url = url
        page_number = 1
        
        while current_url and (limit == -1 or successful_downloads < limit):
            logger.info(f"\nProcessing page {page_number}...")
            response = requests.get(current_url, headers=headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Try different methods to find product links
            product_links = []
            
            # Method 1: PyroBuy specific links
            if 'pyrobuy.com' in current_url:
                logger.info("Trying PyroBuy specific links...")
                # Look for product images directly in table cells
                product_cells = soup.find_all('td', valign='top')
                for cell in product_cells:
                    # Get image from the cell
                    img = cell.find('img')
                    if img and img.get('src'):
                        image_url = urljoin(current_url, img.get('src'))
                        logger.debug(f"Found image URL: {image_url}")
                        if not any(skip in image_url.lower() for skip in ['spacer.gif', 'button', 'icon']):
                            if download_image(image_url, domain_dir):
                                successful_downloads += 1
                                time.sleep(1)
                    
                    # Get product detail link
                    detail_link = cell.find('a', href=lambda x: x and 'detail.asp' in x)
                    if detail_link:
                        product_links.append(detail_link)
            
            # Method 2: World Class specific product links
            if not product_links:
                logger.info("Trying World Class specific links...")
                # Look for links in the product grid
                product_links.extend(soup.find_all('a', href=lambda x: x and '/fireworks/artillery-shells/' in x))
                product_links.extend(soup.find_all('a', href=lambda x: x and '/fireworks/fountains/' in x))
                product_links.extend(soup.find_all('a', href=lambda x: x and '/fireworks/show-starters/' in x))
                product_links.extend(soup.find_all('a', href=lambda x: x and '/fireworks/finales/' in x))
                
                # Look for product titles that are links
                product_titles = soup.find_all('h4', class_='product-title')
                for title in product_titles:
                    link = title.find('a')
                    if link:
                        product_links.append(link)
            
            # Method 3: Standard WooCommerce links
            if not product_links:
                logger.info("Trying WooCommerce links...")
                product_links.extend(soup.find_all('a', class_='woocommerce-LoopProduct-link'))
            
            # Method 4: Red Rhino specific links
            if not product_links:
                logger.info("Trying Red Rhino links...")
                product_links.extend(soup.find_all('a', href=lambda x: x and '/firework/' in x))
            
            # Method 5: Generic product links
            if not product_links:
                logger.info("Trying generic product links...")
                product_links.extend(soup.find_all('a', class_=lambda x: x and 'product' in x.lower()))
                product_links.extend(soup.find_all('a', href=lambda x: x and 'product' in x.lower()))
            
            # Method 6: Any link containing an image
            if not product_links:
                logger.info("Trying links with images...")
                for img in soup.find_all('img'):
                    parent_link = img.find_parent('a')
                    if parent_link:
                        product_links.append(parent_link)
            
            unique_product_links = list(set([link.get('href') for link in product_links if link.get('href')]))
            logger.info(f"Found {len(unique_product_links)} unique product links")
            
            # Method 1: PyroBuy specific handling
            if 'pyrobuy.com' in current_url:
                logger.info("Using PyroBuy specific approach...")
                try:
                    # Find all product detail links first
                    detail_links = soup.find_all('a', href=lambda x: x and 'productdtls.asp' in x)
                    logger.info(f"Found {len(detail_links)} product detail links")
                    
                    # Visit each detail page to get the actual image URL
                    for link in detail_links:
                        if limit != -1 and successful_downloads >= limit:
                            break
                            
                        detail_url = urljoin(current_url, link['href'])
                        logger.info(f"Visiting detail page: {detail_url}")
                        
                        try:
                            detail_response = requests.get(
                                detail_url,
                                headers=headers,
                                verify=False,
                                timeout=10
                            )
                            detail_soup = BeautifulSoup(detail_response.text, 'html.parser')
                            
                            # Find the image tag in the detail page
                            img = detail_soup.find('img', src=lambda x: x and '/video/thumb/' in x)
                            if img and img.get('src'):
                                image_url = urljoin('http://pyrobuy.com', img['src'])
                                logger.info(f"Found image URL: {image_url}")
                                
                                try:
                                    image_response = requests.get(
                                        image_url,
                                        headers={
                                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124 Safari/537.36',
                                            'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                                            'Referer': 'http://pyrobuy.com/'
                                        },
                                        verify=False,
                                        timeout=10
                                    )
                                    
                                    if image_response.status_code == 200 and image_response.content:
                                        filename = os.path.basename(image_url)
                                        filepath = os.path.join(domain_dir, filename)
                                        
                                        with open(filepath, 'wb') as f:
                                            f.write(image_response.content)
                                        logger.info(f"Successfully downloaded: {filename}")
                                        successful_downloads += 1
                                        time.sleep(1)
                                    else:
                                        logger.warning(f"Failed to download {image_url}: Status {image_response.status_code}")
                                        
                                except Exception as e:
                                    logger.error(f"Error downloading {image_url}: {str(e)}")
                                    continue
                            
                            time.sleep(1)  # Be nice to their server
                            
                        except Exception as e:
                            logger.error(f"Error processing detail page {detail_url}: {str(e)}")
                            continue
                    
                    # Handle pagination
                    if successful_downloads < limit or limit == -1:
                        page_links = soup.find_all('a', href=lambda x: x and 'page=' in x)
                        if page_links:
                            current_page = int(re.search(r'page=(\d+)', current_url).group(1)) if 'page=' in current_url else 1
                            next_page = current_page + 1
                            next_url = f"{current_url}&page={next_page}" if '?' in current_url else f"{current_url}?page={next_page}"
                            return next_url
                            
                except Exception as e:
                    logger.error(f"Error processing PyroBuy page: {str(e)}")
                    
                return None
            
            # Visit each product page to get images
            for product_url in unique_product_links:
                if limit != -1 and successful_downloads >= limit:
                    break
                    
                if not product_url.startswith(('http://', 'https://')):
                    product_url = urljoin(current_url, product_url)
                
                logger.info(f"Visiting product page: {product_url}")
                try:
                    product_response = requests.get(product_url, headers=headers)
                    product_response.raise_for_status()
                    product_soup = BeautifulSoup(product_response.text, 'html.parser')
                    
                    # Try different methods to find product images
                    images = []
                    
                    # Method 1: PyroBuy specific product images
                    if 'pyrobuy.com' in product_url:
                        # Look for images in table cells
                        product_cells = product_soup.find_all('td', align='center')
                        for cell in product_cells:
                            img = cell.find('img')
                            if img:
                                images.append(img)
                    
                    # Method 2: World Class specific product images
                    if 'worldclassfireworks.com' in product_url:
                        # Look for images in wp-content uploads
                        images.extend(product_soup.find_all('img', src=lambda x: x and '/wp-content/uploads/' in x))
                        
                        # Look for images in product gallery
                        gallery = product_soup.find('div', class_='product-gallery')
                        if gallery:
                            images.extend(gallery.find_all('img'))
                    
                    # Method 3: Gallery images
                    images.extend(product_soup.find_all('img', class_=lambda x: x and 'gallery' in x.lower()))
                    
                    # Method 4: Any large images
                    images.extend(product_soup.find_all('img', class_=lambda x: x and ('large' in x.lower() or 'full' in x.lower())))
                    
                    # Method 5: Any images in product containers
                    product_containers = product_soup.find_all(class_=lambda x: x and 'product' in x.lower())
                    for container in product_containers:
                        images.extend(container.find_all('img'))
                    
                    logger.info(f"Found {len(images)} images on product page")
                    
                    for img in images:
                        if limit != -1 and successful_downloads >= limit:
                            break
                        
                        image_url = get_image_url(img, product_url)
                        if image_url:
                            if download_image(image_url, domain_dir):
                                successful_downloads += 1
                                time.sleep(1)
                
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
        logger.info(f"Images skipped (already exist): {skipped_existing}")
        logger.info(f"Images skipped (invalid): {skipped}")
        logger.info(f"Total images in directory: {count_existing_images(domain_dir)}")
                
    except Exception as e:
        logger.error(f"Error scraping website: {str(e)}", exc_info=True)

def scrape_all_websites():
    websites = load_websites()
    
    if not websites:
        print("No websites found in configuration file!")
        return
    
    for site in websites:
        if not site.get('enabled', True):
            print(f"\nSkipping disabled website: {site['name']}")
            continue
            
        print(f"\n{'='*50}")
        print(f"Processing: {site['name']}")
        print(f"{'='*50}")
        
        scrape_firework_images(
            url=site['url'],
            limit=site.get('limit', 5)
        )

if __name__ == "__main__":
    logger.info("Starting scraper...")
    try:
        scrape_all_websites()
    except Exception as e:
        logger.error("Fatal error in main execution", exc_info=True) 