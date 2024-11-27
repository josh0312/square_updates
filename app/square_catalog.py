import os
from dotenv import load_dotenv
from square.client import Client
import logging
from pprint import pformat

# Load environment variables
load_dotenv()

# Set up logging specifically for square_catalog
logger = logging.getLogger('square_catalog')
logger.setLevel(logging.INFO)
logger.handlers = []  # Clear any existing handlers

# Create handlers
file_handler = logging.FileHandler('square_catalog.log', mode='w')
console_handler = logging.StreamHandler()

# Create formatters and add it to handlers
log_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(log_format)
console_handler.setFormatter(log_format)

# Add handlers to the logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)

class SquareCatalog:
    def __init__(self):
        self.client = Client(
            access_token=os.getenv('SQUARE_ACCESS_TOKEN'),
            environment='production'
        )
        # Get vendor mapping on initialization
        self.vendor_map = self.get_vendors()
        
    def get_vendors(self):
        """Fetch all vendors using the Vendors API"""
        try:
            logger.info("\n=== Fetching Vendors Using Vendors API ===")
            vendor_map = {}
            
            body = {
                "filter": {
                    "status": ["ACTIVE"]
                },
                "sort": {
                    "field": "NAME",
                    "order": "ASC"
                }
            }
            
            result = self.client.vendors.search_vendors(
                body=body
            )
            
            if result.is_success():
                vendors = result.body.get('vendors', [])
                logger.info(f"Found {len(vendors)} vendors")
                
                for vendor in vendors:
                    vendor_id = vendor.get('id')
                    vendor_name = vendor.get('name')
                    if vendor_id and vendor_name:
                        vendor_map[vendor_id] = vendor_name
                        logger.info(f"Mapped vendor: {vendor_name}")
                
                return vendor_map
            else:
                logger.error("Failed to fetch vendors:")
                logger.error(pformat(result.errors))
                return {}
                
        except Exception as e:
            logger.error(f"Error fetching vendors: {str(e)}")
            return {}
        
    def get_items_without_images(self):
        """Fetch catalog items that need images (either item-level or variation-level)"""
        try:
            items_needing_images = []
            cursor = None
            
            while True:
                body = {
                    "product_types": ["REGULAR"],
                    "state_filters": {
                        "states": ["ACTIVE"]  # Only active items
                    }
                }
                
                if cursor:
                    body["cursor"] = cursor
                
                result = self.client.catalog.search_catalog_items(
                    body=body
                )
                
                if result.is_success():
                    for item in result.body.get('items', []):
                        item_data = item.get('item_data', {})
                        variations = item_data.get('variations', [])
                        
                        # Check if item needs a primary image
                        item_image_ids = item_data.get('image_ids', [])
                        needs_primary_image = len(item_image_ids) == 0
                        
                        # If item has a primary image, we can skip checking variations
                        if not needs_primary_image:
                            continue
                        
                        item_data_formatted = {
                            'id': item.get('id'),
                            'type': item.get('type'),
                            'item_data': {
                                'name': item_data.get('name'),
                                'needs_primary_image': needs_primary_image,
                                'variations': []
                            }
                        }
                        
                        # Process each variation independently
                        for variation in variations:
                            var_data = variation.get('item_variation_data', {})
                            var_image_ids = variation.get('image_ids', [])
                            
                            # Get vendor name from variation name
                            var_name = var_data.get('name', '')
                            vendor_name = 'Unknown'
                            
                            # Map common vendor codes
                            if var_name.startswith('WN'):
                                vendor_name = 'Winco'
                            elif var_name.startswith('RR'):
                                vendor_name = 'Red Rhino'
                            elif var_name.startswith('RN'):
                                vendor_name = 'Raccoon'
                            elif var_name.startswith('WC'):
                                vendor_name = 'Jakes'  # World Class = Jakes
                            
                            # If still unknown, try vendor_infos
                            if vendor_name == 'Unknown':
                                vendor_infos = var_data.get('item_variation_vendor_infos', [])
                                if vendor_infos:
                                    vendor_info = vendor_infos[0].get('item_variation_vendor_info_data', {})
                                    var_vendor_id = vendor_info.get('vendor_id')
                                    vendor_name = self.vendor_map.get(var_vendor_id, 'Unknown')
                            
                            # Check if variation needs an image
                            needs_variation_image = len(var_image_ids) == 0
                            
                            variation_data = {
                                'id': variation.get('id'),
                                'name': var_data.get('name'),
                                'sku': var_data.get('sku'),
                                'vendor_name': vendor_name,
                                'needs_image': needs_variation_image
                            }
                            
                            # Only add variation if it needs an image
                            if needs_variation_image:
                                item_data_formatted['item_data']['variations'].append(variation_data)
                                
                                if needs_primary_image:
                                    logger.info(f"Item {item_data.get('name')} needs primary image")
                                if needs_variation_image:
                                    logger.info(f"Variation {var_name} needs its own image")
                        
                        # Only add item if it needs a primary image AND has variations needing images
                        if needs_primary_image and item_data_formatted['item_data']['variations']:
                            items_needing_images.append(item_data_formatted)
                            logger.info(f"\nFound item with image needs: {item_data.get('name')}")
                            logger.info(f"  Needs primary image: {needs_primary_image}")
                            logger.info(f"  Variations needing images: {len(item_data_formatted['item_data']['variations'])}")
                            
                            # Log vendor info for debugging
                            for var in item_data_formatted['item_data']['variations']:
                                logger.info(f"  Variation: {var['name']} -> Vendor: {var['vendor_name']}")
                                logger.info(f"    Needs image: {var['needs_image']}")
                    
                    cursor = result.body.get('cursor')
                    if not cursor:
                        break
                else:
                    logger.error(f"Error fetching catalog: {result.errors}")
                    break
            
            logger.info(f"\nFound total of {len(items_needing_images)} items needing images")
            return items_needing_images
            
        except Exception as e:
            logger.error(f"Error accessing Square catalog: {str(e)}")
            return None

if __name__ == "__main__":
    catalog = SquareCatalog()
    items = catalog.get_items_without_images()
    
    if items:
        for item in items:
            print(f"\nItem: {item['item_data']['name']} (ID: {item['id']})")
            if item['item_data']['variations']:
                print("Variations:")
                for var in item['item_data']['variations']:
                    print(f"  - SKU {var['sku']}: {var['name']} | {var['vendor_name']}")