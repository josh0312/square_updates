#!/usr/bin/env python3
"""
Script to download MP4 files from multiple video directories that match
vendor codes for Pyro Buy products and rename them appropriately.
"""

import pandas as pd
import requests
from bs4 import BeautifulSoup
import os
import re
from urllib.parse import urljoin, urlparse
import time
from datetime import datetime

def load_pyrobuy_products(excel_file):
    """Load Pyro Buy products and their vendor codes from the Excel file."""
    try:
        df = pd.read_excel(excel_file)
        pyrobuy_df = df[df['Vendor'] == 'Pyro Buy'].copy()
        
        print(f"Found {len(pyrobuy_df)} Pyro Buy products")
        
        # Create a mapping of vendor codes to product names
        vendor_code_map = {}
        for _, row in pyrobuy_df.iterrows():
            vendor_code = str(row['Vendor_Code']).strip()
            product_name = str(row['Product_Name']).strip()
            vendor_code_map[vendor_code] = product_name
            
        return vendor_code_map
    except Exception as e:
        print(f"Error loading Pyro Buy products: {e}")
        return {}

def get_video_file_list(url):
    """Scrape the video directory to get list of MP4 files."""
    try:
        print(f"Fetching video file list from {url}...")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find all links that end with .mp4
        mp4_files = []
        for link in soup.find_all('a'):
            href = link.get('href')
            if href and href.endswith('.mp4'):
                # Clean up the filename (remove URL encoding if present)
                filename = href
                if '%20' in filename:
                    filename = filename.replace('%20', ' ')
                mp4_files.append(filename)
        
        print(f"Found {len(mp4_files)} MP4 files in the directory")
        return mp4_files
        
    except Exception as e:
        print(f"Error fetching video file list from {url}: {e}")
        return []

def normalize_vendor_code(code):
    """Normalize vendor code for matching."""
    if not code:
        return ""
    # Remove common separators and convert to uppercase
    normalized = str(code).upper().replace('-', '').replace('_', '').replace(' ', '')
    return normalized

def find_matching_files(mp4_files, vendor_codes, source_url):
    """Find MP4 files that match vendor codes."""
    matches = []
    
    # Create normalized vendor code lookup
    normalized_vendor_codes = {}
    for vendor_code in vendor_codes:
        normalized = normalize_vendor_code(vendor_code)
        normalized_vendor_codes[normalized] = vendor_code
    
    print(f"\nLooking for matches in {source_url}...")
    
    for mp4_file in mp4_files:
        # Extract potential vendor code from filename
        # Remove .mp4 extension
        base_name = mp4_file.replace('.mp4', '')
        
        # Try different patterns to extract vendor code
        patterns = [
            r'^([A-Z0-9\-_]+)',  # Start of filename
            r'([A-Z0-9\-_]+)$',  # End of filename
            r'^([A-Z]+\-?[0-9A-Z\-_]+)',  # Letter prefix with numbers/letters
        ]
        
        for pattern in patterns:
            match = re.search(pattern, base_name.upper())
            if match:
                potential_code = match.group(1)
                normalized_potential = normalize_vendor_code(potential_code)
                
                # Check if this matches any of our vendor codes
                if normalized_potential in normalized_vendor_codes:
                    original_vendor_code = normalized_vendor_codes[normalized_potential]
                    matches.append({
                        'filename': mp4_file,
                        'vendor_code': original_vendor_code,
                        'extracted_code': potential_code,
                        'source_url': source_url
                    })
                    print(f"Match found: {mp4_file} -> {original_vendor_code} (from {source_url})")
                    break
    
    return matches

def sanitize_filename(filename):
    """Sanitize filename for filesystem compatibility."""
    # Remove or replace invalid characters
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    
    # Remove extra spaces and limit length
    filename = re.sub(r'\s+', ' ', filename).strip()
    if len(filename) > 200:  # Reasonable filename length limit
        filename = filename[:200]
    
    return filename

def download_file(url, local_filename):
    """Download a file from URL to local filesystem."""
    try:
        print(f"Downloading {url}...")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, stream=True, timeout=60)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        downloaded_size = 0
        
        with open(local_filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded_size += len(chunk)
                    
                    # Show progress for larger files
                    if total_size > 0 and downloaded_size % (1024 * 1024) == 0:  # Every MB
                        progress = (downloaded_size / total_size) * 100
                        print(f"  Progress: {progress:.1f}% ({downloaded_size / (1024*1024):.1f}MB / {total_size / (1024*1024):.1f}MB)")
        
        print(f"  Downloaded: {local_filename} ({downloaded_size / (1024*1024):.1f}MB)")
        return True
        
    except Exception as e:
        print(f"  Error downloading {url}: {e}")
        return False

def download_pyrobuy_videos():
    """Main function to download matching Pyro Buy videos from multiple sources."""
    
    # Configuration
    excel_file = "url_catalog_matches_20250527_104746.xlsx"
    
    # Multiple video URLs to check for Pyro Buy products
    video_urls = [
        "https://pyrobuy.com/video/",
        "http://dominatorfireworks.com/video/",
        "http://www.oxfireworks.com/video/"
    ]
    
    download_dir = "pyrobuy_videos"
    
    # Create download directory
    os.makedirs(download_dir, exist_ok=True)
    
    # Load Pyro Buy products and vendor codes
    print("Loading Pyro Buy products...")
    vendor_code_map = load_pyrobuy_products(excel_file)
    if not vendor_code_map:
        print("No Pyro Buy products found or error loading data")
        return
    
    print(f"Searching for {len(vendor_code_map)} Pyro Buy vendor codes across {len(video_urls)} video directories...")
    print(f"Vendor codes: {list(vendor_code_map.keys())}")
    
    # Collect all matches from all sources
    all_matches = []
    
    for video_url in video_urls:
        print(f"\n{'='*60}")
        print(f"Checking: {video_url}")
        print(f"{'='*60}")
        
        # Get list of MP4 files from this video directory
        mp4_files = get_video_file_list(video_url)
        if not mp4_files:
            print(f"No MP4 files found or error fetching from {video_url}")
            continue
        
        # Find matching files for this source
        matches = find_matching_files(mp4_files, vendor_code_map.keys(), video_url)
        all_matches.extend(matches)
    
    if not all_matches:
        print("\nNo matching video files found across all sources")
        return
    
    # Remove duplicates (same vendor code from different sources - keep first found)
    unique_matches = {}
    for match in all_matches:
        vendor_code = match['vendor_code']
        if vendor_code not in unique_matches:
            unique_matches[vendor_code] = match
    
    final_matches = list(unique_matches.values())
    
    print(f"\n{'='*60}")
    print(f"SUMMARY: Found {len(final_matches)} unique matching video files to download:")
    print(f"{'='*60}")
    
    for match in final_matches:
        product_name = vendor_code_map[match['vendor_code']]
        source_domain = urlparse(match['source_url']).netloc
        print(f"  {match['filename']} -> {product_name} - {match['vendor_code']} (from {source_domain})")
    
    # Download matching files
    print(f"\nStarting downloads to {download_dir}/...")
    successful_downloads = 0
    
    for i, match in enumerate(final_matches, 1):
        vendor_code = match['vendor_code']
        product_name = vendor_code_map[vendor_code]
        original_filename = match['filename']
        source_url = match['source_url']
        
        # Create new filename: Product Name - Vendor Code.mp4
        new_filename = f"{product_name} - {vendor_code}.mp4"
        new_filename = sanitize_filename(new_filename)
        local_path = os.path.join(download_dir, new_filename)
        
        # Skip if file already exists
        if os.path.exists(local_path):
            print(f"[{i}/{len(final_matches)}] Skipping {new_filename} (already exists)")
            successful_downloads += 1
            continue
        
        source_domain = urlparse(source_url).netloc
        print(f"[{i}/{len(final_matches)}] Downloading: {original_filename} from {source_domain}")
        print(f"  Saving as: {new_filename}")
        
        # Construct download URL
        download_url = urljoin(source_url, original_filename)
        
        # Download the file
        if download_file(download_url, local_path):
            successful_downloads += 1
        
        # Add small delay between downloads to be respectful
        time.sleep(1)
    
    # Summary
    print(f"\n{'='*60}")
    print(f"FINAL DOWNLOAD SUMMARY:")
    print(f"{'='*60}")
    print(f"Total Pyro Buy products: {len(vendor_code_map)}")
    print(f"Total matches found across all sources: {len(all_matches)}")
    print(f"Unique matches downloaded: {len(final_matches)}")
    print(f"Successful downloads: {successful_downloads}")
    print(f"Failed downloads: {len(final_matches) - successful_downloads}")
    print(f"Files saved to: {os.path.abspath(download_dir)}/")
    
    # Create a summary report
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = f"pyrobuy_video_download_report_{timestamp}.txt"
    
    with open(report_file, 'w') as f:
        f.write(f"Pyro Buy Video Download Report - Multi-Source\n")
        f.write(f"Generated: {datetime.now()}\n")
        f.write(f"Sources checked: {', '.join(video_urls)}\n")
        f.write(f"Total Pyro Buy products: {len(vendor_code_map)}\n")
        f.write(f"Total matches found: {len(all_matches)}\n")
        f.write(f"Unique matches downloaded: {len(final_matches)}\n")
        f.write(f"Successful downloads: {successful_downloads}\n\n")
        
        f.write("Sources Summary:\n")
        source_counts = {}
        for match in all_matches:
            domain = urlparse(match['source_url']).netloc
            source_counts[domain] = source_counts.get(domain, 0) + 1
        
        for domain, count in source_counts.items():
            f.write(f"  {domain}: {count} matches\n")
        
        f.write(f"\nDownloaded Files:\n")
        for match in final_matches:
            vendor_code = match['vendor_code']
            product_name = vendor_code_map[vendor_code]
            new_filename = f"{product_name} - {vendor_code}.mp4"
            new_filename = sanitize_filename(new_filename)
            source_domain = urlparse(match['source_url']).netloc
            f.write(f"  {match['filename']} -> {new_filename} (from {source_domain})\n")
    
    print(f"Report saved to: {report_file}")

if __name__ == "__main__":
    download_pyrobuy_videos() 