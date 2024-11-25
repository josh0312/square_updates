import os
import yaml
from fuzzywuzzy import fuzz
from fuzzywuzzy import process
import logging.config
import re
from square_catalog import SquareCatalog

# Remove all handlers from the root logger
logging.getLogger().handlers = []

# Configure our specific logger
logger = logging.getLogger('image_matcher')
logger.setLevel(logging.INFO)
logger.handlers = []  # Remove any existing handlers

# Create handlers
file_handler = logging.FileHandler('matcher.log', mode='w')
console_handler = logging.StreamHandler()

# Create formatters and add it to handlers
log_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(log_format)
console_handler.setFormatter(log_format)

# Add handlers to the logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)

class ImageMatcher:
    def __init__(self):
        # Load vendor directory mappings
        with open('vendor_directories.yaml', 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.base_dir = self.config['base_directory']
        self.vendors = self.config['vendors']
        self.aliases = self.config.get('aliases', {})
        
        # Initialize Square catalog
        self.square = SquareCatalog()
        
    def get_vendor_directory(self, vendor_name):
        """Get the directory for a vendor, including alias check"""
        # Check aliases first
        vendor_name = self.aliases.get(vendor_name, vendor_name)
        return self.vendors.get(vendor_name)
    
    def get_image_files(self, vendor_dir):
        """Get list of image files in vendor directory"""
        full_path = os.path.join(self.base_dir, vendor_dir)
        if not os.path.exists(full_path):
            logger.warning(f"Directory not found: {full_path}")
            return []
        
        return [f for f in os.listdir(full_path) 
                if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp'))]
    
    def clean_name(self, name):
        """Clean product name for better matching"""
        if not name:
            logger.warning("Received empty name for cleaning")
            return ""
        
        # Convert to string and lowercase
        name = str(name).lower().strip()
        
        # Replace specific characters with spaces
        name = re.sub(r'[_\-/\\]', ' ', name)
        
        # Keep alphanumeric characters and spaces
        name = re.sub(r'[^a-z0-9\s]', '', name)
        
        # Remove common words that don't help with matching
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'with', 'by'}
        words = name.split()
        words = [w for w in words if w not in stop_words]
        
        # Remove extra whitespace and join
        cleaned = ' '.join(words).strip()
        
        if not cleaned:
            logger.warning(f"Cleaning resulted in empty string for input: '{name}'")
            return name  # Return original if cleaning emptied it
        
        logger.info(f"Cleaned name: '{name}' -> '{cleaned}'")  # Added logging to see the transformation
        return cleaned
    
    def find_best_match(self, item_name, image_files):
        """Find best matching image for an item name"""
        # Special debug for our test case
        if "girl wants backpack" in item_name.lower():
            logger.info(f"\n=== DEBUG: Processing '{item_name}' ===")
            logger.info("Available images:")
            for img in image_files:
                logger.info(f"  {img}")
        
        logger.info(f"\nMatching item: '{item_name}'")
        cleaned_name = self.clean_name(item_name)
        
        # More debug for our test case
        if "girl wants backpack" in item_name.lower():
            logger.info(f"Cleaned name to match: '{cleaned_name}'")
            logger.info("\nCleaned image names:")
            for img in image_files:
                cleaned_img = self.clean_name(os.path.splitext(img)[0])
                logger.info(f"  '{img}' -> '{cleaned_img}'")
                # Try all matching methods
                ratio = fuzz.ratio(cleaned_name, cleaned_img)
                partial = fuzz.partial_ratio(cleaned_name, cleaned_img)
                token_sort = fuzz.token_sort_ratio(cleaned_name, cleaned_img)
                token_set = fuzz.token_set_ratio(cleaned_name, cleaned_img)
                logger.info(f"  Ratios - Simple: {ratio}, Partial: {partial}, Token Sort: {token_sort}, Token Set: {token_set}")
        
        if not cleaned_name:
            logger.warning(f"No valid name to match for: {item_name}")
            return None, 0
        
        # Clean image names and prepare for matching
        cleaned_images = []
        logger.info(f"Processing {len(image_files)} potential image matches:")
        for img_file in image_files:
            base_name = os.path.splitext(img_file)[0]
            cleaned_img_name = self.clean_name(base_name)
            if cleaned_img_name:
                cleaned_images.append((cleaned_img_name, img_file))
                logger.info(f"  Image: '{img_file}' -> '{cleaned_img_name}'")
            else:
                logger.warning(f"  Skipping image due to empty cleaned name: {img_file}")
        
        if not cleaned_images:
            logger.warning("No valid image names to match against")
            return None, 0
        
        # Find best match using fuzzywuzzy
        best_match = process.extractOne(
            cleaned_name,
            [name for name, _ in cleaned_images],
            scorer=fuzz.token_set_ratio
        )
        
        if best_match and best_match[1] >= 80:  # Minimum match ratio
            # Find the original filename for the matched name
            matched_name = best_match[0]
            for cleaned, original in cleaned_images:
                if fuzz.token_set_ratio(cleaned, matched_name) >= 80:  # Use fuzzy matching here too
                    logger.info(f"Found match: '{item_name}' -> '{original}' (Score: {best_match[1]})")
                    return original, best_match[1]
        
        # If we get here, no match was found that met our criteria
        logger.info(f"No match found meeting criteria for: '{item_name}'")
        return None, 0
    
    def find_matches(self):
        """Find matches for all items without images"""
        items = self.square.get_items_without_images()
        matches = []
        
        if not items:
            logger.error("No items found in Square catalog")
            return []
        
        for item in items:
            item_name = item['item_data']['name']
            variations = item['item_data']['variations']
            
            logger.info(f"\nProcessing Square Item: '{item_name}'")
            
            for var in variations:
                var_name = var['name']
                vendor_name = var['vendor_name']
                
                logger.info(f"  Variation: '{var_name}'")
                logger.info(f"  Vendor: {vendor_name}")
                
                vendor_dir = self.get_vendor_directory(vendor_name)
                if not vendor_dir:
                    logger.warning(f"No directory mapping found for vendor: {vendor_name}")
                    continue
                
                logger.info(f"  Looking in directory: {vendor_dir}")
                image_files = self.get_image_files(vendor_dir)
                
                # Use item name for matching unless variation name is more specific
                name_to_match = item_name
                if var_name != "Regular" and var_name != item_name:
                    name_to_match = f"{item_name} {var_name}"
                
                logger.info(f"  Using name for matching: '{name_to_match}'")
                
                best_match, match_ratio = self.find_best_match(name_to_match, image_files)
                
                if best_match:
                    match_data = {
                        'item_name': item_name,
                        'variation_name': var_name,
                        'variation_id': var['id'],
                        'sku': var['sku'],
                        'vendor': vendor_name,
                        'image_file': best_match,
                        'image_path': os.path.join(self.base_dir, vendor_dir, best_match),
                        'match_ratio': match_ratio
                    }
                    matches.append(match_data)
                    logger.info(f"  Found match: {best_match} ({match_ratio}%)")
                else:
                    logger.warning(f"  No match found for: {name_to_match} (Vendor: {vendor_name})")
        
        return matches

if __name__ == "__main__":
    matcher = ImageMatcher()
    
    logger.info("\n=== Starting Image Matcher ===")
    
    # Track statistics
    total_items = 0  # Count of unique items (not variations)
    total_variations = 0  # Count of all variations
    total_images = 0
    matched_items = set()  # Track unique items that got matches
    matched_variations = 0
    unmatched_items = []
    
    # First, get all Square items without images
    items = matcher.square.get_items_without_images()
    total_items = len(items)
    
    logger.info("\n=== Square Items Without Images (Alphabetical) ===")
    square_items = []
    for item in items:
        variations = item['item_data']['variations']
        total_variations += len(variations)
        for var in variations:
            square_items.append({
                'item_name': item['item_data']['name'],
                'name': var['name'],
                'vendor': var['vendor_name'],
                'sku': var['sku']
            })
    
    # Sort Square items by name
    square_items.sort(key=lambda x: x['name'].lower())
    
    # Log Square items
    for item in square_items:
        logger.info(f"Square: {item['name']} | Vendor: {item['vendor']} | SKU: {item['sku']}")
    
    # Now get all available images by vendor
    logger.info("\n=== Available Images by Vendor (Alphabetical) ===")
    all_images = {}
    for vendor, directory in matcher.vendors.items():
        images = matcher.get_image_files(directory)
        if images:
            all_images[vendor] = sorted(images, key=str.lower)
            total_images += len(images)
            logger.info(f"\nVendor: {vendor}")
            for img in all_images[vendor]:
                logger.info(f"Image: {os.path.splitext(img)[0]}")
    
    # Now run the matching
    matches = matcher.find_matches()
    matched_variations = len(matches)
    
    # Track which items got matches
    for match in matches:
        matched_items.add(match['item_name'])
    
    # Write unmatched items to file
    with open('unmatched.txt', 'w') as f:
        f.write("=== Unmatched Items ===\n\n")
        for item in square_items:
            if not any(m['variation_name'] == item['name'] for m in matches):
                unmatched_items.append(item)
                f.write(f"Item Name: {item['item_name']}\n")
                f.write(f"Variation: {item['name']}\n")
                f.write(f"Vendor: {item['vendor']}\n")
                f.write(f"SKU: {item['sku']}\n")
                f.write("-" * 50 + "\n")
    
    # Log summary
    logger.info("\n=== Summary ===")
    logger.info(f"Total unique items in Square: {total_items}")
    logger.info(f"Total variations in Square: {total_variations}")
    logger.info(f"Total images available: {total_images}")
    logger.info(f"Items with at least one match: {len(matched_items)}")
    logger.info(f"Total variations matched: {matched_variations}")
    logger.info(f"Unmatched variations: {len(unmatched_items)}")
    logger.info(f"Item match rate: {(len(matched_items)/total_items*100):.1f}%")
    logger.info(f"Variation match rate: {(matched_variations/total_variations*100):.1f}%")
    logger.info("\nUnmatched items have been written to 'unmatched.txt'") 