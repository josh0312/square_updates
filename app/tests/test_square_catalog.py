import pytest
from app.services.square_catalog import SquareCatalog
from app.utils.logger import setup_logger
from .fixtures.square_responses import VENDOR_RESPONSE, CATALOG_ITEMS_RESPONSE

logger = setup_logger('test_square_catalog')

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