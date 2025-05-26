from bs4 import BeautifulSoup
import requests
from typing import Dict, List, Tuple
import json
from datetime import datetime
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from app.utils.logger import setup_logger
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
from selenium.webdriver.chrome.service import Service

class NytexVideoScanner:
    def __init__(self):
        self.logger = setup_logger('nytex_video_scanner')
        self.base_url = "https://shop.nytexfireworks.com"
        
        # Set up requests session
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        })
        
        # Create results directory
        os.makedirs('video_scan_results', exist_ok=True)

    def scan_videos(self) -> Tuple[List[Dict], List[Dict]]:
        """Scans NyTex website for products with and without videos"""
        self.logger.info("="*50)
        self.logger.info(f"Starting NyTex video scan at {datetime.now()}")
        self.logger.info("="*50)
        
        products_with_videos = []
        products_without_videos = []
        
        try:
            # Get all product URLs first using Selenium
            product_urls = self._get_all_product_urls()
            self.logger.info(f"Found {len(product_urls)} products to scan")
            
            # Use more threads since we're just making requests
            with ThreadPoolExecutor(max_workers=25) as executor:
                futures = [executor.submit(self._check_product_page, url) for url in product_urls]
                
                for i, future in enumerate(as_completed(futures)):
                    try:
                        product_info = future.result()
                        if product_info['has_video']:
                            products_with_videos.append(product_info)
                            self.logger.info(f"✓ Found video for {product_info['product_name']}")
                        else:
                            products_without_videos.append(product_info)
                            self.logger.info(f"✗ No video found for {product_info['product_name']}")
                        
                        if i % 25 == 0:
                            self.logger.info(f"Progress: {i}/{len(product_urls)} products processed")
                            
                    except Exception as e:
                        self.logger.error(f"Error processing future: {str(e)}")
            
            # Save results and log summary
            self._save_results(products_with_videos, products_without_videos)
            
            self.logger.info("="*50)
            self.logger.info("Scan Complete - Summary:")
            self.logger.info(f"Total products scanned: {len(product_urls)}")
            self.logger.info(f"Products with videos: {len(products_with_videos)}")
            self.logger.info(f"Products without videos: {len(products_without_videos)}")
            self.logger.info("="*50)
            
            return products_with_videos, products_without_videos
            
        except Exception as e:
            self.logger.error(f"Error during video scan: {str(e)}", exc_info=True)
            return [], []
            
    def _get_all_product_urls(self) -> List[str]:
        """Get all product URLs from main shop page or cached file"""
        # Try to load from cache first
        try:
            with open('product_urls.json', 'r') as f:
                self.logger.info("Loading product URLs from cache...")
                return json.load(f)
        except FileNotFoundError:
            self.logger.info("No cached URLs found, fetching from website...")
            
            # Set up Selenium just for getting URLs
            options = webdriver.ChromeOptions()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            
            try:
                service = Service('/usr/local/bin/chromedriver')
                driver = webdriver.Chrome(service=service, options=options)
                
                # Get URLs from main page
                driver.get(self.base_url)
                time.sleep(5)  # Wait for initial load
                
                product_urls = set()
                last_count = 0
                no_change_count = 0
                
                while no_change_count < 3:
                    # Scroll down
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(2)
                    
                    # Get all product links
                    elements = driver.find_elements(By.CSS_SELECTOR, "a[href*='/product/']")
                    current_count = len(elements)
                    
                    if current_count > last_count:
                        self.logger.info(f"Found {current_count} products")
                        last_count = current_count
                        no_change_count = 0
                    else:
                        no_change_count += 1
                    
                    # Get URLs
                    for element in elements:
                        try:
                            url = element.get_attribute('href')
                            if url:
                                product_urls.add(url.split('?')[0])
                        except:
                            continue
                
                # Save URLs to cache
                urls = list(product_urls)
                with open('product_urls.json', 'w') as f:
                    json.dump(urls, f)
                
                driver.quit()
                return urls
                
            except Exception as e:
                self.logger.error(f"Error getting product URLs: {str(e)}")
                if 'driver' in locals():
                    driver.quit()
                return []
            
    def _check_product_page(self, url: str) -> Dict:
        """Check a single product page for video content"""
        product_name = url.split('/')[-2].replace('-', ' ').title()
        product_id = url.split('/')[-1]
        
        product_info = {
            'product_name': product_name,
            'url': url,
            'has_video': False,
            'video_type': None,
            'video_url': None
        }
        
        try:
            # Get the page content
            response = self.session.get(url, timeout=5)
            page_text = response.text
            
            # Debug first few responses
            if not hasattr(self, '_debug_count'):
                self._debug_count = 0
            if self._debug_count < 3:
                self.logger.info(f"\nDEBUG: Checking {url}")
                with open(f'debug_page_{self._debug_count}.html', 'w') as f:
                    f.write(page_text)
                self._debug_count += 1

            # Method 1: Look for video data in Square's bootstrap data
            bootstrap_match = re.search(r'window\.__BOOTSTRAP_STATE__\s*=\s*({.*?});', page_text, re.DOTALL)
            if bootstrap_match:
                try:
                    bootstrap_data = json.loads(bootstrap_match.group(1))
                    # Check for video in product data
                    if 'storeInfo' in bootstrap_data and 'products' in bootstrap_data['storeInfo']:
                        product_data = bootstrap_data['storeInfo']['products'].get(product_id, {})
                        if any('video' in str(x).lower() for x in product_data.values()):
                            product_info.update({
                                'has_video': True,
                                'video_type': 'youtube',
                                'video_url': url
                            })
                            return product_info
                except:
                    pass

            # Method 2: Look for video data in Square's dynamic bootstrap
            dynamic_match = re.search(r'window\.__DYNAMIC_BOOTSTRAP__\s*=\s*({.*?});', page_text, re.DOTALL)
            if dynamic_match:
                try:
                    dynamic_data = json.loads(dynamic_match.group(1))
                    if any('video' in str(x).lower() for x in dynamic_data.values()):
                        product_info.update({
                            'has_video': True,
                            'video_type': 'youtube',
                            'video_url': url
                        })
                        return product_info
                except:
                    pass

            # Method 3: Look for video elements in the HTML
            soup = BeautifulSoup(page_text, 'html.parser')
            video_elements = (
                soup.find_all('iframe', src=lambda x: x and ('youtube.com/embed' in x or 'youtu.be' in x)) or
                soup.find_all('div', {'data-component': 'ProductVideo'}) or
                soup.find_all('div', {'data-component': 'VideoPlayer'}) or
                soup.find_all('div', class_=lambda x: x and any(c in x.lower() for c in ['video-player', 'youtube-player']))
            )
            
            if video_elements:
                # Try to get actual video URL
                for elem in video_elements:
                    src = elem.get('src', '')
                    if src and 'youtube.com' in src:
                        product_info.update({
                            'has_video': True,
                            'video_type': 'youtube',
                            'video_url': src
                        })
                        return product_info
                
                # If no direct URL found but video elements exist
                product_info.update({
                    'has_video': True,
                    'video_type': 'youtube',
                    'video_url': url
                })
                return product_info

        except Exception as e:
            self.logger.error(f"Error checking product {url}: {str(e)}")
        
        return product_info
            
    def _save_results(self, with_videos: List[Dict], without_videos: List[Dict]) -> None:
        """Save scan results to JSON files"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        try:
            # Save products with videos
            with_videos_file = f'video_scan_results/products_with_videos_{timestamp}.json'
            with open(with_videos_file, 'w') as f:
                json.dump(with_videos, f, indent=2)
            self.logger.info(f"Saved products with videos to {with_videos_file}")
            
            # Save products without videos
            without_videos_file = f'video_scan_results/products_without_videos_{timestamp}.json'
            with open(without_videos_file, 'w') as f:
                json.dump(without_videos, f, indent=2)
            self.logger.info(f"Saved products without videos to {without_videos_file}")
            
        except Exception as e:
            self.logger.error(f"Error saving results: {str(e)}", exc_info=True) 

    def __del__(self):
        """Clean up Selenium driver"""
        if hasattr(self, 'driver'):
            self.driver.quit() 

    def _get_chrome_version(self) -> str:
        """Get Chrome version from the default macOS location"""
        import subprocess
        try:
            # Try to get Chrome version using default macOS path
            cmd = ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '--version']
            version = subprocess.check_output(cmd).decode('utf-8')
            # Extract just the version number
            version = version.strip().split()[-1].split('.')[0]
            return version
        except:
            self.logger.warning("Could not detect Chrome version, using latest")
            return "latest" 