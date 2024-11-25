import os
from dotenv import load_dotenv
from square.client import Client
import logging
import json
from pprint import pformat

# Load environment variables
load_dotenv()

# Set up logging specifically for testing
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('square.log', mode='w'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class SquareCatalogTest:
    def __init__(self):
        self.client = Client(
            access_token=os.getenv('SQUARE_ACCESS_TOKEN'),
            environment='production'
        )
        logger.info("=== Initializing Square Catalog Test ===")
        
        # First get the vendor mapping
        self.vendor_map = self.get_vendors()
        logger.info(f"Loaded {len(self.vendor_map)} vendors")
    
    def get_vendors(self):
        """Fetch all vendors using the Vendors API"""
        try:
            logger.info("\n=== Fetching Vendors Using Vendors API ===")
            vendor_map = {}
            
            # Correct body structure according to API docs
            body = {
                "filter": {
                    "status": ["ACTIVE"]
                },
                "sort": {
                    "field": "NAME",
                    "order": "ASC"
                }
            }
            
            # Use the Vendors API endpoint with search_vendors
            result = self.client.vendors.search_vendors(
                body=body
            )
            
            if result.is_success():
                vendors = result.body.get('vendors', [])
                logger.info(f"\nFound {len(vendors)} vendors")
                logger.info("\nRaw vendor response:")
                logger.info(pformat(result.body))
                
                for vendor in vendors:
                    vendor_id = vendor.get('id')
                    vendor_name = vendor.get('name')
                    if vendor_id and vendor_name:
                        vendor_map[vendor_id] = vendor_name
                        logger.info(f"Mapped vendor: {vendor_name} (ID: {vendor_id})")
                        # Log full vendor details for analysis
                        logger.info(f"Full vendor data:")
                        logger.info(pformat(vendor))
                
                return vendor_map
            else:
                logger.error("Failed to fetch vendors:")
                logger.error(pformat(result.errors))
                return {}
                
        except Exception as e:
            logger.error(f"Error fetching vendors: {str(e)}", exc_info=True)
            return {}
    
    def test_catalog_items(self, limit=10):
        """Get detailed information for catalog items"""
        try:
            logger.info("\n=== Starting Catalog Items Test ===")
            logger.info("\nVendor Map:")
            for vendor_id, vendor_name in self.vendor_map.items():
                logger.info(f"{vendor_id}: {vendor_name}")
            
            result = self.client.catalog.list_catalog(
                types="ITEM"
            )
            
            if result.is_success():
                items = result.body.get('objects', [])[:limit]
                logger.info(f"\nAnalyzing {len(items)} items:")
                
                for idx, item in enumerate(items, 1):
                    item_data = item.get('item_data', {})
                    logger.info(f"\nItem {idx}: {item_data.get('name')}")
                    
                    # Check variations
                    variations = item_data.get('variations', [])
                    if variations:
                        for var in variations:
                            var_data = var.get('item_variation_data', {})
                            vendor_infos = var_data.get('item_variation_vendor_infos', [])
                            
                            # Log the complete vendor info structure
                            logger.info(f"\nVariation: {var_data.get('name')}")
                            logger.info(f"Raw vendor_infos: {pformat(vendor_infos)}")
                            
                            if vendor_infos:
                                vendor_info = vendor_infos[0].get('item_variation_vendor_info_data', {})
                                var_vendor_id = vendor_info.get('vendor_id')
                                var_vendor_name = self.vendor_map.get(var_vendor_id, f"Unknown (ID: {var_vendor_id})")
                                
                                logger.info(f"  SKU: {var_data.get('sku')}")
                                logger.info(f"  Vendor ID: {var_vendor_id}")
                                logger.info(f"  Vendor Name: {var_vendor_name}")
                            else:
                                logger.info("  No vendor info found")
                    else:
                        logger.info("  No variations")
                    
            else:
                logger.error("API call failed:")
                logger.error(pformat(result.errors))
                
        except Exception as e:
            logger.error(f"Error during test: {str(e)}", exc_info=True)

if __name__ == "__main__":
    test = SquareCatalogTest()
    test.test_catalog_items() 