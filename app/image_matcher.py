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
    
    def clean_name(self, name, is_red_rhino=False):
        """Clean product name for better matching"""
        if not name:
            logger.warning("Received empty name for cleaning")
            return ""
        
        # Convert to string and lowercase
        name = str(name).lower().strip()
        
        # For Red Rhino images, remove product code if present
        if is_red_rhino:
            # Remove product codes
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
            'safe and sane'
        ]
        
        # Define stop words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'with', 'by'}
        
        # First clean special characters
        name = re.sub(r'[_\-/\\]', ' ', name)
        
        # Keep alphanumeric characters and spaces
        name = re.sub(r'[^a-z0-9\s]', '', name)
        
        # Split into words
        words = name.split()
        
        # Remove descriptive terms
        cleaned_words = []
        i = 0
        while i < len(words):
            skip = False
            # Check each descriptive term
            for term in descriptive_terms:
                term_words = term.split()
                if i + len(term_words) <= len(words):
                    # Check if the next few words match the term
                    if ' '.join(words[i:i+len(term_words)]).lower() == term.lower():
                        i += len(term_words)
                        skip = True
                        break
            if not skip and words[i] not in stop_words:
                cleaned_words.append(words[i])
            i += 1
        
        # Remove extra whitespace and join
        cleaned = ' '.join(cleaned_words).strip()
        
        if not cleaned:
            logger.warning(f"Cleaning resulted in empty string for input: '{name}'")
            return name
        
        logger.info(f"Cleaned name: '{name}' -> '{cleaned}'")
        return cleaned
    
    def find_best_match(self, name_to_match, image_files):
        """Find best matching image file for a given name"""
        if not image_files:
            logger.warning("No valid image names to match against")
            return None, 0
        
        is_red_rhino = 'redrhinofireworks.com' in str(image_files)
        
        logger.info(f"\n=== Starting Match Process ===")
        logger.info(f"Looking for match: '{name_to_match}'")
        logger.info(f"Number of images to check: {len(image_files)}")
        
        # Clean the name to match (no product code removal needed for Square name)
        clean_name = self.clean_name(name_to_match, is_red_rhino=False)
        logger.info(f"Final name to match: '{clean_name}'")
        
        logger.info("\nChecking each image:")
        best_match = None
        best_ratio = 0
        
        for image_file in image_files:
            # Get base name without extension
            base_name = os.path.splitext(image_file)[0]
            
            # Clean the image name WITH product code removal for Red Rhino
            clean_image = self.clean_name(base_name, is_red_rhino=True)
            
            # Calculate match ratio
            ratio = fuzz.ratio(clean_name, clean_image)
            logger.info(f"Comparing:")
            logger.info(f"  Clean name: '{clean_name}'")
            logger.info(f"  Image name: '{clean_image}'")
            logger.info(f"  Match ratio: {ratio}%")
            
            # Update best match if better ratio found
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = image_file
                logger.info(f"  New best match! Score: {ratio}%")
                
                # Early exit if we find a perfect match
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
            needs_primary = item['item_data']['needs_primary_image']
            
            logger.info(f"\nProcessing Square Item: '{item_name}'")
            logger.info(f"Needs primary image: {needs_primary}")
            
            # Check if item already has images
            if 'image_ids' in item['item_data'] and item['item_data']['image_ids']:
                logger.info("Item already has images - skipping")
                continue
                
            # Get all variations that need images
            variations_needing_images = []
            for var in variations:
                var_name = var['name']
                vendor_name = var['vendor_name']
                needs_image = var.get('needs_image', False)
                
                logger.info(f"  Variation: '{var_name}'")
                logger.info(f"  Vendor: {vendor_name}")
                logger.info(f"  Needs image: {needs_image}")
                
                # Check if variation already has images
                if 'image_ids' in var and var['image_ids']:
                    logger.info("  Variation already has images - skipping")
                    continue
                    
                # Skip if neither item nor variation needs an image
                if not needs_image and not needs_primary:
                    logger.info("  Skipping - no image needed")
                    continue
                    
                variations_needing_images.append(var)
            
            # If no variations need images, skip this item
            if not variations_needing_images:
                logger.info("No variations need images - skipping item")
                continue
                
            # Use first variation's vendor to find images
            vendor_name = variations_needing_images[0]['vendor_name']
            vendor_dir = self.get_vendor_directory(vendor_name)
            if not vendor_dir:
                logger.warning(f"No directory mapping found for vendor: {vendor_name}")
                continue
            
            logger.info(f"  Looking in directory: {vendor_dir}")
            image_files = self.get_image_files(vendor_dir)
            
            # Find best match using item name
            name_to_match = item_name
            logger.info(f"  Using name for matching: '{name_to_match}'")
            
            best_match, match_ratio = self.find_best_match(name_to_match, image_files)
            
            if best_match:
                # Create match data for each variation
                for var in variations_needing_images:
                    match_data = {
                        'item_name': item_name,
                        'variation_name': var['name'],
                        'variation_id': var['id'],
                        'sku': var['sku'],
                        'vendor': vendor_name,
                        'image_file': best_match,
                        'image_path': os.path.join(self.base_dir, vendor_dir, best_match),
                        'match_ratio': match_ratio,
                        'needs_primary': needs_primary
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
            
            # Check if item already has images BEFORE proceeding
            if item_result.body['object']['item_data'].get('image_ids'):
                logger.info("Item already has images - skipping upload")
                return "SKIPPED"
            
            # Get file info
            image_file = Path(image_path)
            file_name = image_file.name
            
            logger.info(f"File name: {file_name}")
            logger.info(f"File size: {image_file.stat().st_size} bytes")
            
            variation_ids = [
                var['id'] 
                for var in item_result.body['object']['item_data']['variations']
            ]
            logger.info(f"Found variations: {variation_ids}")
            
            # Create unique idempotency key
            idempotency_key = f"test_upload_{int(time.time())}_{uuid.uuid4()}"
            
            # Create request for image upload
            request = {
                "idempotency_key": idempotency_key,
                "object_id": item_id,
                "image": {
                    "type": "IMAGE",
                    "id": "#TEMP_ID",
                    "image_data": {
                        "name": file_name,
                        "caption": f"Image for item {item_id}",
                        "is_primary": needs_primary
                    }
                }
            }
            
            logger.info(f"Request data: {request}")
            logger.info(f"Setting as {'primary' if needs_primary else 'additional'} image")
            
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
                if 'image' in result.body:
                    image_id = result.body['image']['id']
                elif 'catalog_object' in result.body:
                    image_id = result.body['catalog_object']['id']
                else:
                    logger.error(f"Unexpected response structure: {result.body}")
                    return None
                    
                logger.info(f"Upload successful! Image ID: {image_id}")
                
                # Try to associate with variations, but don't fail if it doesn't work
                if variation_ids:
                    for var_id in variation_ids:
                        try:
                            update_request = {
                                "idempotency_key": f"update_{image_id}_{var_id}_{int(time.time())}",
                                "object": {
                                    "type": "ITEM_VARIATION",
                                    "id": var_id,
                                    "item_variation_data": {
                                        "image_ids": [image_id]
                                    }
                                }
                            }
                            
                            update_result = self.catalog_api.upsert_catalog_object(
                                body=update_request
                            )
                            
                            if not update_result.is_success():
                                logger.warning(f"Failed to associate image with variation {var_id}")
                                logger.warning(f"Error: {update_result.errors}")
                        except Exception as e:
                            logger.warning(f"Error associating image with variation {var_id}: {str(e)}")
                
                # Return success since the image was uploaded to the parent item
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
    
    logger.info(f"\n=== Processing {total_items} items ===")
    
    # Process all items
    matches = []
    for item in items:
        item_name = item['item_data']['name']
        variations = item['item_data']['variations']
        needs_primary = item['item_data']['needs_primary_image']
        
        logger.info(f"\nProcessing Square Item: '{item_name}'")
        logger.info(f"Needs primary image: {needs_primary}")
        
        for var in variations:
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
            
            # Use item name for matching, don't add variation name
            name_to_match = item_name  # Just use the item name
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
                    logger.info(f"Successfully processed {successful_uploads} of unlimited")
                    matched_items.add(item_name)
                    matched_variations += 1
                    # Clear needs_primary flag after successful primary upload
                    if needs_primary:
                        needs_primary = False
                elif image_id == "SKIPPED":
                    logger.info(f"Skipped upload for {name_to_match} - item already has images")
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
    logger.info(f"Total items processed: {total_items}")
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