from app.scrapers.base_scraper import BaseScraper
from bs4 import BeautifulSoup
import time
import os
from urllib.parse import urljoin

class PyrobuyFireworksScraper(BaseScraper):
    def __init__(self):
        super().__init__('pyrobuy_scraper')

    def scrape_website(self, url, limit=5, base_dir=None):
        """Main scraping method with PyroBuy-specific logic"""
        domain_dir = os.path.join(base_dir, self.get_domain_folder(url)) if base_dir else self.get_domain_folder(url)
        
        self.logger.info(f"Starting scrape of {url}")
        self.logger.info(f"Saving images to {domain_dir}")
        
        successful_downloads = 0
        current_url = url
        
        while current_url and (limit == -1 or successful_downloads < limit):
            try:
                response = self.make_request(current_url)
                if not response:
                    break
                    
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # PyroBuy-specific product link extraction
                product_links = []
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    if 'productdtls.asp' in href:
                        # Convert relative URL to absolute URL
                        full_url = urljoin(current_url, href)
                        product_links.append(full_url)
                
                self.logger.info(f"Found {len(product_links)} product links")
                
                # Process each product with PyroBuy-specific logic
                for product_url in product_links:
                    if limit != -1 and successful_downloads >= limit:
                        break
                        
                    self.logger.info(f"Processing product URL: {product_url}")
                    product_response = self.make_request(product_url)
                    if not product_response:
                        continue
                        
                    product_soup = BeautifulSoup(product_response.text, 'html.parser')
                    
                    # PyroBuy-specific product data extraction
                    name = None
                    image_url = None
                    
                    title_meta = product_soup.find('meta', property='og:title')
                    if title_meta:
                        name = title_meta.get('content')
                        
                    image_meta = product_soup.find('meta', property='og:image')
                    if image_meta:
                        image_url = image_meta.get('content')
                        # Make sure image URL is absolute and handle both HTTP/HTTPS
                        if image_url:
                            if not image_url.startswith(('http://', 'https://')):
                                image_url = urljoin(product_url, image_url)
                            # Try to use domain from base URL for consistency
                            if 'pyrobuy.com' in current_url and 'pyrobuy.com' not in image_url:
                                image_url = urljoin(current_url, image_url.split('/')[-1])
                            self.logger.info(f"Resolved image URL: {image_url}")
                    
                    if name and image_url:
                        self.logger.info(f"Found product: {name}")
                        self.logger.info(f"Image URL: {image_url}")
                        
                        # Use base class utility for downloading
                        filename = f"{self.clean_filename(name)}.png"
                        filepath = os.path.join(domain_dir, filename)
                        
                        if not os.path.exists(filepath):
                            if self.download_image(image_url, filepath):
                                successful_downloads += 1
                                self.logger.info(f"Downloaded image for {name}")
                            else:
                                self.logger.error(f"Failed to download image for {name}")
                        else:
                            self.logger.info(f"Image already exists for {name}")
                                
                    time.sleep(1)  # Polite delay
                    
                # PyroBuy-specific next page logic
                next_link = None
                current_page = 1
                
                # First try: Look for currentpage parameter in URL
                if 'currentpage=' in current_url:
                    try:
                        current_page = int(current_url.split('currentpage=')[1].split('&')[0])
                        next_page = current_page + 1
                        # Construct next page URL
                        next_url = current_url.replace(f'currentpage={current_page}', f'currentpage={next_page}')
                        self.logger.info(f"Found next page URL from parameter: {next_url}")
                        current_url = next_url
                        time.sleep(2)
                    except Exception as e:
                        self.logger.error(f"Error parsing current page: {str(e)}")
                        break
                else:
                    # First page - add currentpage parameter
                    separator = '&' if '?' in current_url else '?'
                    next_url = f"{current_url}{separator}currentpage=2"
                    self.logger.info(f"Adding pagination to URL: {next_url}")
                    current_url = next_url
                    time.sleep(2)
                
                # Verify next page has products
                next_response = self.make_request(current_url)
                if not next_response:
                    self.logger.info("No valid next page found")
                    break
                    
                next_soup = BeautifulSoup(next_response.text, 'html.parser')
                next_products = [link['href'] for link in next_soup.find_all('a', href=True) 
                                if 'productdtls.asp' in link['href']]
                
                if not next_products:
                    self.logger.info("No products found on next page")
                    break
                    
            except Exception as e:
                self.logger.error(f"Error processing page: {str(e)}")
                break
                
        # Only print summary after all URLs are processed
        if url == self.config['urls'][-1]:  # Only on last URL
            self.stats.print_summary(self.logger)

# Add entry point for direct execution
if __name__ == "__main__":
    scraper = PyrobuyFireworksScraper()
    scraper.run()