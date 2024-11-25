import os
from dotenv import load_dotenv
from square.client import Client
import logging
from pprint import pformat

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('square_catalog.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

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
        """Fetch catalog items that don't have images assigned"""
        try:
            items_without_images = []
            cursor = None
            
            while True:
                result = self.client.catalog.list_catalog(
                    types="ITEM",
                    cursor=cursor
                )
                
                if result.is_success():
                    for item in result.body.get('objects', []):
                        item_data = {
                            'id': item.get('id'),
                            'type': item.get('type'),
                            'item_data': {
                                'name': item.get('item_data', {}).get('name'),
                                'variations': []
                            }
                        }
                        
                        # Check if item has no image
                        if not item.get('item_data', {}).get('image_ids'):
                            variations = item.get('item_data', {}).get('variations', [])
                            for variation in variations:
                                var_data = variation.get('item_variation_data', {})
                                vendor_infos = var_data.get('item_variation_vendor_infos', [])
                                
                                if vendor_infos:
                                    vendor_info = vendor_infos[0].get('item_variation_vendor_info_data', {})
                                    var_vendor_id = vendor_info.get('vendor_id')
                                    var_vendor_name = self.vendor_map.get(var_vendor_id, 'Unknown')
                                else:
                                    var_vendor_id = None
                                    var_vendor_name = 'Unknown'
                                
                                variation_data = {
                                    'id': variation.get('id'),
                                    'name': var_data.get('name'),
                                    'sku': var_data.get('sku'),
                                    'vendor_id': var_vendor_id,
                                    'vendor_name': var_vendor_name
                                }
                                item_data['item_data']['variations'].append(variation_data)
                            
                            items_without_images.append(item_data)
                            logger.info(f"Found item without image: {item_data['item_data']['name']}")
                    
                    cursor = result.body.get('cursor')
                    if not cursor:
                        break
                else:
                    logger.error(f"Error fetching catalog: {result.errors}")
                    break
            
            logger.info(f"Found total of {len(items_without_images)} items without images")
            return items_without_images
            
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