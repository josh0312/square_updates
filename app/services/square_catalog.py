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
                        logger.info(f"Mapped vendor: {vendor_id} -> {vendor_name}")
                
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
            logger.info("\n=== Starting Catalog Item Search ===")
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
                        try:
                            # Debug logging (commented out but preserved)
                            # logger.info("\n=== Processing Item ===")
                            # logger.info("Raw item data:")
                            # logger.info(pformat(item))
                            
                            item_data = item.get('item_data', {})
                            variations = item_data.get('variations', [])
                            
                            # Check if item needs a primary image
                            item_image_ids = item_data.get('image_ids', [])
                            needs_primary_image = len(item_image_ids) == 0
                            logger.info(f"\nImage Status:")
                            logger.info(f"  Has Primary Image: {not needs_primary_image}")
                            if item_image_ids:
                                logger.info(f"  Image IDs: {item_image_ids}")
                            
                            # Get item-level data
                            item_gtin = item_data.get('gtin')
                            item_name = item_data.get('name')
                            item_sku = None
                            item_vendor_name = 'Unknown'
                            item_vendor_id = None
                            item_vendor_sku = None
                            
                            # Get vendor info from first variation if it exists
                            if variations:
                                var_data = variations[0].get('item_variation_data', {})
                                item_sku = var_data.get('sku')
                                vendor_infos = var_data.get('item_variation_vendor_infos', [])
                                if vendor_infos and vendor_infos[0].get('item_variation_vendor_info_data'):
                                    vendor_info = vendor_infos[0]['item_variation_vendor_info_data']
                                    item_vendor_id = vendor_info.get('vendor_id')
                                    item_vendor_sku = vendor_info.get('sku')
                                    item_vendor_name = self.vendor_map.get(item_vendor_id, 'Unknown')
                            
                            # Log item-level data
                            logger.info(f"\nItem Details:")
                            logger.info(f"  Name: {item_name}")
                            logger.info(f"  GTIN: {item_gtin}")
                            logger.info(f"  Square SKU: {item_sku}")
                            logger.info(f"  Vendor ID: {item_vendor_id}")
                            logger.info(f"  Vendor Name: {item_vendor_name}")
                            logger.info(f"  Vendor SKU: {item_vendor_sku}")
                            
                            # Process variations
                            logger.info(f"\nVariations ({len(variations)}):")
                            
                            # Check if we have any real variations (with IDs)
                            real_variations = []
                            for v in variations:
                                if v and isinstance(v, dict) and v.get('id'):
                                    real_variations.append(v)
                                else:
                                    logger.warning(f"Skipping invalid variation: {v}")
                            
                            logger.info(f"Found {len(real_variations)} real variations with IDs")
                            
                            if not real_variations:
                                # Single item with no variations
                                if needs_primary_image:
                                    # Only process if it needs a primary image
                                    variation_data = {
                                        'id': None,
                                        'name': item_name,
                                        'sku': item_sku,
                                        'gtin': item_gtin,
                                        'vendor_name': item_vendor_name,
                                        'vendor_id': item_vendor_id,
                                        'vendor_sku': item_vendor_sku,
                                        'needs_image': True  # Needs primary image
                                    }
                                    
                                    items_needing_images.append({
                                        'id': item.get('id'),
                                        'type': item.get('type'),
                                        'item_data': {
                                            'name': item_name,
                                            'gtin': item_gtin,
                                            'sku': item_sku,
                                            'vendor_name': item_vendor_name,
                                            'vendor_id': item_vendor_id,
                                            'vendor_sku': item_vendor_sku,
                                            'needs_primary_image': True,
                                            'variations': [variation_data]
                                        }
                                    })
                            else:
                                # Has variations - process each one
                                first_variation = True
                                current_vendor = None
                                needs_processing = False
                                
                                for variation in real_variations:
                                    try:
                                        var_data = variation.get('item_variation_data', {})
                                        var_name = var_data.get('name')
                                        var_sku = var_data.get('sku')
                                        var_gtin = var_data.get('gtin')
                                        var_vendor_name = 'Unknown'
                                        var_vendor_id = None
                                        var_vendor_sku = None
                                        
                                        # Get variation vendor info
                                        vendor_infos = var_data.get('item_variation_vendor_infos', [])
                                        if vendor_infos and vendor_infos[0].get('item_variation_vendor_info_data'):
                                            vendor_info = vendor_infos[0]['item_variation_vendor_info_data']
                                            var_vendor_id = vendor_info.get('vendor_id')
                                            var_vendor_sku = vendor_info.get('sku')
                                            var_vendor_name = self.vendor_map.get(var_vendor_id, 'Unknown')
                                        
                                        # First variation can provide primary image if needed
                                        needs_variation_image = True
                                        if first_variation:
                                            current_vendor = var_vendor_id
                                            if needs_primary_image:
                                                needs_processing = True
                                            first_variation = False
                                        else:
                                            # Subsequent variations need images if:
                                            # 1. They're from a different vendor than the first variation
                                            # 2. Or if they don't have their own image
                                            if var_vendor_id != current_vendor:
                                                needs_variation_image = True
                                                needs_processing = True
                                            else:
                                                needs_variation_image = len(var_data.get('image_ids', [])) == 0
                                                if needs_variation_image:
                                                    needs_processing = True
                                        
                                        if needs_processing:
                                            # Create variation data
                                            variation_data = {
                                                'id': variation.get('id'),
                                                'name': var_name,
                                                'sku': var_data.get('sku'),
                                                'gtin': var_gtin,
                                                'vendor_name': var_vendor_name,
                                                'vendor_id': var_vendor_id,
                                                'vendor_sku': vendor_info.get('sku'),
                                                'needs_image': needs_variation_image,
                                                'item_variation_data': var_data
                                            }
                                            
                                            # Log variation details
                                            logger.info(f"  Variation Details:")
                                            logger.info(f"    Name: {var_name}")
                                            logger.info(f"    GTIN: {var_gtin}")
                                            logger.info(f"    Square SKU: {var_data.get('sku')}")
                                            logger.info(f"    Vendor ID: {var_vendor_id}")
                                            logger.info(f"    Vendor Name: {var_vendor_name}")
                                            logger.info(f"    Vendor SKU: {vendor_info.get('sku')}")
                                            logger.info(f"    Has Own Image: {not needs_variation_image}")
                                            
                                            # Add to items needing images
                                            if not any(item['id'] == item.get('id') for item in items_needing_images):
                                                items_needing_images.append({
                                                    'id': item.get('id'),
                                                    'type': item.get('type'),
                                                    'item_data': {
                                                        'name': item_name,
                                                        'gtin': item_gtin,
                                                        'sku': item_sku,
                                                        'vendor_name': item_vendor_name,
                                                        'vendor_id': item_vendor_id,
                                                        'vendor_sku': item_vendor_sku,
                                                        'needs_primary_image': needs_primary_image,
                                                        'variations': []
                                                    }
                                                })
                                            
                                            # Find the item and append the variation
                                            for catalog_item in items_needing_images:
                                                if catalog_item['id'] == item.get('id'):
                                                    catalog_item['item_data']['variations'].append(variation_data)
                                                    break
                                    
                                    except Exception as var_error:
                                        logger.error(f"Error processing variation: {str(var_error)}")
                                        continue
                        
                        except Exception as item_error:
                            logger.error(f"Error processing item: {str(item_error)}")
                            continue
                    
                    cursor = result.body.get('cursor')
                    if not cursor:
                        break
                else:
                    logger.error(f"Error fetching catalog: {result.errors}")
                    break
            
            # Summary section
            if items_needing_images:
                try:
                    logger.info("\n" + "="*50)
                    logger.info("SQUARE CATALOG IMAGE NEEDS SUMMARY")
                    logger.info("="*50)
                    
                    # Collect stats by vendor
                    vendor_stats = {}
                    for item in items_needing_images:
                        item_data = item.get('item_data', {})
                        for var in item_data.get('variations', []):
                            vendor = var.get('vendor_name', 'Unknown')
                            if vendor not in vendor_stats:
                                vendor_stats[vendor] = {
                                    'items': set(),
                                    'variations': [],
                                    'skus': set()
                                }
                            vendor_stats[vendor]['items'].add(item_data.get('name', ''))
                            vendor_stats[vendor]['variations'].append(var.get('name', ''))
                            if var.get('sku'):
                                vendor_stats[vendor]['skus'].add(var['sku'])
                    
                    # Print vendor-specific summaries
                    for vendor, stats in sorted(vendor_stats.items()):
                        logger.info(f"\n{vendor} Details:")
                        logger.info(f"  • Items needing images: {len(stats['items'])}")
                        logger.info(f"  • Variations needing images: {len(stats['variations'])}")
                        logger.info(f"  • Unique SKUs: {len(stats['skus'])}")
                        
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
                    
                except Exception as summary_error:
                    logger.error(f"Error generating summary: {str(summary_error)}")
            
            return items_needing_images
            
        except Exception as e:
            logger.error(f"Error accessing Square catalog: {str(e)}")
            return []

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