#!/usr/bin/env python3
"""
Comprehensive Video Detection Scanner
Uses proven Selenium-based method to scan all product URLs from sitemap.
Outputs separate files for URLs with videos and URLs without videos.
"""

import requests
import re
import time
import json
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from typing import Dict, List

def fetch_sitemap(sitemap_url: str) -> str:
    """Fetch the sitemap XML content."""
    try:
        response = requests.get(sitemap_url, timeout=30)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"Error fetching sitemap: {e}")
        return ""

def extract_product_urls(sitemap_content: str) -> List[str]:
    """Extract product URLs that end with 4-digit numbers from sitemap."""
    pattern = r'https://shop\.nytexfireworks\.com/product/[^<]+/\d{4}'
    urls = re.findall(pattern, sitemap_content)
    return list(set(urls))

def setup_driver():
    """Set up Chrome driver with appropriate options."""
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    return driver

def analyze_page_for_video(driver: webdriver.Chrome, url: str) -> Dict:
    """Analyze a page for video content using our proven method."""
    results = {
        'url': url,
        'has_video': False,
        'see_it_in_action_found': False,
        'video_elements_count': 0,
        'video_iframes_count': 0,
        'video_iframe_sources': [],
        'video_related_elements_count': 0,
        'page_source_length': 0,
        'scan_timestamp': datetime.now().isoformat(),
        'error': None
    }
    
    try:
        print(f"  Loading: {url}")
        driver.get(url)
        
        # Wait for initial page load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        # Wait for dynamic content to load
        time.sleep(8)
        
        # Get the page source after JavaScript execution
        page_source = driver.page_source
        results['page_source_length'] = len(page_source)
        
        # Primary test: Check for "See it in Action" text
        if 'see it in action' in page_source.lower():
            results['see_it_in_action_found'] = True
        
        # Also check for elements with "See it in Action" text
        try:
            see_it_elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'See it in Action')]")
            if see_it_elements:
                results['see_it_in_action_found'] = True
        except Exception:
            pass
        
        # Look for video elements
        video_elements = driver.find_elements(By.TAG_NAME, 'video')
        results['video_elements_count'] = len(video_elements)
        
        # Look for iframe elements (could contain embedded videos)
        iframe_elements = driver.find_elements(By.TAG_NAME, 'iframe')
        video_iframes = []
        for iframe in iframe_elements:
            src = iframe.get_attribute('src') or ''
            if any(domain in src.lower() for domain in ['youtube', 'vimeo', 'player', 'video']):
                video_iframes.append(src)
        
        results['video_iframes_count'] = len(video_iframes)
        results['video_iframe_sources'] = video_iframes
        
        # Count video-related elements
        video_related_selectors = [
            "[class*='video']",
            "[data-video]",
            "[data-video-url]",
            "[class*='player']",
            "[id*='video']",
            "[id*='player']"
        ]
        
        video_related_count = 0
        for selector in video_related_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                video_related_count += len(elements)
            except Exception:
                continue
        
        results['video_related_elements_count'] = video_related_count
        
        # Determine if page has video content
        results['has_video'] = (
            results['see_it_in_action_found'] or
            results['video_elements_count'] > 0 or
            results['video_iframes_count'] > 0
        )
        
        return results
        
    except Exception as e:
        results['error'] = str(e)
        print(f"    ❌ Error: {e}")
        return results

def scan_all_urls(product_urls: List[str]) -> Dict[str, List[Dict]]:
    """Scan all URLs and categorize them by video presence."""
    results = {
        'urls_with_video': [],
        'urls_without_video': [],
        'urls_with_errors': []
    }
    
    driver = None
    try:
        driver = setup_driver()
        total_urls = len(product_urls)
        
        print(f"Starting scan of {total_urls} URLs...")
        print("="*60)
        
        for i, url in enumerate(product_urls, 1):
            print(f"[{i}/{total_urls}] Scanning: {url}")
            
            analysis = analyze_page_for_video(driver, url)
            
            if analysis['error']:
                results['urls_with_errors'].append(analysis)
                print(f"  ❌ Error occurred")
            elif analysis['has_video']:
                results['urls_with_video'].append(analysis)
                print(f"  ✅ VIDEO DETECTED")
                if analysis['see_it_in_action_found']:
                    print(f"    - 'See it in Action' found")
                if analysis['video_elements_count'] > 0:
                    print(f"    - {analysis['video_elements_count']} video elements")
                if analysis['video_iframes_count'] > 0:
                    print(f"    - {analysis['video_iframes_count']} video iframes")
            else:
                results['urls_without_video'].append(analysis)
                print(f"  ❌ No video detected")
            
            # Progress update every 25 URLs
            if i % 25 == 0:
                print(f"\n--- Progress Update ({i}/{total_urls}) ---")
                print(f"URLs with video: {len(results['urls_with_video'])}")
                print(f"URLs without video: {len(results['urls_without_video'])}")
                print(f"URLs with errors: {len(results['urls_with_errors'])}")
                print("="*60)
            
            # Small delay to be respectful to the server
            time.sleep(0.5)
    
    finally:
        if driver:
            driver.quit()
    
    return results

def save_results(results: Dict[str, List[Dict]]) -> None:
    """Save results to separate files."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Save URLs with videos
    urls_with_video_file = f"urls_with_video_{timestamp}.json"
    with open(urls_with_video_file, 'w') as f:
        json.dump(results['urls_with_video'], f, indent=2)
    
    # Save URLs without videos
    urls_without_video_file = f"urls_without_video_{timestamp}.json"
    with open(urls_without_video_file, 'w') as f:
        json.dump(results['urls_without_video'], f, indent=2)
    
    # Save URLs with errors
    if results['urls_with_errors']:
        urls_with_errors_file = f"urls_with_errors_{timestamp}.json"
        with open(urls_with_errors_file, 'w') as f:
            json.dump(results['urls_with_errors'], f, indent=2)
    
    # Create simple text files with just URLs
    urls_with_video_txt = f"urls_with_video_{timestamp}.txt"
    with open(urls_with_video_txt, 'w') as f:
        for result in results['urls_with_video']:
            f.write(f"{result['url']}\n")
    
    urls_without_video_txt = f"urls_without_video_{timestamp}.txt"
    with open(urls_without_video_txt, 'w') as f:
        for result in results['urls_without_video']:
            f.write(f"{result['url']}\n")
    
    # Create summary report
    summary_file = f"video_scan_summary_{timestamp}.txt"
    with open(summary_file, 'w') as f:
        f.write("Video Detection Scan Summary\n")
        f.write("="*50 + "\n")
        f.write(f"Scan completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Total URLs scanned: {len(results['urls_with_video']) + len(results['urls_without_video']) + len(results['urls_with_errors'])}\n")
        f.write(f"URLs with video: {len(results['urls_with_video'])}\n")
        f.write(f"URLs without video: {len(results['urls_without_video'])}\n")
        f.write(f"URLs with errors: {len(results['urls_with_errors'])}\n\n")
        
        f.write("Detection Method:\n")
        f.write("- Selenium-based dynamic content loading\n")
        f.write("- 8-second wait for JavaScript execution\n")
        f.write("- Primary indicator: 'See it in Action' text\n")
        f.write("- Secondary indicators: video elements, video iframes\n\n")
        
        f.write("Files Generated:\n")
        f.write(f"- {urls_with_video_file} (detailed JSON)\n")
        f.write(f"- {urls_without_video_file} (detailed JSON)\n")
        f.write(f"- {urls_with_video_txt} (simple URL list)\n")
        f.write(f"- {urls_without_video_txt} (simple URL list)\n")
        if results['urls_with_errors']:
            f.write(f"- {urls_with_errors_file} (error details)\n")
    
    return {
        'summary_file': summary_file,
        'urls_with_video_file': urls_with_video_file,
        'urls_without_video_file': urls_without_video_file,
        'urls_with_video_txt': urls_with_video_txt,
        'urls_without_video_txt': urls_without_video_txt
    }

def main():
    """Main function to run the comprehensive video detection scan."""
    sitemap_url = "https://shop.nytexfireworks.com/sitemap.xml"
    
    print("Comprehensive Video Detection Scanner")
    print("="*60)
    print("Using proven Selenium-based detection method")
    print("Primary indicator: 'See it in Action' text")
    print("Secondary indicators: video elements, video iframes")
    print("="*60)
    
    # Fetch sitemap
    print("Fetching sitemap...")
    sitemap_content = fetch_sitemap(sitemap_url)
    
    if not sitemap_content:
        print("❌ Failed to fetch sitemap. Exiting.")
        return
    
    # Extract product URLs
    print("Extracting product URLs...")
    product_urls = extract_product_urls(sitemap_content)
    print(f"Found {len(product_urls)} product URLs to scan")
    
    if not product_urls:
        print("❌ No product URLs found. Exiting.")
        return
    
    # Scan all URLs
    results = scan_all_urls(product_urls)
    
    # Save results
    print("\nSaving results...")
    file_info = save_results(results)
    
    # Print final summary
    print("\n" + "="*60)
    print("SCAN COMPLETED!")
    print("="*60)
    print(f"Total URLs scanned: {len(results['urls_with_video']) + len(results['urls_without_video']) + len(results['urls_with_errors'])}")
    print(f"URLs with video: {len(results['urls_with_video'])}")
    print(f"URLs without video: {len(results['urls_without_video'])}")
    print(f"URLs with errors: {len(results['urls_with_errors'])}")
    
    print(f"\nFiles created:")
    print(f"📄 Summary: {file_info['summary_file']}")
    print(f"✅ URLs with video (JSON): {file_info['urls_with_video_file']}")
    print(f"❌ URLs without video (JSON): {file_info['urls_without_video_file']}")
    print(f"✅ URLs with video (TXT): {file_info['urls_with_video_txt']}")
    print(f"❌ URLs without video (TXT): {file_info['urls_without_video_txt']}")
    
    if results['urls_with_video']:
        print(f"\nSample URLs with video:")
        for result in results['urls_with_video'][:5]:
            print(f"  ✅ {result['url']}")
            if result['video_iframe_sources']:
                print(f"     Video source: {result['video_iframe_sources'][0][:60]}...")
    
    if results['urls_without_video']:
        print(f"\nSample URLs without video:")
        for result in results['urls_without_video'][:5]:
            print(f"  ❌ {result['url']}")

if __name__ == "__main__":
    main() 