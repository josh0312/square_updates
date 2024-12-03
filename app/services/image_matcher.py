import os
import yaml
from fuzzywuzzy import fuzz
from fuzzywuzzy import process
import logging.config
import re
from app.services.square_catalog import SquareCatalog
from square.client import Client
from dotenv import load_dotenv
from pathlib import Path
import time
import uuid
import io
from datetime import datetime
from app.utils.paths import paths
from app.utils.verify_paths import PathVerifier
import sys
from pprint import pformat

# Use paths instead of local definitions
file_handler = logging.FileHandler(paths.get_log_file('image_matcher'), mode='w')

# Remove all handlers from the root logger
logging.getLogger().handlers = []

# Configure our specific logger
logger = logging.getLogger('image_matcher')
logger.setLevel(logging.INFO)
logger.handlers = []  # Remove any existing handlers

# Create handlers
file_handler = logging.FileHandler(paths.get_log_file('image_matcher'), mode='w')
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
        # Load vendor directory mappings from vendor config
        with open(paths.VENDOR_CONFIG, 'r') as f:
            self.config = yaml.safe_load(f)
        
        # Base directory is now under DATA_DIR/images
        self.base_dir = os.path.join(paths.DATA_DIR, 'images')
        self.vendors = self.config['vendors']
        self.aliases = self.config.get('aliases', {})
        
        # Initialize Square catalog
        self.square = SquareCatalog()
        
        # Initialize Square client for image uploads
        self.client = Client(
            access_token=os.getenv('SQUARE_ACCESS_TOKEN'),
            environment=os.getenv('SQUARE_ENVIRONMENT', 'sandbox')
        )
        self.catalog_api = self.client.catalog
        
    def get_vendor_directory(self, vendor_name):
        """Get the directory for a vendor, including alias check"""
        if not vendor_name:
            return None
        
        # Check aliases first
        vendor_name = self.aliases.get(vendor_name, vendor_name)
        
        # Load vendor directory mappings from vendor config
        with open(paths.VENDOR_CONFIG, 'r') as f:
            config = yaml.safe_load(f)
            websites = config.get('websites', [])
            
            # Look for matching website configuration
            for website in websites:
                if website['name'].lower() == vendor_name.lower():
                    # For Supreme, use the URL from the website config
                    if 'url' in website:
                        domain = website['url'].split('//')[1].split('/')[0]
                        # Remove www. prefix if present
                        return domain.replace('www.', '')
                    elif 'urls' in website:
                        # If multiple URLs, use the first one
                        domain = website['urls'][0].split('//')[1].split('/')[0]
                        # Remove www. prefix if present
                        return domain.replace('www.', '')
        
        # If no match found in websites.yaml, try the original vendors mapping
        vendor_dir = self.vendors.get(vendor_name)
        if vendor_dir:
            # Remove www. prefix if present
            return vendor_dir.replace('www.', '')
        return None
    
    def get_image_files(self, vendor_dir):
        """Get list of image files in vendor directory"""
        if not vendor_dir:
            logger.warning("No vendor directory specified")
            return []
        
        # Construct path using data/images directory
        full_path = os.path.join(self.base_dir, vendor_dir)
        if not os.path.exists(full_path):
            logger.warning(f"Directory not found: {full_path}")
            # Try alternate path without www prefix
            alt_path = os.path.join(self.base_dir, vendor_dir.replace('www.', ''))
            if os.path.exists(alt_path):
                full_path = alt_path
            else:
                return []
        
        return [f for f in os.listdir(full_path) 
                if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp'))]
    
    def clean_name(self, name, is_red_rhino=False):
        """Clean product name for better matching"""
        if not name:
            logger.warning("Received empty name for cleaning")
            return ""
        
        # Convert to string and lowercase
        name = str(name).lower().strip()
        logger.debug(f"After lowercase: '{name}'")
        
        # For Red Rhino images, remove product code if present
        if is_red_rhino:
            name = re.sub(r'^[a-z0-9]{3,30}-', '', name, flags=re.IGNORECASE)
            name = re.sub(r'^[a-z0-9]{3,30}\s+', '', name, flags=re.IGNORECASE)
            logger.info(f"After product code removal: '{name}'")
        
        # Define descriptive terms to remove
        descriptive_terms = [
            'artillery',
            'shells',
            'shots',
            'canister',
            'cake',
            'finale',
            'repeater',
            'multi shot',
            'multishot',
            '500 gram',
            '500g',
            '200 gram',
            '200g',
            'safe and sane',
            'parachute',
            'chute',
            'candle',
            'assortment',
            'missile',
            'launcher',
            'cracker',
            'crackers',
            '6pk',
            '4pk',
            '12pk',
            'dzn',
            'battery',
            '20pk',
            'head',
            'bomb',
            'shot',
            'shell',
            'fireworks'
        ]
        
        # Define stop words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'with', 'by'}
        
        # First clean special characters
        name = re.sub(r'[_\-/\\]', ' ', name)
        logger.debug(f"After special char cleanup: '{name}'")
        
        # Keep alphanumeric characters and spaces
        name = re.sub(r'[^a-z0-9\s]', '', name)
        logger.debug(f"After keeping alphanumeric: '{name}'")
        
        # Split into words
        words = name.split()
        logger.debug(f"Split words: {words}")
        
        # Check if name would be too simple after cleaning
        word_count = len(words)
        numeric_words = [w for w in words if any(c.isdigit() for c in w)]
        
        # Don't remove descriptive terms if:
        # 1. The name has 2 or fewer words
        # 2. One of the words is a number
        # 3. Removing the term would leave just a number
        if word_count <= 2 or numeric_words:
            logger.info(f"Simple name detected: '{name}' - keeping descriptive terms")
            cleaned = name
        else:
            # Remove descriptive terms only for longer names
            cleaned_words = []
            i = 0
            while i < len(words):
                skip = False
                current_word = words[i]
                logger.debug(f"Processing word: '{current_word}'")
                
                # Check each descriptive term
                for term in descriptive_terms:
                    term_words = term.split()
                    if i + len(term_words) <= len(words):
                        potential_match = ' '.join(words[i:i+len(term_words)]).lower()
                        logger.debug(f"Checking term '{term}' against '{potential_match}'")
                        if potential_match == term.lower():
                            i += len(term_words) - 1
                            skip = True
                            logger.debug(f"Removed descriptive term: '{potential_match}'")
                            break
                
                if not skip and words[i] not in stop_words:
                    cleaned_words.append(words[i])
                    logger.debug(f"Kept word: '{words[i]}'")
                elif words[i] in stop_words:
                    logger.debug(f"Removed stop word: '{words[i]}'")
                i += 1
                
            # Remove extra whitespace and join
            cleaned = ' '.join(cleaned_words).strip()
        
        logger.debug(f"Final cleaned result: '{cleaned}'")
        
        if not cleaned:
            logger.warning(f"Cleaning resulted in empty string for input: '{name}'")
            return name
        
        logger.info(f"Cleaned name: '{name}' -> '{cleaned}'")
        return cleaned
    
    def find_best_match(self, name_to_match, image_files, sku=None, vendor_sku=None):
        """Find best matching image file for a given name"""
        if not image_files:
            logger.warning("No valid image names to match against")
            return None, 0
        
        logger.info(f"\n=== Starting Match Process ===")
        logger.info(f"Looking for match: '{name_to_match}'")
        logger.info(f"Square SKU: '{sku}'")
        logger.info(f"Vendor SKU: '{vendor_sku}'")
        logger.info(f"Number of images to check: {len(image_files)}")
        
        # First try to match by Square SKU
        if sku:
            logger.info(f"\nTrying to match by Square SKU: {sku}")
            for image_file in image_files:
                base_name = os.path.splitext(image_file)[0].lower()
                logger.info(f"  Checking against: {base_name}")
                
                # Try exact match first
                if sku.lower() == base_name:
                    logger.info(f"  Found exact Square SKU match: {image_file}")
                    return image_file, 100
                    
                # Then try as part of filename
                if sku.lower() in base_name:
                    # Make sure it's a word boundary
                    sku_pattern = rf'\b{re.escape(sku.lower())}\b'
                    if re.search(sku_pattern, base_name):
                        logger.info(f"  Found Square SKU in filename: {image_file}")
                        return image_file, 100
                    else:
                        logger.debug(f"  SKU found but not at word boundary: {base_name}")
        
        # Then try to match by vendor SKU
        if vendor_sku:
            logger.info(f"\nTrying to match by Vendor SKU: {vendor_sku}")
            for image_file in image_files:
                base_name = os.path.splitext(image_file)[0].lower()
                logger.info(f"  Checking against: {base_name}")
                
                # Try exact match first
                if vendor_sku.lower() == base_name:
                    logger.info(f"  Found exact Vendor SKU match: {image_file}")
                    return image_file, 100
                
                # Then try as part of filename
                if vendor_sku.lower() in base_name:
                    # Make sure it's a word boundary
                    sku_pattern = rf'\b{re.escape(vendor_sku.lower())}\b'
                    if re.search(sku_pattern, base_name):
                        logger.info(f"  Found Vendor SKU in filename: {image_file}")
                        return image_file, 100
                    else:
                        logger.debug(f"  Vendor SKU found but not at word boundary: {base_name}")
                
                # Try without special characters
                clean_sku = re.sub(r'[^a-zA-Z0-9]', '', vendor_sku.lower())
                clean_name = re.sub(r'[^a-zA-Z0-9]', '', base_name)
                if clean_sku and clean_sku in clean_name:
                    logger.info(f"  Found Vendor SKU (cleaned) in filename: {image_file}")
                    return image_file, 100
        
        # Finally, fall back to name matching
        logger.info("\nFalling back to name matching...")
        clean_name = self.clean_name(name_to_match)
        logger.info(f"Final name to match: '{clean_name}'")
        
        best_match = None
        best_ratio = 0
        
        for image_file in image_files:
            base_name = os.path.splitext(image_file)[0]
            clean_image = self.clean_name(base_name)
            
            ratio = fuzz.ratio(clean_name, clean_image)
            logger.info(f"Comparing:")
            logger.info(f"  Clean name: '{clean_name}'")
            logger.info(f"  Image name: '{clean_image}'")
            logger.info(f"  Match ratio: {ratio}%")
            
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = image_file
                logger.info(f"  New best match! Score: {ratio}%")
                
                if ratio == 100:
                    logger.info("Found perfect match - stopping search")
                    break
        
        if best_match and best_ratio >= 80:
            logger.info(f"\nFinal Match Found:")
            logger.info(f"Original name: '{name_to_match}'")
            logger.info(f"Matched with: '{best_match}'")
            logger.info(f"Match score: {best_ratio}%")
            return best_match, best_ratio
        else:
            logger.info(f"\nNo match found meeting minimum score (80%)")
            logger.info(f"Best match was: '{best_match}' with score: {best_ratio}%")
            return None, best_ratio
    
    def get_vendor_code(self, vendor_name, variation_name):
        """Extract vendor code from variation name or vendor name"""
        # Common vendor codes
        vendor_codes = {
            'Supreme': 'SP',
            'Red Rhino': 'RR',
            'Winco': 'WC',
            'Raccoon': 'RC',
        }
        
        # First try to extract from variation name
        if variation_name:
            # Look for 2-3 letter code at start of variation name
            match = re.match(r'^([A-Za-z]{2,3})[0-9-]*', variation_name)
            if match:
                return match.group(1).upper()
        
        # Fall back to vendor mapping
        return vendor_codes.get(vendor_name)
    
    def find_matches(self):
        """Find matches for all items without images"""
        items = self.square.get_items_without_images()
        
        # Add debug logging for received data
        logger.info("\n=== Received Data from Square Catalog ===")
        logger.info(f"Number of items: {len(items)}")
        
        matches = []
        
        if not items:
            logger.info("No items found needing images")
            return []
        
        for item in items:
            item_name = item['name']
            logger.debug(f"\nProcessing Square Item: '{item_name}'")
            
            # Double check with Square API that this item still needs images
            item_result = self.catalog_api.retrieve_catalog_object(
                object_id=item['id']
            )
            
            if not item_result.is_success():
                logger.error(f"Failed to verify item {item_name}")
                continue
                
            item_data = item_result.body['object'].get('item_data', {})
            if item_data.get('image_ids'):
                logger.info(f"Skipping {item_name} - already has primary image")
                continue
            
            for var in item['variations']:
                vendor_name = var['vendor_name']
                square_sku = var['square_sku']
                vendor_sku = var['vendor_sku']
                
                # Double check variation still needs image
                var_result = self.catalog_api.retrieve_catalog_object(
                    object_id=var['id']
                )
                
                if not var_result.is_success():
                    logger.error(f"Failed to verify variation {var['name']}")
                    continue
                    
                var_data = var_result.body['object'].get('item_variation_data', {})
                if var_data.get('image_ids'):
                    logger.info(f"Skipping variation {var['name']} - already has images")
                    continue
                
                logger.info(f"\nProcessing variation: {var['name']}")
                logger.info(f"  Vendor: {vendor_name}")
                logger.info(f"  Square SKU: {square_sku}")
                logger.info(f"  Vendor SKU: {vendor_sku}")
                
                # Focus on image matching
                vendor_dir = self.get_vendor_directory(vendor_name)
                if not vendor_dir:
                    logger.warning(f"No directory mapping found for vendor: {vendor_name}")
                    continue
                
                logger.info(f"  Looking in directory: {vendor_dir}")
                image_files = self.get_image_files(vendor_dir)
                
                best_match, match_ratio = self.find_best_match(
                    item_name,
                    image_files,
                    sku=square_sku,
                    vendor_sku=vendor_sku
                )
                
                if best_match:
                    match_data = {
                        'item_name': item_name,
                        'variation_name': var['name'],
                        'variation_id': var['id'],
                        'vendor': vendor_name,
                        'image_file': best_match,
                        'image_path': os.path.join(self.base_dir, vendor_dir, best_match),
                        'match_ratio': match_ratio,
                        'needs_primary': item['needs_primary_image']
                    }
                    matches.append(match_data)
                    logger.info(f"  Found match: {best_match} ({match_ratio}%)")
                else:
                    logger.warning(f"  No match found for: {item_name} (Vendor: {vendor_name})")
        
        return matches
    
    def upload_image_to_square(self, image_path, variation_id, needs_primary=True):
        """Upload an image to Square and associate it with item/variations as needed."""
        try:
            # First, get the variation to ensure it exists and get the item ID
            result = self.catalog_api.retrieve_catalog_object(
                object_id=variation_id
            )
            
            if not result.is_success():
                logger.error("Failed to get variation details")
                return None
            
            variation_data = result.body['object'].get('item_variation_data', {})
            item_id = variation_data.get('item_id')
            
            # Check if variation already has images
            if variation_data.get('image_ids'):
                logger.info(f"Variation {variation_id} already has images - skipping upload")
                return "SKIPPED"
            
            # Get item details to check for primary image if needed
            if needs_primary:
                item_result = self.catalog_api.retrieve_catalog_object(
                    object_id=item_id
                )
                
                if not item_result.is_success():
                    logger.error("Failed to get item details")
                    return None
                
                if item_result.body['object']['item_data'].get('image_ids'):
                    logger.info("Item already has primary image - skipping upload")
                    return "SKIPPED"
            
            # If we get here, we need to upload the image
            logger.info(f"Uploading image {image_path} for variation {variation_id}")
            logger.info(f"Will set as primary: {needs_primary}")
            
            # Get file info
            image_file = Path(image_path)
            file_name = image_file.name
            
            logger.info(f"File name: {file_name}")
            logger.info(f"File size: {image_file.stat().st_size} bytes")
            
            # Create unique idempotency key
            idempotency_key = f"upload_{variation_id}_{int(time.time())}"
            
            # Prepare upload request
            request = {
                "idempotency_key": idempotency_key,
                "object_id": item_id if needs_primary else None,
                "image": {
                    "type": "IMAGE",
                    "id": "#TEMP_ID",
                    "image_data": {
                        "name": file_name,
                        "caption": f"Image for {'item' if needs_primary else 'variation'} {item_id if needs_primary else variation_id}",
                        "is_primary": needs_primary
                    }
                }
            }
            
            # Upload the image
            with open(image_path, 'rb') as f:
                image_data = f.read()
                image_file_obj = io.BytesIO(image_data)
                image_file_obj.name = file_name
                
                result = self.catalog_api.create_catalog_image(
                    request=request,
                    image_file=image_file_obj
                )
            
            if result.is_success():
                # Get the image ID
                image_id = result.body.get('image', {}).get('id') or result.body.get('catalog_object', {}).get('id')
                
                if not image_id:
                    logger.error(f"Unexpected response structure: {result.body}")
                    return None
                    
                logger.info(f"Upload successful! Image ID: {image_id}")
                
                # Associate with variation if needed
                if not needs_primary:
                    success = self._associate_image_with_variation(image_id, variation_id)
                    if not success:
                        logger.warning(f"Failed to associate image with variation {variation_id}")
                
                return image_id
                
            else:
                logger.error("Upload failed!")
                for error in result.errors:
                    logger.error(f"Category: {error.get('category')}")
                    logger.error(f"Code: {error.get('code')}")
                    logger.error(f"Detail: {error.get('detail')}")
                return None
                
        except Exception as e:
            logger.error(f"Exception during upload: {str(e)}")
            logger.error(f"Exception type: {type(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None
    
    def _associate_image_with_variation(self, image_id, variation_id):
        """Associate an uploaded image with a catalog item variation."""
        try:
            # First get the variation to ensure it exists
            variation_result = self.catalog_api.retrieve_catalog_object(
                object_id=variation_id
            )
            
            if not variation_result.is_success():
                logger.error(f"Failed to retrieve variation {variation_id}")
                return False
            
            # Get the current variation data
            current_variation = variation_result.body['object']
            current_data = current_variation.get('item_variation_data', {})
            
            # Create a copy of the current data and add our image_ids
            updated_data = current_data.copy()
            updated_data['image_ids'] = [image_id]
            
            # Create the batch upsert request
            batch_request = {
                "idempotency_key": f"update_{image_id}_{variation_id}_{int(time.time())}",
                "batches": [
                    {
                        "objects": [
                            {
                                "type": "ITEM_VARIATION",
                                "id": variation_id,
                                "version": current_variation.get('version'),
                                "present_at_all_locations": current_variation.get('present_at_all_locations'),
                                "present_at_location_ids": current_variation.get('present_at_location_ids'),
                                "item_variation_data": updated_data
                            }
                        ]
                    }
                ]
            }
            
            logger.debug("\nCurrent variation data:")
            logger.debug(pformat(current_variation))
            logger.debug("\nSending batch upsert request:")
            logger.debug(pformat(batch_request))
            
            # Use BatchUpsertCatalogObjects to associate the image
            update_result = self.catalog_api.batch_upsert_catalog_objects(
                body=batch_request
            )
            
            if update_result.is_success():
                logger.info(f"Successfully associated image {image_id} with variation {variation_id}")
                return True
            else:
                logger.error(f"Failed to associate image: {update_result.errors}")
                return False
                
        except Exception as e:
            logger.error(f"Exception while associating image: {str(e)}")
            return False
    
    def process_matches(self, matches):
        """Process matches and upload images to Square."""
        logger.info("\n=== Processing Matches and Uploading Images ===")
        
        successful_uploads = 0
        failed_uploads = 0
        
        for match in matches:
            logger.info(f"\nProcessing match for {match['item_name']} - {match['variation_name']}")
            
            image_id = self.upload_image_to_square(
                match['image_path'],
                match['variation_id'],
                needs_primary=match['needs_primary']
            )
            
            if image_id:
                if image_id == "SKIPPED":
                    logger.info(f"Skipped upload for {match['item_name']} - item already has images")
                else:
                    successful_uploads += 1
                    logger.info(f"Successfully processed match with image ID: {image_id}")
            else:
                failed_uploads += 1
                logger.error(f"Failed to process match for variation {match['variation_id']}")
        
        logger.info("\n=== Image Upload Summary ===")
        logger.info(f"Successful uploads: {successful_uploads}")
        logger.info(f"Failed uploads: {failed_uploads}")
        
        return successful_uploads, failed_uploads
    
    def write_unmatched(self, unmatched_items):
        """Write unmatched items to a log file, grouped by vendor."""
        unmatched_log = paths.get_log_file('image_matcher_unmatched')
        logger.info(f"\nWriting unmatched items to: {unmatched_log}")
        
        # Group items by vendor
        vendor_groups = {}
        for item in unmatched_items:
            vendor = item['vendor']
            if vendor not in vendor_groups:
                vendor_groups[vendor] = []
            vendor_groups[vendor].append(item)
        
        with open(unmatched_log, 'w') as f:
            f.write("Items with no matching images found:\n")
            f.write(f"Total unmatched items: {len(unmatched_items)}\n\n")
            
            # Write items grouped by vendor
            for vendor, items in sorted(vendor_groups.items()):
                f.write(f"\n{vendor} ({len(items)} items):\n")
                f.write("=" * 50 + "\n")
                
                # Sort items by name within each vendor group
                for item in sorted(items, key=lambda x: x['item_name']):
                    f.write(f"\nItem: {item['item_name']}\n")
                    f.write(f"Variation: {item['variation_name']}\n")
                    f.write(f"Vendor SKU: {item['vendor_sku']}\n")
                    f.write("-" * 30 + "\n")
                
                f.write("\n")
    
    def test_square_data(self):
        """Test method to verify Square catalog data"""
        logger.info("\n=== Testing Square Catalog Data ===")
        
        items = self.square.get_items_without_images()
        
        # Log overall statistics
        logger.info(f"\nReceived {len(items)} items")
        
        # Count items by vendor
        vendor_counts = {}
        for item in items:
            for var in item['variations']:
                vendor = var['vendor_name']
                vendor_counts[vendor] = vendor_counts.get(vendor, 0) + 1
        
        logger.info("\nItems by vendor:")
        for vendor, count in vendor_counts.items():
            logger.info(f"  {vendor}: {count} variations")
        
        # Sample the first few items
        logger.info("\nSample of received data:")
        for item in items[:3]:
            logger.info(pformat(item))

if __name__ == "__main__":
    # Verify paths first
    verifier = PathVerifier()
    if not verifier.verify_all():
        logger.error("Path verification failed!")
        sys.exit(1)
    
    matcher = ImageMatcher()
    logger.info("\n=== Starting Image Matcher ===")
    
    # Get items needing images from Square Catalog
    catalog = SquareCatalog()
    
    # Get all items using Square Catalog's improved pagination
    all_items = []
    cursor = None
    batch_size = 100
    
    logger.info("Fetching all items from Square...")
    
    while True:
        # Get batch of items
        body = {
            "product_types": ["REGULAR"],
            "state_filters": {"states": ["ACTIVE"]},
            "limit": batch_size
        }
        
        if cursor:
            body["cursor"] = cursor
        
        result = catalog.client.catalog.search_catalog_items(body=body)
        
        if not result.is_success():
            logger.error("Failed to fetch items from Square API")
            logger.error(pformat(result.errors))
            break
        
        # Process this batch
        batch_items = catalog.process_catalog_items(result.body)
        all_items.extend(batch_items)
        
        # Get cursor for next batch
        cursor = result.body.get('cursor')
        logger.info(f"Fetched batch of {len(batch_items)} items. Total so far: {len(all_items)}")
        
        # If no cursor, we've got all items
        if not cursor:
            break
    
    logger.info(f"\nFetched {len(all_items)} total items")
    
    # Find matches for items needing images
    matches = []
    unmatched_items = []  # Track unmatched items
    
    for item in all_items:
        item_name = item['name']
        item_needs_primary = item['needs_primary_image']
        has_variations = len(item['variations']) > 0
        
        logger.info(f"\nProcessing: {item_name}")
        logger.info(f"Has variations: {has_variations}")
        logger.info(f"Needs primary image: {item_needs_primary}")
        
        if not has_variations:
            # Single item without variations - just look for a match
            if item_needs_primary:
                logger.info("Looking for primary image for single item")
                # Take first variation's vendor info for matching
                var = item['variations'][0]
                vendor_name = var['vendor_name']
                square_sku = var['square_sku']
                vendor_sku = var['vendor_sku']
                
                vendor_dir = matcher.get_vendor_directory(vendor_name)
                if vendor_dir:
                    image_files = matcher.get_image_files(vendor_dir)
                    best_match, match_ratio = matcher.find_best_match(
                        item_name,
                        image_files,
                        sku=square_sku,
                        vendor_sku=vendor_sku
                    )
                    
                    if best_match:
                        match_data = {
                            'item_name': item_name,
                            'variation_name': var['name'],
                            'variation_id': var['id'],
                            'vendor': vendor_name,
                            'image_file': best_match,
                            'image_path': os.path.join(matcher.base_dir, vendor_dir, best_match),
                            'match_ratio': match_ratio,
                            'needs_primary': True
                        }
                        matches.append(match_data)
                        logger.info(f"Found match for primary image: {best_match} ({match_ratio}%)")
                    else:
                        unmatched_items.append({
                            'item_name': item_name,
                            'variation_name': var['name'],
                            'vendor': vendor_name,
                            'vendor_sku': vendor_sku
                        })
        else:
            # Item with variations - process in order
            first_variation = True
            for var in item['variations']:
                if var['needs_image'] or (first_variation and item_needs_primary):
                    logger.info(f"\nProcessing variation: {var['name']}")
                    vendor_name = var['vendor_name']
                    square_sku = var['square_sku']
                    vendor_sku = var['vendor_sku']
                    
                    vendor_dir = matcher.get_vendor_directory(vendor_name)
                    if vendor_dir:
                        image_files = matcher.get_image_files(vendor_dir)
                        best_match, match_ratio = matcher.find_best_match(
                            item_name,
                            image_files,
                            sku=square_sku,
                            vendor_sku=vendor_sku
                        )
                        
                        if best_match:
                            match_data = {
                                'item_name': item_name,
                                'variation_name': var['name'],
                                'variation_id': var['id'],
                                'vendor': vendor_name,
                                'image_file': best_match,
                                'image_path': os.path.join(matcher.base_dir, vendor_dir, best_match),
                                'match_ratio': match_ratio,
                                'needs_primary': first_variation and item_needs_primary
                            }
                            matches.append(match_data)
                            logger.info(f"Found match: {best_match} ({match_ratio}%)")
                            if first_variation and item_needs_primary:
                                logger.info("This will also be set as the primary image")
                        else:
                            unmatched_items.append({
                                'item_name': item_name,
                                'variation_name': var['name'],
                                'vendor': vendor_name,
                                'vendor_sku': vendor_sku
                            })
                first_variation = False
    
    # Process any matches found
    if matches:
        successful_uploads, failed_uploads = matcher.process_matches(matches)
        logger.info("\n=== Final Summary ===")
        logger.info(f"Total matches found: {len(matches)}")
        logger.info(f"Successful uploads: {successful_uploads}")
        logger.info(f"Failed uploads: {failed_uploads}")
    else:
        logger.info("\nNo matches found")
    
    # Write unmatched items to log
    if unmatched_items:
        matcher.write_unmatched(unmatched_items)
        logger.info(f"\nWrote {len(unmatched_items)} unmatched items to log")