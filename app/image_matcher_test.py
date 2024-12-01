import os
from app.services.image_matcher import ImageMatcher
import logging
from dotenv import load_dotenv
from square.client import Client
from pathlib import Path
import io
import time
import uuid

# Load environment variables first
load_dotenv()

# Configure test logger
logger = logging.getLogger('image_matcher_test')
logger.setLevel(logging.INFO)

# Create handlers
file_handler = logging.FileHandler('matcher_test.log', mode='w')
console_handler = logging.StreamHandler()

# Create formatters and add it to handlers
log_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(log_format)
console_handler.setFormatter(log_format)

# Add handlers to the logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)

def test_single_upload(image_path, variation_id):
    """Test uploading a single image directly using Square client."""
    try:
        client = Client(
            access_token=os.getenv('SQUARE_ACCESS_TOKEN'),
            environment=os.getenv('SQUARE_ENVIRONMENT', 'sandbox')
        )
        
        # Get file info
        image_file = Path(image_path)
        file_name = image_file.name
        
        logger.info(f"Attempting to upload image: {image_path}")
        logger.info(f"File name: {file_name}")
        logger.info(f"File size: {image_file.stat().st_size} bytes")
        
        # Create unique idempotency key using timestamp and UUID
        idempotency_key = f"test_upload_{int(time.time())}_{uuid.uuid4()}"
        
        # Create simple request for testing
        request = {
            "idempotency_key": idempotency_key,
            "object_id": variation_id,
            "image": {
                "type": "IMAGE",
                "id": "#TEMP_ID",
                "image_data": {
                    "name": file_name,
                    "caption": f"Image for variation {variation_id}"
                }
            }
        }
        
        logger.info(f"Request data: {request}")
        
        # Create a file-like object from the image data
        with open(image_path, 'rb') as f:
            image_data = f.read()
            image_file_obj = io.BytesIO(image_data)
            image_file_obj.name = file_name
            
            # Make the API call with the file-like object
            result = client.catalog.create_catalog_image(
                request=request,
                image_file=image_file_obj
            )
        
        # Log the entire response for debugging
        logger.info("API Response:")
        logger.info(f"Success: {result.is_success()}")
        logger.info(f"Body: {result.body}")
        if hasattr(result, 'errors') and result.errors:
            logger.error("Errors found:")
            for error in result.errors:
                logger.error(f"Category: {error.get('category')}")
                logger.error(f"Code: {error.get('code')}")
                logger.error(f"Detail: {error.get('detail')}")
        
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
            return image_id
        else:
            logger.error("Upload failed!")
            return None
            
    except Exception as e:
        logger.error(f"Exception during test: {str(e)}")
        logger.error(f"Exception type: {type(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return None

def test_specific_item(item_name="Artillery Shells - Assorted Color", vendor=None):
    """Test uploading an image for a specific item, optionally from a specific vendor."""
    logger.info("=== Starting Specific Item Test ===")
    
    # Verify environment variables
    access_token = os.getenv('SQUARE_ACCESS_TOKEN')
    environment = os.getenv('SQUARE_ENVIRONMENT', 'sandbox')
    
    logger.info(f"Square Environment: {environment}")
    logger.info(f"Access Token Present: {'Yes' if access_token else 'No'}")
    logger.info(f"Looking for item: {item_name}" + (f" from {vendor}" if vendor else " from any vendor"))
    
    # Initialize matcher
    matcher = ImageMatcher()
    
    # Get matches
    matches = matcher.find_matches()
    
    if not matches:
        logger.error("No matches found to test with!")
        return
        
    # Log all items we have matches for
    logger.info("\nAll available matches:")
    for match in matches:
        logger.info(f"Item: {match['item_name']} | Vendor: {match['vendor']}")
    
    # Find items with similar names
    similar_matches = [
        match for match in matches 
        if item_name.lower() in match['item_name'].lower()
        and (vendor is None or match['vendor'].lower() == vendor.lower())
    ]
    
    if not similar_matches:
        logger.error(f"No items found containing '{item_name}'" + 
                    (f" from vendor '{vendor}'" if vendor else ""))
        return
    
    logger.info("\nFound similar matches:")
    for match in similar_matches:
        logger.info(f"Item: {match['item_name']} | Vendor: {match['vendor']}")
    
    # Use the first match
    test_match = similar_matches[0]
    
    logger.info("\n=== Testing with matched item ===")
    logger.info(f"Item Name: {test_match['item_name']}")
    logger.info(f"Variation: {test_match['variation_name']}")
    logger.info(f"Variation ID: {test_match['variation_id']}")
    logger.info(f"Vendor: {test_match['vendor']}")
    logger.info(f"SKU: {test_match['sku']}")
    logger.info(f"Image Path: {test_match['image_path']}")
    
    # Try upload with simplified method
    image_id = test_single_upload(
        test_match['image_path'],
        test_match['variation_id']
    )
    
    if image_id:
        logger.info(f"Test successful! Image ID: {image_id}")
    else:
        logger.error("Test failed!")
    
    logger.info("\n=== Test Complete ===")

if __name__ == "__main__":
    # Try without specifying vendor
    test_specific_item("Artillery Shells - Assorted Color") 