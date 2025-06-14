from app.scrapers.base_scraper import BaseScraper, ProductData
from bs4 import BeautifulSoup
import time
import os
from urllib.parse import urljoin
from datetime import datetime
from app.models.product import BaseProduct, VendorProduct, Base
from app.utils.paths import paths

class SupremeFireworksScraper(BaseScraper):
    def __init__(self):
        super().__init__('supreme_scraper')
        self.base_url = 'http://www.spfireworks.com'
        self.session = None
        
        # Set up database path
        self.db_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data')
        self.db_path = os.path.join(self.db_dir, 'products.db')
        
        # Ensure database directory exists
        os.makedirs(self.db_dir, exist_ok=True)
        
        # Initialize database if it doesn't exist
        if not os.path.exists(self.db_path):
            from sqlalchemy import create_engine
            engine = create_engine(f'sqlite:///{self.db_path}')
            Base.metadata.create_all(engine)
            
    def make_request(self, url, timeout=30, max_retries=3, retry_delay=5):
        """Make HTTP request with better error handling and retries"""
        if not self.session:
            import requests
            self.session = requests.Session()
            self.session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            })
        
        for attempt in range(max_retries):
            try:
                response = self.session.get(url, timeout=timeout, verify=False)
                response.raise_for_status()
                return response
            except Exception as e:
                self.logger.warning(f"Attempt {attempt + 1}/{max_retries} failed: {str(e)}")
                if attempt < max_retries - 1:
                    import time
                    time.sleep(retry_delay)
                    continue
                self.logger.error(f"Error making request to {url}: {str(e)}")
                return None
                
    def get_category_links(self, soup, base_url):
        """Extract USA Products subcategory links"""
        links = []
        try:
            # First find the USA Products section
            usa_link = soup.find('a', string=lambda x: x and 'USA Products' in x)  # Updated to use string instead of text
            if not usa_link:
                self.logger.error("Could not find USA Products link")
                return links

            # Get the USA Products page
            usa_url = urljoin(base_url, usa_link['href'])
            response = self.make_request(usa_url)
            if not response:
                return links

            usa_soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find subcategories in USA Products
            # Look in the left menu for subcategories
            subcategories = usa_soup.find_all('a', href=lambda x: x and '/html/1/' in x)
            for subcat in subcategories:
                href = subcat.get('href')
                name = subcat.text.strip()
                # Skip non-product categories
                if any(x in name.lower() for x in ['news', 'info', 'about', 'contact']):
                    continue
                if href:
                    full_url = urljoin(base_url, href)
                    links.append({
                        'url': full_url,
                        'name': name
                    })
                    self.logger.info(f"Found subcategory: {name}")
                    
            # Clear memory
            del usa_soup
            del response
        
        except Exception as e:
            self.logger.error(f"Error getting category links: {str(e)}")
            self.stats.errors += 1
        
        return links
        
    def extract_product_data(self, product_soup: BeautifulSoup, product_url: str, known_code: str = None) -> ProductData:
        """Extract product data following base scraper pattern"""
        product_code = known_code  # Start with the code we found in the product list
        product_name = None
        image_url = None
        metadata = {}
        
        # Get product code and name from the table in the h1 tag
        h1_table = product_soup.find('h1')
        if h1_table:
            table = h1_table.find('table')
            if table:
                self.logger.debug("Found product table, contents:")
                self.logger.debug(table.prettify())
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) == 2:
                        # Get header text, handling any nested tags
                        header = ' '.join(cells[0].stripped_strings).lower()
                        # Get value text, handling any nested tags
                        value = ' '.join(cells[1].stripped_strings)
                        
                        self.logger.debug(f"Found table row - Header: '{header}', Value: '{value}'")
                        
                        # Store all metadata
                        clean_key = header.replace('item', '').replace('no.', '').strip()
                        metadata[clean_key] = value
                        
                        if any(x in header for x in ['item no', 'item  no', 'item   no']):
                            if not product_code:  # Only update if we don't have a code yet
                                product_code = value.strip()
                        elif 'item name' in header:
                            product_name = value.strip()
        
        # Get product image from the script that sets the image source
        scripts = product_soup.find_all('script', type='text/javascript')
        for script in scripts:
            if script.string and 'picPath' in script.string:
                for line in script.string.split('\n'):
                    if 'picPath =' in line:
                        path = line.split('=')[1].strip()
                        path = path.strip('"').strip("'").strip(';').strip()
                        if path.startswith('/upload/'):
                            image_url = urljoin(self.base_url, path).rstrip('"')
                            break
        
        if not product_code or not image_url:
            self.logger.debug("Raw HTML content:")
            self.logger.debug(product_soup.prettify())
            
        self.logger.debug(f"Found product code: {product_code}")
        self.logger.debug(f"Found product name: {product_name}")
        self.logger.debug(f"Found image URL: {image_url}")
        
        # Create product name with code if available
        full_name = f"{product_code} - {product_name}" if product_code and product_name else product_code or product_name
        
        # Format metadata as a string
        metadata_str = "\n".join(f"{k}: {v}" for k, v in metadata.items() if k not in ['name', ''])
        
        return ProductData(
            name=full_name,
            url=product_url,
            image_url=image_url,
            description=metadata_str,  # Include all metadata in description
            effects=None,  # No effects data available
            price=None,  # No price data available
            category=None,  # Category handled separately
            stock_status=None  # No stock status available
        )
    
    def get_product_links(self, soup: BeautifulSoup, base_url: str) -> list[dict]:
        """Extract product links following base scraper pattern"""
        links = []
        try:
            # Products are in li elements within scc_content
            content = soup.find('ul', class_='scc_content')
            if not content:
                self.logger.warning("No product content found")
                return links
            
            product_items = content.find_all('li')
            self.logger.info(f"Found {len(product_items)} potential product items")
            
            for item in product_items:
                # Look for the product link
                product_link = item.find('a', href=True)
                product_code = item.find('p', class_='case_title_pingming')
                
                if product_link and '/html/1/150/' in product_link['href']:
                    full_url = urljoin(base_url, product_link['href'])
                    code = None
                    if product_code:
                        code = product_code.text.strip()
                        if code.startswith('<font'):
                            code = BeautifulSoup(code, 'html.parser').text.strip()
                        self.logger.info(f"Found product: {code} - {full_url}")
                    links.append({
                        'url': full_url,
                        'code': code
                    })

        except Exception as e:
            self.logger.error(f"Error getting product links: {str(e)}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            self.stats.errors += 1
        
        return links
    
    def scrape_website(self, url, limit=5, base_dir=None):
        """Main scraping method with Supreme Fireworks specific logic"""
        # Use centralized images directory structure
        domain = self.get_domain_folder(url)
        domain_dir = os.path.join(paths.IMAGES_DIR, domain)
        
        self.logger.info(f"Starting scrape of {url}")
        self.logger.info(f"Saving images to {domain_dir}")
        
        try:
            # First get all category links
            response = self.make_request(url)
            if not response:
                return
                
            soup = BeautifulSoup(response.text, 'html.parser')
            categories = self.get_category_links(soup, url)
            self.logger.info(f"Found {len(categories)} categories")
            
            # Process each category
            for category in categories:
                if limit != -1 and self.stats.products_found >= limit:
                    break
                    
                self.logger.info(f"Processing category: {category['name']}")
                self.process_category(category['url'], domain_dir)
                
        except Exception as e:
            self.logger.error(f"Error in main scrape: {str(e)}")
            self.stats.errors += 1
            
        self.stats.print_summary(self.logger)
    
    def process_category(self, category_url, domain_dir):
        """Process a single category page and its products"""
        current_url = category_url
        processed_urls = set()  # Keep track of processed URLs to avoid loops
        
        while current_url and current_url not in processed_urls and (self.config['limit'] == -1 or self.stats.images_downloaded < self.config['limit']):
            try:
                self.logger.info(f"Processing category URL: {current_url}")
                processed_urls.add(current_url)
                
                response = self.make_request(current_url)
                if not response:
                    break
                    
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Get product links from current page
                product_links = self.get_product_links(soup, current_url)
                
                # Process each product
                for product in product_links:
                    if self.config['limit'] != -1 and self.stats.images_downloaded >= self.config['limit']:
                        break
                        
                    product_url = product['url']
                    product_response = self.make_request(product_url)
                    if not product_response:
                        continue
                        
                    product_soup = BeautifulSoup(product_response.text, 'html.parser')
                    product_data = self.extract_product_data(product_soup, product_url, product.get('code'))
                    
                    if product_data and product_data.image_url:
                        # Save image and update database
                        self.save_product(product_data, domain_dir)
                    
                    # Clear memory
                    del product_soup
                    del product_response
                    
                # Look for next page link
                next_page = soup.find('a', string=lambda x: x and ('下一页' in x or 'Next' in x or '>' in x))
                if next_page and next_page.get('href'):
                    next_url = urljoin(current_url, next_page['href'])
                    if next_url != current_url and next_url not in processed_urls:
                        current_url = next_url
                    else:
                        break  # No new pages to process
                else:
                    break  # No next page found
                    
                # Clear memory
                del soup
                del response
                
                self.stats.pages_processed += 1
                
            except Exception as e:
                self.logger.error(f"Error processing category page: {str(e)}")
                self.stats.errors += 1
                break  # Stop on error to avoid potential infinite loops
    
    def save_product(self, product_data, domain_dir):
        """Save product image and update database using new model structure"""
        if not product_data.name or not product_data.image_url:
            return
            
        self.stats.products_found += 1
        
        # Create clean filename from product name
        clean_name = self.clean_filename(product_data.name.lower())
        filename = f"{clean_name}.jpg"
        filepath = os.path.join(domain_dir, filename)
        
        if os.path.exists(filepath):
            self.stats.images_existing += 1
            self.logger.info(f"Image already exists for {product_data.name}")
        else:
            # Ensure image URL uses HTTP
            image_url = product_data.image_url
            if image_url.startswith('https://'):
                image_url = image_url.replace('https://', 'http://', 1)
            
            try:
                # Create directory if it doesn't exist
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                
                # Download image with HTTP
                response = self.session.get(image_url, timeout=30, verify=False)
                if response.status_code == 200:
                    with open(filepath, 'wb') as f:
                        f.write(response.content)
                    self.stats.images_downloaded += 1
                    self.logger.info(f"Successfully downloaded image for {product_data.name}")
                else:
                    self.stats.errors += 1
                    self.logger.error(f"Failed to download image: {response.status_code} for URL: {image_url}")
                
                # Clear memory
                del response
                
            except Exception as e:
                self.stats.errors += 1
                self.logger.error(f"Error downloading image for {product_data.name}: {str(e)}")
        
        # Save to database using new model structure
        try:
            from sqlalchemy.orm import Session
            from sqlalchemy import create_engine
            
            # Use absolute path for database
            engine = create_engine(f'sqlite:///{self.db_path}')
            session = Session(engine)
            
            # Extract product name (remove code part if present)
            product_name = product_data.name.split(' - ')[0] if ' - ' in product_data.name else product_data.name
            
            # Find or create BaseProduct
            base_product = session.query(BaseProduct).filter_by(name=product_name).first()
            if not base_product:
                base_product = BaseProduct(name=product_name)
                session.add(base_product)
                session.flush()  # Get the ID
            
            # Check if vendor product exists
            existing_vendor_product = session.query(VendorProduct).filter_by(
                base_product_id=base_product.id,
                vendor_name='Supreme Fireworks'
            ).first()
            
            if existing_vendor_product:
                # Update existing vendor product
                existing_vendor_product.vendor_sku = product_data.name.split(' - ')[0] if ' - ' in product_data.name else None
                existing_vendor_product.vendor_description = product_data.description
                existing_vendor_product.vendor_image_url = product_data.image_url
                existing_vendor_product.local_image_path = filepath
                existing_vendor_product.vendor_product_url = product_data.url
                existing_vendor_product.vendor_category = product_data.category if hasattr(product_data, 'category') else None
                session.commit()
                self.logger.info(f"Updated existing product in database: {product_data.name}")
                self.stats.db_updates += 1
            else:
                # Create new vendor product
                new_vendor_product = VendorProduct(
                    base_product_id=base_product.id,
                    vendor_name='Supreme Fireworks',
                    vendor_sku=product_data.name.split(' - ')[0] if ' - ' in product_data.name else None,
                    vendor_description=product_data.description,
                    vendor_image_url=product_data.image_url,
                    local_image_path=filepath,
                    vendor_product_url=product_data.url,
                    vendor_category=product_data.category if hasattr(product_data, 'category') else None
                )
                session.add(new_vendor_product)
                session.commit()
                self.logger.info(f"Added new product to database: {product_data.name}")
                self.stats.db_inserts += 1
            
            session.close()
            
        except Exception as e:
            self.logger.error(f"Error saving to database: {str(e)}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            self.stats.errors += 1
            
        # Add delay between products
        time.sleep(2)
    
    def __del__(self):
        """Clean up session on object destruction"""
        if self.session:
            self.session.close()

if __name__ == "__main__":
    scraper = SupremeFireworksScraper()
    scraper.run() 