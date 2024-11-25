import os
from dotenv import load_dotenv
from square.client import Client
import logging

# Load environment variables
load_dotenv()

# Set up logging
logger = logging.getLogger('square_check')
logger.setLevel(logging.INFO)

# Create handlers
file_handler = logging.FileHandler('square_check.log', mode='w')
console_handler = logging.StreamHandler()

# Create formatters and add it to handlers
log_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(log_format)
console_handler.setFormatter(log_format)

# Add handlers to the logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)

def check_square_items(search_term=None):
    """Check items in Square catalog, optionally filtering by search term."""
    try:
        client = Client(
            access_token=os.getenv('SQUARE_ACCESS_TOKEN'),
            environment=os.getenv('SQUARE_ENVIRONMENT', 'sandbox')
        )
        
        logger.info("=== Square Catalog Check ===")
        logger.info(f"Environment: {os.getenv('SQUARE_ENVIRONMENT', 'sandbox')}")
        logger.info(f"Search Term: {search_term if search_term else 'None'}\n")
        
        # Get all catalog items
        result = client.catalog.list_catalog(
            types="ITEM"
        )
        
        if result.is_success():
            items = result.body.get('objects', [])
            logger.info(f"Total items found in catalog: {len(items)}")
            
            # Log all items and their details
            logger.info("\n=== Catalog Items ===")
            for item in items:
                item_data = item.get('item_data', {})
                item_name = item_data.get('name', 'No Name')
                variations = item_data.get('variations', [])
                
                # If search term provided, only show matching items
                if search_term and search_term.lower() not in item_name.lower():
                    continue
                
                logger.info(f"\nItem: {item_name}")
                logger.info(f"ID: {item.get('id')}")
                logger.info("Variations:")
                
                for var in variations:
                    var_data = var.get('item_variation_data', {})
                    logger.info(f"  - Name: {var_data.get('name')}")
                    logger.info(f"    SKU: {var_data.get('sku')}")
                    logger.info(f"    ID: {var.get('id')}")
                    
                    # Check for custom attributes (like vendor)
                    custom_attributes = var_data.get('custom_attributes', [])
                    for attr in custom_attributes:
                        if attr.get('name') == 'vendor_name':
                            logger.info(f"    Vendor: {attr.get('string_value')}")
                    
                    # Check if variation has image
                    image_ids = var.get('image_ids', [])
                    logger.info(f"    Has Image: {'Yes' if image_ids else 'No'}")
                    
        else:
            logger.error("Failed to get catalog items:")
            for error in result.errors:
                logger.error(f"Error: {error}")
                
    except Exception as e:
        logger.error(f"Exception during catalog check: {str(e)}")

if __name__ == "__main__":
    # Check for specific item
    check_square_items("Artillery Shells - Assorted Color")
    
    # Uncomment to see all items
    # check_square_items() 