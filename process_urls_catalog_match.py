#!/usr/bin/env python3
"""
Script to process URLs from urls_without_video file, extract product names,
match them with Square catalog data, and create an output spreadsheet.
"""

import pandas as pd
import re
from urllib.parse import urlparse, unquote
from fuzzywuzzy import fuzz, process
import os
from datetime import datetime

def extract_product_name_from_url(url):
    """Extract product name from the URL pattern."""
    # Parse URL: https://shop.nytexfireworks.com/product/product-name/id
    try:
        # Extract the path and get the product name part
        path = urlparse(url).path
        # Pattern: /product/product-name/id
        match = re.match(r'/product/([^/]+)/\d+$', path)
        if match:
            product_slug = match.group(1)
            # Convert slug to readable name
            # Replace hyphens with spaces and handle special cases
            product_name = product_slug.replace('-', ' ')
            # Handle edge cases like leading/trailing hyphens
            product_name = product_name.strip()
            # Capitalize words appropriately
            product_name = ' '.join(word.capitalize() for word in product_name.split())
            return product_name
        else:
            return None
    except Exception as e:
        print(f"Error extracting product name from {url}: {e}")
        return None

def normalize_product_name(name):
    """Normalize product name for better matching."""
    if not name:
        return ""
    
    # Convert to lowercase for comparison
    normalized = name.lower().strip()
    
    # Remove common variations and punctuation
    normalized = re.sub(r'[^\w\s]', ' ', normalized)  # Remove punctuation
    normalized = re.sub(r'\s+', ' ', normalized)  # Normalize whitespace
    normalized = normalized.strip()
    
    return normalized

def find_best_match(product_name, catalog_names, threshold=70):
    """Find the best match for a product name in the catalog using fuzzy matching."""
    if not product_name or not catalog_names:
        return None, 0
    
    # Normalize the input name
    normalized_product = normalize_product_name(product_name)
    
    # Create normalized catalog names for matching
    normalized_catalog = [normalize_product_name(name) for name in catalog_names]
    
    # Use fuzzy matching
    best_match = process.extractOne(
        normalized_product, 
        normalized_catalog, 
        scorer=fuzz.token_sort_ratio
    )
    
    if best_match and best_match[1] >= threshold:
        # Find the original name corresponding to the normalized match
        matched_index = normalized_catalog.index(best_match[0])
        return catalog_names[matched_index], best_match[1]
    
    return None, 0

def load_square_catalog(file_path):
    """Load the Square catalog Excel file."""
    try:
        # Try reading the Excel file
        df = pd.read_excel(file_path)
        print(f"Loaded Square catalog with {len(df)} rows and columns: {list(df.columns)}")
        return df
    except Exception as e:
        print(f"Error loading Square catalog from {file_path}: {e}")
        return None

def process_urls_and_match_catalog():
    """Main function to process URLs and match with catalog."""
    
    # File paths
    urls_file = "urls_without_video_20250527_092132.txt"
    catalog_file = "/Users/joshgoble/code/nytexfireworks/square_catalog_export/square_catalog_export.xlsx"
    
    # Check if files exist
    if not os.path.exists(urls_file):
        print(f"Error: URLs file {urls_file} not found")
        return
    
    if not os.path.exists(catalog_file):
        print(f"Error: Catalog file {catalog_file} not found")
        return
    
    # Load URLs
    print("Loading URLs...")
    with open(urls_file, 'r') as f:
        urls = [line.strip() for line in f if line.strip()]
    
    print(f"Found {len(urls)} URLs to process")
    
    # Load Square catalog
    print("Loading Square catalog...")
    catalog_df = load_square_catalog(catalog_file)
    if catalog_df is None:
        return
    
    # Determine which columns contain the product names, categories, and vendors
    print("\nCatalog columns:")
    for i, col in enumerate(catalog_df.columns):
        print(f"{i}: {col}")
    
    # Assume common column names - we'll need to inspect the actual file
    # Common possibilities: 'Name', 'Product Name', 'Item Name', 'Title'
    name_columns = [col for col in catalog_df.columns if 
                   any(term in col.lower() for term in ['name', 'item', 'product', 'title'])]
    
    category_columns = [col for col in catalog_df.columns if 
                       any(term in col.lower() for term in ['category', 'type', 'class'])]
    
    vendor_columns = [col for col in catalog_df.columns if 
                     any(term in col.lower() for term in ['vendor', 'supplier', 'brand', 'manufacturer'])]
    
    print(f"\nPossible name columns: {name_columns}")
    print(f"Possible category columns: {category_columns}")
    print(f"Possible vendor columns: {vendor_columns}")
    
    # Use the first available column for each type, or ask user to specify
    name_col = name_columns[0] if name_columns else None
    category_col = category_columns[0] if category_columns else None
    vendor_col = vendor_columns[0] if vendor_columns else None
    
    if not name_col:
        print("Warning: Could not identify name column automatically")
        print("Available columns:", list(catalog_df.columns))
        return
    
    print(f"\nUsing columns:")
    print(f"Name: {name_col}")
    print(f"Category: {category_col}")
    print(f"Vendor: {vendor_col}")
    
    # Get catalog product names for matching
    catalog_names = catalog_df[name_col].dropna().astype(str).tolist()
    print(f"Found {len(catalog_names)} product names in catalog")
    
    # Process each URL
    print("\nProcessing URLs and matching with catalog...")
    results = []
    
    for i, url in enumerate(urls):
        if i % 50 == 0:
            print(f"Processed {i}/{len(urls)} URLs...")
        
        # Extract product name from URL
        extracted_name = extract_product_name_from_url(url)
        
        # Try to match with catalog
        matched_name = None
        category = None
        vendor = None
        vendor_code = None
        match_score = 0
        
        if extracted_name:
            matched_name, match_score = find_best_match(extracted_name, catalog_names)
            
            if matched_name:
                # Find the row with this product name
                matched_row = catalog_df[catalog_df[name_col] == matched_name].iloc[0]
                category = matched_row[category_col] if category_col and category_col in catalog_df.columns else None
                vendor = matched_row[vendor_col] if vendor_col and vendor_col in catalog_df.columns else None
                vendor_code = matched_row['Default Vendor Code'] if 'Default Vendor Code' in catalog_df.columns else None
        
        results.append({
            'URL': url,
            'Extracted_Name': extracted_name,
            'Matched_Name': matched_name,
            'Match_Score': match_score,
            'Category': category,
            'Vendor': vendor,
            'Vendor_Code': vendor_code
        })
    
    # Create output DataFrame
    output_df = pd.DataFrame(results)
    
    # Create final output with requested columns
    final_df = pd.DataFrame({
        'URL': output_df['URL'],
        'Product_Name': output_df['Matched_Name'].fillna(''),
        'Category': output_df['Category'].fillna(''),
        'Vendor': output_df['Vendor'].fillna(''),
        'Vendor_Code': output_df['Vendor_Code'].fillna(''),
        'Extracted_Name': output_df['Extracted_Name'].fillna(''),
        'Match_Score': output_df['Match_Score']
    })
    
    # Generate output filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"url_catalog_matches_{timestamp}.xlsx"
    
    # Save to Excel
    final_df.to_excel(output_file, index=False)
    
    print(f"\nProcessing complete!")
    print(f"Results saved to: {output_file}")
    print(f"Total URLs processed: {len(urls)}")
    print(f"Successfully matched: {len(final_df[final_df['Product_Name'] != ''])}")
    print(f"No matches found: {len(final_df[final_df['Product_Name'] == ''])}")
    
    # Show some sample results
    print(f"\nSample results:")
    print(final_df.head(10).to_string(index=False))
    
    return output_file

if __name__ == "__main__":
    process_urls_and_match_catalog() 