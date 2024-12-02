from square.client import Client
from fastapi import HTTPException
from typing import List, Optional
from pprint import pformat
from app.core.config import settings
from app.utils.logger import setup_logger
from app.utils.paths import paths
from app.utils.verify_paths import PathVerifier
import sys

logger = setup_logger('square_catalog')

class SquareCatalog:
    def __init__(self):
        self.client = Client(
            access_token=settings.SQUARE_ACCESS_TOKEN,
            environment=settings.SQUARE_ENVIRONMENT
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
        """Fetch catalog items that need images"""
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
                            item_name = item_data.get('name')
                            
                            # Log item details with all its variations
                            logger.info(f"\nItem: {item_name}")
                            logger.info(f"  Needs primary image: {needs_primary_image}")
                            logger.info(f"  Total variations: {len(item_data_formatted['item_data']['variations'])}")
                            logger.info("  Variations:")
                            for var in item_data_formatted['item_data']['variations']:
                                logger.info(f"    - {var['name']} ({var['vendor_name']})")
                    
                    cursor = result.body.get('cursor')
                    if not cursor:
                        break
                else:
                    logger.error(f"Error fetching catalog: {result.errors}")
                    break
            
            # Summary section grouped by vendor
            if items_needing_images:
                logger.info("\n" + "="*50)
                logger.info("SQUARE CATALOG IMAGE NEEDS SUMMARY")
                logger.info("="*50)
                
                # Collect stats by vendor
                vendor_stats = {}
                for item in items_needing_images:
                    for var in item['item_data']['variations']:
                        vendor = var['vendor_name']
                        if vendor not in vendor_stats:
                            vendor_stats[vendor] = {
                                'items': set(),  # Use set to avoid duplicates
                                'variations': [],
                                'skus': set()
                            }
                        vendor_stats[vendor]['items'].add(item['item_data']['name'])
                        vendor_stats[vendor]['variations'].append(var['name'])
                        if var.get('sku'):
                            vendor_stats[vendor]['skus'].add(var['sku'])

                # Print vendor-specific summaries
                for vendor, stats in sorted(vendor_stats.items()):
                    logger.info(f"\n{vendor} Details:")
                    logger.info(f"  • Items needing images: {len(stats['items'])}")
                    logger.info(f"  • Variations needing images: {len(stats['variations'])}")
                    logger.info(f"  • Unique SKUs: {len(stats['skus'])}")
                    
                    # List SKUs if available
                    if stats['skus']:
                        logger.info("\n  SKUs missing images:")
                        for sku in sorted(stats['skus']):
                            logger.info(f"    - {sku}")

                # Overall totals
                total_items = sum(len(stats['items']) for stats in vendor_stats.values())
                total_variations = sum(len(stats['variations']) for stats in vendor_stats.values())
                total_skus = sum(len(stats['skus']) for stats in vendor_stats.values())
                
                logger.info("\nOverall Totals:")
                logger.info(f"  • Total unique items: {total_items}")
                logger.info(f"  • Total variations: {total_variations}")
                logger.info(f"  • Total unique SKUs: {total_skus}")
                logger.info("="*50 + "\n")
            
            logger.info(f"\nFound total of {len(items_needing_images)} items needing images")
            return items_needing_images
            
        except Exception as e:
            logger.error(f"Error accessing Square catalog: {str(e)}")
            return None

if __name__ == "__main__":
    # Verify paths first
    verifier = PathVerifier()
    if not verifier.verify_all():
        logger.error("Path verification failed!")
        sys.exit(1)
    
    # Continue with existing code
    catalog = SquareCatalog()
    items = catalog.get_items_without_images()
    
    if items:
        logger.info("\nDetailed Item Breakdown:")
        # Group by vendor
        vendor_items = {}
        for item in items:
            for var in item['item_data']['variations']:
                vendor = var['vendor_name']
                if vendor not in vendor_items:
                    vendor_items[vendor] = []
                vendor_items[vendor].append({
                    'name': item['item_data']['name'],
                    'sku': var['sku'],
                    'variation': var['name']
                })
        
        # Print by vendor
        for vendor, items in sorted(vendor_items.items()):
            logger.info(f"\n{vendor} Items:")
            for item in sorted(items, key=lambda x: x['sku']):
                logger.info(f"  • {item['sku']}: {item['name']}")