import os
import yaml
from fuzzywuzzy import fuzz
from fuzzywuzzy import process
import logging.config
import re
from square_catalog import SquareCatalog
from square.client import Client
from dotenv import load_dotenv
from pathlib import Path
import time
import uuid
import io

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
        
        # If the alias gave us a directory directly, use that
        if vendor_name.endswith('.com'):
            return vendor_name
        
        # Otherwise look up the vendor name in vendors
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
    
    def upload_image_to_square(self, image_path, variation_id, needs_primary=True):
        """Upload an image to Square and associate it with item/variations as needed."""
        try:
            logger.info(f"Uploading image {image_path} for variation {variation_id}")
            logger.info(f"Will set as primary: {needs_primary}")
            
            # Get file info
            image_file = Path(image_path)
            file_name = image_file.name
            
            logger.info(f"File name: {file_name}")
            logger.info(f"File size: {image_file.stat().st_size} bytes")
            
            # First, get the item ID and all variation IDs from the variation
            result = self.catalog_api.retrieve_catalog_object(
                object_id=variation_id
            )
            
            if not result.is_success():
                logger.error("Failed to get item ID from variation")
                return None
            
            item_id = result.body['object']['item_variation_data']['item_id']
            logger.info(f"Found parent item ID: {item_id}")
            
            # Get all variations for this item
            item_result = self.catalog_api.retrieve_catalog_object(
                object_id=item_id
            )
            
            if not item_result.is_success():
                logger.error("Failed to get item details")
                return None
            
            variation_ids = [
                var['id'] 
                for var in item_result.body['object']['item_data']['variations']
            ]
            logger.info(f"Found variations: {variation_ids}")
            
            # Check if item or variation already has images
            if item_result.body['object']['item_data'].get('image_ids'):
                logger.info("Item already has images - skipping upload")
                return None
            
            for var in item_result.body['object']['item_data']['variations']:
                if var.get('image_ids'):
                    logger.info(f"Variation {var['id']} already has images - skipping upload")
                    return None
            
            # Create unique idempotency key using timestamp and UUID
            idempotency_key = f"test_upload_{int(time.time())}_{uuid.uuid4()}"
            
            # Create request for testing - including item ID and all variation IDs
            request = {
                "idempotency_key": idempotency_key,
                "object_id": item_id,  # Associate with parent item
                "image": {
                    "type": "IMAGE",
                    "id": "#TEMP_ID",
                    "image_data": {
                        "name": file_name,
                        "caption": f"Image for item {item_id}",
                        "is_primary": needs_primary  # Use the parameter
                    }
                }
            }
            
            logger.info(f"Request data: {request}")
            logger.info(f"Setting as {'primary' if needs_primary else 'additional'} image")
            
            # Create a file-like object from the image data
            with open(image_path, 'rb') as f:
                image_data = f.read()
                image_file_obj = io.BytesIO(image_data)
                image_file_obj.name = file_name
                
                # Make the API call with the file-like object
                result = self.catalog_api.create_catalog_image(
                    request=request,
                    image_file=image_file_obj
                )
            
            if result.is_success():
                # Check if we have the expected data structure
                if 'image' in result.body:
                    image_id = result.body['image']['id']
                elif 'catalog_object' in result.body:
                    image_id = result.body['catalog_object']['id']
                else:
                    logger.error(f"Unexpected response structure: {result.body}")
                    return None
                    
                logger.info(f"Upload successful! Image ID: {image_id}")
                
                # Now associate the image with all variations using batch upsert
                batch_request = {
                    "idempotency_key": f"batch_{idempotency_key}",
                    "batches": [{
                        "objects": [{
                            "type": "ITEM",
                            "id": item_id,
                            "item_data": {
                                "variations": [
                                    {
                                        "id": var_id,
                                        "item_variation_data": {
                                            "image_ids": [image_id]
                                        }
                                    } for var_id in variation_ids
                                ]
                            }
                        }]
                    }]
                }
                
                batch_result = self.catalog_api.batch_upsert_catalog_objects(
                    body=batch_request
                )
                
                if batch_result.is_success():
                    logger.info("Successfully associated image with all variations")
                    return image_id
                else:
                    logger.error("Failed to associate image with variations")
                    logger.error(f"Errors: {batch_result.errors}")
                    return None
                
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
            result = self.catalog_api.update_catalog_image(
                body={
                    "idempotency_key": f"associate_{image_id}_{variation_id}",
                    "image": {
                        "id": image_id,
                        "item_variation_ids": [variation_id]
                    }
                }
            )
            
            if result.is_success():
                logger.info(f"Successfully associated image {image_id} with variation {variation_id}")
            else:
                logger.error(f"Failed to associate image: {result.errors}")
                
        except Exception as e:
            logger.error(f"Error associating image: {str(e)}")
    
    def process_matches(self, matches):
        """Process matches and upload images to Square."""
        logger.info("\n=== Processing Matches and Uploading Images ===")
        
        successful_uploads = 0
        failed_uploads = 0
        
        for match in matches:
            logger.info(f"\nProcessing match for {match['item_name']} - {match['variation_name']}")
            
            image_id = self.upload_image_to_square(
                match['image_path'],
                match['variation_id']
            )
            
            if image_id:
                successful_uploads += 1
                logger.info(f"Successfully processed match with image ID: {image_id}")
            else:
                failed_uploads += 1
                logger.error(f"Failed to process match for variation {match['variation_id']}")
        
        logger.info("\n=== Image Upload Summary ===")
        logger.info(f"Successful uploads: {successful_uploads}")
        logger.info(f"Failed uploads: {failed_uploads}")
        
        return successful_uploads, failed_uploads

if __name__ == "__main__":
    matcher = ImageMatcher()
    
    logger.info("\n=== Starting Image Matcher ===")
    
    # Track statistics
    total_items = 0
    total_variations = 0
    matched_items = set()
    matched_variations = 0
    unmatched_items = []
    successful_uploads = 0
    
    # Get all items needing images
    items = matcher.square.get_items_without_images()
    total_items = len(items)
    
    # Process items until we get 3 successful uploads
    matches = []
    for item in items:
        if successful_uploads >= 3:
            break
            
        item_name = item['item_data']['name']
        variations = item['item_data']['variations']
        needs_primary = item['item_data']['needs_primary_image']
        
        logger.info(f"\nProcessing Square Item: '{item_name}'")
        logger.info(f"Needs primary image: {needs_primary}")
        
        for var in variations:
            if successful_uploads >= 3:
                break
                
            var_name = var['name']
            vendor_name = var['vendor_name']
            
            logger.info(f"  Variation: '{var_name}'")
            logger.info(f"  Vendor: {vendor_name}")
            logger.info(f"  Needs image: {var.get('needs_image', False)}")
            
            # Skip if variation doesn't need image
            if not var.get('needs_image', False) and not needs_primary:
                logger.info("  Skipping - no image needed")
                continue
            
            vendor_dir = matcher.get_vendor_directory(vendor_name)
            if not vendor_dir:
                logger.warning(f"No directory mapping found for vendor: {vendor_name}")
                continue
            
            logger.info(f"  Looking in directory: {vendor_dir}")
            image_files = matcher.get_image_files(vendor_dir)
            
            # Use item name for matching unless variation name is more specific
            name_to_match = item_name
            if var_name != "Regular" and var_name != item_name:
                name_to_match = f"{item_name} {var_name}"
            
            logger.info(f"  Using name for matching: '{name_to_match}'")
            
            best_match, match_ratio = matcher.find_best_match(name_to_match, image_files)
            
            if best_match:
                match_data = {
                    'item_name': item_name,
                    'variation_name': var_name,
                    'variation_id': var['id'],
                    'sku': var['sku'],
                    'vendor': vendor_name,
                    'image_file': best_match,
                    'image_path': os.path.join(matcher.base_dir, vendor_dir, best_match),
                    'match_ratio': match_ratio,
                    'needs_primary': needs_primary
                }
                
                # Try to upload immediately
                image_id = matcher.upload_image_to_square(
                    match_data['image_path'],
                    match_data['variation_id'],
                    needs_primary=needs_primary
                )
                
                if image_id:
                    successful_uploads += 1
                    matches.append(match_data)
                    logger.info(f"Successfully uploaded image ({successful_uploads}/3)")
                    matched_items.add(item_name)
                    matched_variations += 1
                    # Clear needs_primary flag after successful primary upload
                    if needs_primary:
                        needs_primary = False
                else:
                    logger.error(f"Failed to upload image for {name_to_match}")
            else:
                logger.warning(f"  No match found for: {name_to_match} (Vendor: {vendor_name})")
                unmatched_items.append({
                    'item_name': item_name,
                    'variation_name': var_name,
                    'vendor': vendor_name
                })
    
    # Log summary
    logger.info("\n=== Summary ===")
    logger.info(f"Items processed until 3 successful uploads")
    logger.info(f"Total variations processed: {total_variations}")
    logger.info(f"Successful uploads: {successful_uploads}")
    logger.info(f"Items with at least one match: {len(matched_items)}")
    logger.info(f"Total variations matched: {matched_variations}")
    logger.info(f"Unmatched variations: {len(unmatched_items)}")
    
    # Add detailed successful uploads section
    logger.info("\n=== Successfully Uploaded Images ===")
    for match in matches:
        logger.info(f"Item: {match['item_name']}")
        logger.info(f"  Variation: {match['variation_name']}")
        logger.info(f"  Vendor: {match['vendor']}")
        logger.info(f"  Image: {match['image_file']}")
        logger.info(f"  Match Score: {match['match_ratio']}%")
        logger.info("-" * 50)
    
    logger.info("\nUnmatched items have been written to 'unmatched.txt'")
    
    # Write unmatched items to file
    with open('unmatched.txt', 'w') as f:
        f.write("=== Unmatched Items ===\n\n")
        for item in unmatched_items:
            f.write(f"Item Name: {item['item_name']}\n")
            f.write(f"Variation: {item['variation_name']}\n")
            f.write(f"Vendor: {item['vendor']}\n")
            f.write("-" * 50 + "\n")