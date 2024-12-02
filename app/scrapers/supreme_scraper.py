from app.scrapers.base_scraper import BaseScraper, ProductData
from bs4 import BeautifulSoup
import time
import os
from urllib.parse import urljoin
from datetime import datetime

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
            from app.models.product import Base
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
        # Use images/<website> directory structure
        domain_dir = os.path.join('images', self.get_domain_folder(url))
        if base_dir:
            domain_dir = os.path.join(base_dir, domain_dir)
        
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
        
        while current_url and (self.config['limit'] == -1 or self.stats.images_downloaded < self.config['limit']):
            try:
                response = self.make_request(current_url)
                if not response:
                    break
                    
                soup = BeautifulSoup(response.text, 'html.parser')
                self.stats.pages_processed += 1
                
                # Find product links in this category
                product_links = self.get_product_links(soup, current_url)
                self.logger.info(f"Found {len(product_links)} products in category")
                
                # Clear memory
                del soup
                del response
                
                # Process products
                for product in product_links:
                    # Check download limit
                    if self.config['limit'] != -1 and self.stats.images_downloaded >= self.config['limit']:
                        self.logger.info(f"Reached download limit of {self.config['limit']} images")
                        return
                        
                    self.logger.info(f"Processing product URL: {product['url']}")
                    
                    response = self.make_request(product['url'])
                    if not response:
                        continue
                        
                    product_soup = BeautifulSoup(response.text, 'html.parser')
                    product_data = self.extract_product_data(product_soup, product['url'], product['code'])
                    
                    # Clear memory
                    del product_soup
                    del response
                    
                    if product_data.name and product_data.image_url:
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
                        
                        # Save to database regardless of whether image was downloaded
                        try:
                            from app.models.product import Product
                            from sqlalchemy.orm import Session
                            from sqlalchemy import create_engine
                            
                            # Use absolute path for database
                            db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'products.db')
                            engine = create_engine(f'sqlite:///{db_path}')
                            session = Session(engine)
                            
                            # Create or update product record
                            product = session.query(Product).filter_by(
                                site_name='Supreme',
                                product_name=product_data.name.split(' - ')[0]  # Get just the code part
                            ).first()
                            
                            if not product:
                                product = Product(
                                    site_name='Supreme',
                                    product_name=product_data.name.split(' - ')[0],  # Product code
                                    sku=product_data.name.split(' - ')[0],  # Use code as SKU
                                    description=product_data.description,
                                    image_url=product_data.image_url,
                                    local_image_path=filepath,
                                    product_url=product_data.url,
                                    category=product_data.category if product_data.category else None,
                                    stock_status=product_data.stock_status if product_data.stock_status else None,
                                    effects=product_data.effects if product_data.effects else None,
                                    price=None,  # No price information available
                                    weight=None,  # No weight information available
                                    is_active=True
                                )
                                session.add(product)
                                self.logger.info(f"Added new product to database: {product_data.name}")
                                self.stats.db_inserts += 1
                            else:
                                product.image_url = product_data.image_url
                                product.local_image_path = filepath
                                product.description = product_data.description
                                product.updated_at = datetime.utcnow()
                                self.logger.info(f"Updated existing product in database: {product_data.name}")
                                self.stats.db_updates += 1
                            
                            session.commit()
                            session.close()
                            
                        except Exception as e:
                            self.logger.error(f"Error saving to database: {str(e)}")
                            import traceback
                            self.logger.error(f"Traceback: {traceback.format_exc()}")
                            self.stats.errors += 1
                    
                    # Clear memory
                    del product_data
                    time.sleep(2)  # Add delay between product requests
                
                # Get next page in this category
                current_url = self.get_next_page_url(soup, current_url)
                if current_url:
                    time.sleep(2)
                    
            except Exception as e:
                self.logger.error(f"Error processing category page: {str(e)}")
                self.stats.errors += 1
                break

    def __del__(self):
        """Clean up session on object destruction"""
        if self.session:
            self.session.close()

if __name__ == "__main__":
    scraper = SupremeFireworksScraper()
    scraper.run() 