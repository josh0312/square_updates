import logging
from square_catalog import SquareCatalog

# Set up logging
logger = logging.getLogger('square_catalog_test')
logger.setLevel(logging.INFO)

# Create handlers
file_handler = logging.FileHandler('square_catalog_test.log', mode='w')
console_handler = logging.StreamHandler()

# Create formatters and add it to handlers
log_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(log_format)
console_handler.setFormatter(log_format)

# Add handlers to the logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)

def test_square_catalog():
    """Test Square catalog functionality"""
    logger.info("=== Starting Square Catalog Test ===")
    
    # Initialize catalog
    catalog = SquareCatalog()
    
    # Get items without images
    logger.info("Fetching items without images...")
    items = catalog.get_items_without_images()
    
    if items:
        logger.info(f"\nFound {len(items)} items without images:")
        for item in items:
            logger.info(f"\nItem: {item['item_data']['name']}")
            logger.info("Variations:")
            for var in item['item_data']['variations']:
                logger.info(f"  - {var['name']} (Vendor: {var['vendor_name']}, SKU: {var['sku']})")
    else:
        logger.error("No items found or error occurred")
    
    logger.info("\n=== Test Complete ===")

if __name__ == "__main__":
    test_square_catalog() 