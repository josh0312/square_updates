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
        
    def verify_item_needs_images(self, item_id):
        """Verify if an item needs images by checking directly with the API"""
        result = self.client.catalog.retrieve_catalog_object(
            object_id=item_id
        )
        if not result.is_success():
            logger.error(f"Failed to verify item {item_id}")
            return False, []
            
        item_data = result.body['object'].get('item_data', {})
        needs_primary = not bool(item_data.get('image_ids'))
        
        # Get all variations in one batch request
        variation_ids = [
            var.get('id') for var in item_data.get('variations', [])
            if var.get('id')
        ]
        
        if not variation_ids:
            return needs_primary, []
            
        # Batch request for all variations
        batch_result = self.client.catalog.batch_retrieve_catalog_objects(
            body={
                "object_ids": variation_ids
            }
        )
        
        if not batch_result.is_success():
            logger.error(f"Failed to fetch variations for item {item_id}")
            return needs_primary, []
            
        variations_needing_images = []
        for obj in batch_result.body.get('objects', []):
            var_data = obj.get('item_variation_data', {})
            if not var_data.get('image_ids'):
                vendor_infos = var_data.get('item_variation_vendor_infos', [])
                vendor_info = vendor_infos[0].get('item_variation_vendor_info_data', {}) if vendor_infos else {}
                
                variations_needing_images.append({
                    'id': obj.get('id'),
                    'name': var_data.get('name'),
                    'square_sku': var_data.get('sku'),
                    'vendor_sku': vendor_info.get('sku'),
                    'vendor_name': self.vendor_map.get(vendor_info.get('vendor_id'), 'Unknown'),
                    'needs_image': True
                })
        
        return needs_primary, variations_needing_images

    def get_items_without_images(self):
        """Fetch catalog items that need images"""
        try:
            items = []
            cursor = None
            total_processed = 0
            batch_size = 100
            
            logger.info("\nFetching and analyzing items from Square...")
            
            while True:
                body = {
                    "product_types": ["REGULAR"],
                    "state_filters": {"states": ["ACTIVE"]},
                    "limit": batch_size,
                    "include_related_objects": True,
                    "include_deleted_objects": False
                }
                
                if cursor:
                    body["cursor"] = cursor
                
                result = self.client.catalog.search_catalog_items(body=body)
                
                if not result.is_success():
                    logger.error(f"Error fetching catalog: {result.errors}")
                    break
                    
                # Log the raw response for debugging
                logger.debug("\nSquare Search Response:")
                logger.debug(pformat(result.body))
                    
                batch_items = result.body.get('items', [])
                related_objects = result.body.get('related_objects', [])
                
                if not batch_items:
                    break
                    
                logger.info(f"Processing batch of {len(batch_items)} items...")
                logger.debug(f"Found {len(related_objects)} related objects")
                
                # Create lookup for related objects
                variations_lookup = {}
                vendor_infos_lookup = {}
                category_lookup = {}
                
                for obj in related_objects:
                    obj_type = obj.get('type')
                    if obj_type == 'ITEM_VARIATION':
                        variations_lookup[obj['id']] = obj
                        logger.debug(f"\nVariation object:\n{pformat(obj)}")
                    elif obj_type == 'CATEGORY':
                        category_lookup[obj['id']] = obj
                        logger.debug(f"\nCategory object:\n{pformat(obj)}")
                    elif obj_type == 'ITEM_VARIATION_VENDOR_INFO_ASSOCIATION':
                        vendor_infos_lookup[obj['id']] = obj
                        logger.debug(f"\nVendor info object:\n{pformat(obj)}")
                
                # First, collect all items and variations that might need images
                items_to_check = []
                for item in batch_items:
                    logger.debug(f"\nProcessing item:\n{pformat(item)}")
                    item_data = item.get('item_data', {})
                    variations = item_data.get('variations', [])
                    
                    # Check if this is a single-variation item
                    is_single_variation = len(variations) <= 1
                    
                    # For single-variation items, only check primary image
                    if is_single_variation:
                        if not item_data.get('image_ids'):
                            items_to_check.append(item.get('id'))
                    else:
                        # For multi-variation items, check both primary and variations
                        needs_primary = not bool(item_data.get('image_ids'))
                        has_variations_needing_images = any(
                            not var.get('item_variation_data', {}).get('image_ids')
                            for var in variations
                        )
                        if needs_primary or has_variations_needing_images:
                            items_to_check.append(item.get('id'))
                
                if items_to_check:
                    batch_result = self.client.catalog.batch_retrieve_catalog_objects(
                        body={
                            "object_ids": items_to_check,
                            "include_related_objects": True,
                            "include_deleted_objects": False
                        }
                    )
                    
                    if batch_result.is_success():
                        # Log the raw batch response for debugging
                        logger.debug("\nSquare Batch Retrieve Response:")
                        logger.debug(pformat(batch_result.body))
                        
                        objects = batch_result.body.get('objects', [])
                        related = batch_result.body.get('related_objects', [])
                        
                        # Update lookups with additional related objects
                        for obj in related:
                            obj_type = obj.get('type')
                            if obj_type == 'ITEM_VARIATION':
                                variations_lookup[obj['id']] = obj
                                logger.debug(f"\nAdditional variation object:\n{pformat(obj)}")
                            elif obj_type == 'CATEGORY':
                                category_lookup[obj['id']] = obj
                                logger.debug(f"\nAdditional category object:\n{pformat(obj)}")
                            elif obj_type == 'ITEM_VARIATION_VENDOR_INFO_ASSOCIATION':
                                vendor_infos_lookup[obj['id']] = obj
                                logger.debug(f"\nAdditional vendor info object:\n{pformat(obj)}")
                        
                        # Process each item
                        for obj in objects:
                            logger.debug(f"\nProcessing batch item:\n{pformat(obj)}")
                            item_data = obj.get('item_data', {})
                            variations = item_data.get('variations', [])
                            is_single_variation = len(variations) <= 1
                            needs_primary = not bool(item_data.get('image_ids'))
                            item_name = item_data.get('name', '')
                            category_id = item_data.get('category_id')
                            category = category_lookup.get(category_id, {}).get('category_data', {}).get('name', '') if category_id else ''
                            
                            # Skip if single variation and has primary image
                            if is_single_variation and not needs_primary:
                                continue
                            
                            # Process variations
                            processed_variations = []
                            all_variations = []
                            
                            # Get item-level vendor info first
                            item_vendor_id = None
                            item_vendor_sku = ''
                            item_vendor_infos = item_data.get('item_vendor_infos', [])
                            for vendor_info in item_vendor_infos:
                                vendor_id = vendor_info.get('vendor_id')
                                if vendor_id in self.vendor_map:
                                    item_vendor_id = vendor_id
                                    item_vendor_sku = vendor_info.get('sku', '')
                                    logger.debug(f"\nFound item-level vendor info:\n{pformat(vendor_info)}")
                                    break
                            
                            for var_ref in variations:
                                var_id = var_ref.get('id')
                                if not var_id:
                                    continue
                                    
                                var = variations_lookup.get(var_id, {})
                                logger.debug(f"\nProcessing variation:\n{pformat(var)}")
                                var_data = var.get('item_variation_data', {})
                                
                                # Get Square SKU directly from variation data
                                square_sku = var_data.get('sku', '')
                                
                                # Get vendor info and vendor SKU
                                vendor_name = 'Unknown'
                                vendor_sku = ''
                                vendor_id = None
                                vendor_info_data = None
                                
                                # Get vendor info from item_variation_vendor_infos array
                                vendor_infos = var_data.get('item_variation_vendor_infos', [])
                                if vendor_infos:
                                    vendor_info = vendor_infos[0]
                                    if vendor_info:
                                        vendor_info_data = vendor_info.get('item_variation_vendor_info_data', {})
                                        if vendor_info_data:
                                            vendor_id = vendor_info_data.get('vendor_id')
                                            vendor_sku = vendor_info_data.get('sku', '')
                                            if vendor_id in self.vendor_map:
                                                vendor_name = self.vendor_map[vendor_id]
                                
                                # If no variation-level vendor info, use item-level
                                if vendor_name == 'Unknown' and item_vendor_id:
                                    vendor_id = item_vendor_id
                                    vendor_name = self.vendor_map[item_vendor_id]
                                    vendor_sku = item_vendor_sku
                                
                                # Get all three types of prices
                                vendor_price = 0.0
                                variation_price = 0.0
                                default_cost = 0.0
                                
                                # 1. Get vendor price from vendor_info_data
                                if vendor_info_data and vendor_info_data.get('price_money'):
                                    vendor_price_amount = vendor_info_data['price_money'].get('amount', 0)
                                    vendor_price = vendor_price_amount / 100.0 if vendor_price_amount else 0.0
                                
                                # 2. Get variation price from price_money
                                price_money = var_data.get('price_money', {})
                                variation_price_amount = price_money.get('amount', 0)
                                variation_price = variation_price_amount / 100.0 if variation_price_amount else 0.0
                                
                                # 3. Get default unit cost
                                default_cost_data = var_data.get('default_unit_cost', {})
                                default_cost_amount = default_cost_data.get('amount', 0)
                                default_cost = default_cost_amount / 100.0 if default_cost_amount else 0.0
                                
                                variation_name = var_data.get('name', '')
                                upc = var_data.get('upc', '')
                                
                                # For single-variation items, only care about primary image
                                needs_image = not is_single_variation and not var_data.get('image_ids')
                                
                                variation_info = {
                                    'id': var_id,
                                    'name': variation_name or item_name,  # Use item name if variation name is empty
                                    'square_sku': square_sku,
                                    'vendor_sku': vendor_sku,
                                    'vendor_name': vendor_name,
                                    'vendor_id': vendor_id,
                                    'vendor_price': vendor_price,
                                    'variation_price': variation_price,
                                    'default_cost': default_cost,
                                    'upc': upc,
                                    'needs_image': needs_image
                                }
                                
                                all_variations.append(variation_info)
                                if needs_image:
                                    processed_variations.append(variation_info)
                            
                            if needs_primary or (not is_single_variation and processed_variations):
                                items.append({
                                    'id': obj.get('id'),
                                    'name': item_name,
                                    'description': item_data.get('description', ''),
                                    'category': category,
                                    'needs_primary_image': needs_primary,
                                    'is_single_variation': is_single_variation,
                                    'variations': all_variations,
                                    'variations_needing_images': processed_variations
                                })
                
                total_processed += len(batch_items)
                logger.info(f"Total items processed so far: {total_processed}")
                
                cursor = result.body.get('cursor')
                if not cursor:
                    break
            
            # Log summary
            logger.info(f"\nAnalysis complete!")
            logger.info(f"Total items processed: {total_processed}")
            logger.info(f"Found {len(items)} items needing images")
            
            if items:
                # Count items and variations needing images
                single_variation_count = 0
                multi_variation_counts = {}
                total_variations_needing = 0
                
                for item in items:
                    if item['is_single_variation']:
                        single_variation_count += 1
                    else:
                        for var in item['variations_needing_images']:
                            vendor = var['vendor_name']
                            multi_variation_counts[vendor] = multi_variation_counts.get(vendor, 0) + 1
                            total_variations_needing += 1
                
                logger.info(f"\nSingle-variation items needing primary image: {single_variation_count}")
                
                if multi_variation_counts:
                    logger.info("\nMulti-variation items - variations needing images by vendor:")
                    for vendor, count in sorted(multi_variation_counts.items()):
                        logger.info(f"  {vendor}: {count} variations")
                    logger.info(f"\nTotal variations needing images: {total_variations_needing}")
                
                # Print detailed breakdown
                logger.info("\nDetailed Item Breakdown:")
                for item in items:
                    logger.info(f"\n{'='*50}")
                    logger.info(f"Item: {item['name']}")
                    logger.info(f"{'='*50}")
                    
                    if item['description']:
                        logger.info(f"Description: {item['description']}")
                    if item['category']:
                        logger.info(f"Category: {item['category']}")
                    
                    if item['is_single_variation']:
                        logger.info("\nType: Single-variation item")
                        logger.info(f"Needs primary image: Yes")
                        var = item['variations'][0] if item['variations'] else {}
                        if var:
                            # Show SKUs first
                            logger.info("\nIdentifiers:")
                            logger.info(f"  • Square SKU: {var['square_sku'] or 'Not Set'}")
                            logger.info(f"  • Vendor SKU: {var['vendor_sku'] or 'Not Set'}")
                            if var['upc']:
                                logger.info(f"  • UPC: {var['upc']}")
                            
                            # Show vendor info
                            logger.info("\nVendor Information:")
                            logger.info(f"  • Vendor: {var['vendor_name']}")
                            logger.info(f"  • Vendor ID: {var['vendor_id'] or 'Not Set'}")
                            
                            # Show all prices
                            logger.info("\nPricing:")
                            logger.info(f"  • Vendor Price: ${var['vendor_price']:.2f}")
                            logger.info(f"  • Retail Price: ${var['variation_price']:.2f}")
                            logger.info(f"  • Unit Cost: ${var['default_cost']:.2f}")
                    else:
                        logger.info("\nType: Multi-variation item")
                        logger.info(f"Needs primary image: {item['needs_primary_image']}")
                        
                        for var in item['variations']:
                            logger.info(f"\n  Variation: {var['name']}")
                            logger.info(f"  Status: {'NEEDS IMAGE' if var['needs_image'] else 'Has Image'}")
                            
                            # Show SKUs first
                            logger.info("\n  Identifiers:")
                            logger.info(f"    • Square SKU: {var['square_sku'] or 'Not Set'}")
                            logger.info(f"    • Vendor SKU: {var['vendor_sku'] or 'Not Set'}")
                            if var['upc']:
                                logger.info(f"    • UPC: {var['upc']}")
                            
                            # Show vendor info
                            logger.info("\n  Vendor Information:")
                            logger.info(f"    • Vendor: {var['vendor_name']}")
                            logger.info(f"    • Vendor ID: {var['vendor_id'] or 'Not Set'}")
                            
                            # Show all prices
                            logger.info("\n  Pricing:")
                            logger.info(f"    • Vendor Price: ${var['vendor_price']:.2f}")
                            logger.info(f"    • Retail Price: ${var['variation_price']:.2f}")
                            logger.info(f"    • Unit Cost: ${var['default_cost']:.2f}")
                    logger.info(f"\n{'='*50}")
            
            return items
            
        except Exception as e:
            logger.error(f"Error fetching items without images: {str(e)}")
            return []

    def process_catalog_items(self, items_response):
        """Process catalog items response and extract needed information."""
        items = []
        for item in items_response.get('items', []):
            item_data = item.get('item_data', {})
            item_id = item.get('id')
            name = item_data.get('name', '')
            description = item_data.get('description', '')
            
            # Check if item has a primary image
            has_primary_image = bool(item_data.get('image_ids'))
            needs_primary_image = not has_primary_image
            
            logger.debug(f"\n\nPROCESSING ITEM: {name}")
            logger.debug("="*80)
            logger.debug(f"Has Primary Image: {has_primary_image}")
            logger.debug(f"Needs Primary Image: {needs_primary_image}")
            
            variations = []
            raw_variations = item_data.get('variations', [])
            is_single_variation = len(raw_variations) == 1
            
            logger.debug(f"Found {len(raw_variations)} variations")
            
            for idx, variation in enumerate(raw_variations, 1):
                var_data = variation.get('item_variation_data', {})
                
                logger.debug(f"\nVARIATION {idx}:")
                logger.debug("-"*40)
                
                # Square SKU
                square_sku = var_data.get('sku', '')
                logger.debug(f"Square SKU: {square_sku}")
                
                # Vendor Info
                vendor_infos = var_data.get('item_variation_vendor_infos', [])
                if vendor_infos and len(vendor_infos) > 0:
                    vendor_info_data = vendor_infos[0].get('item_variation_vendor_info_data', {})
                    vendor_sku = vendor_info_data.get('sku', '')
                    vendor_id = vendor_info_data.get('vendor_id')
                    vendor_price = vendor_info_data.get('price_money', {}).get('amount', 0) / 100.0
                    logger.debug(f"Vendor Info Found:")
                    logger.debug(f"  Vendor SKU: {vendor_sku}")
                    logger.debug(f"  Vendor ID: {vendor_id}")
                    logger.debug(f"  Vendor Price: ${vendor_price:.2f}")
                else:
                    vendor_sku = ''
                    vendor_id = None
                    vendor_price = 0.0
                    logger.debug("No vendor info found")
                
                # Retail Price
                price_data = var_data.get('price_money', {})
                retail_price = price_data.get('amount', 0) / 100.0
                logger.debug(f"Retail Price: ${retail_price:.2f}")
                
                # Unit Cost
                cost_data = var_data.get('default_unit_cost', {})
                unit_cost = cost_data.get('amount', 0) / 100.0
                logger.debug(f"Unit Cost: ${unit_cost:.2f}")
                
                vendor_name = self.vendor_map.get(vendor_id, 'Unknown')
                logger.debug(f"Mapped Vendor Name: {vendor_name}")
                
                # Check variation image status
                has_variation_image = bool(var_data.get('image_ids'))
                needs_image = not is_single_variation and not has_variation_image
                
                variation_info = {
                    'id': variation.get('id'),
                    'name': var_data.get('name', ''),
                    'square_sku': square_sku,
                    'vendor_sku': vendor_sku,
                    'vendor_id': vendor_id,
                    'vendor_name': vendor_name,
                    'vendor_price': vendor_price,
                    'retail_price': retail_price,
                    'unit_cost': unit_cost,
                    'has_image': has_variation_image,
                    'needs_image': needs_image
                }
                
                logger.debug("\nFinal Variation Data:")
                logger.debug(f"  Name: {variation_info['name']}")
                logger.debug(f"  Square SKU: {variation_info['square_sku']}")
                logger.debug(f"  Vendor SKU: {variation_info['vendor_sku']}")
                logger.debug(f"  Vendor: {variation_info['vendor_name']} ({variation_info['vendor_id']})")
                logger.debug(f"  Vendor Price: ${variation_info['vendor_price']:.2f}")
                logger.debug(f"  Retail Price: ${variation_info['retail_price']:.2f}")
                logger.debug(f"  Unit Cost: ${variation_info['unit_cost']:.2f}")
                logger.debug(f"  Has Image: {variation_info['has_image']}")
                logger.debug(f"  Needs Image: {variation_info['needs_image']}")
                
                variations.append(variation_info)
            
            item_info = {
                'id': item_id,
                'name': name,
                'description': description,
                'has_primary_image': has_primary_image,
                'needs_primary_image': needs_primary_image,
                'variations': variations,
                'is_single_variation': is_single_variation
            }
            
            items.append(item_info)
            logger.debug("="*80 + "\n")
        
        return items

if __name__ == "__main__":
    # Verify paths first
    verifier = PathVerifier()
    if not verifier.verify_all():
        logger.error("Path verification failed!")
        sys.exit(1)
    
    # Initialize Square Catalog
    catalog = SquareCatalog()
    
    all_items = []
    cursor = None
    batch_size = 100
    
    logger.info("Fetching all items from Square...")
    
    while True:
        # Get batch of items
        body = {
            "product_types": ["REGULAR"],
            "state_filters": {"states": ["ACTIVE"]},
            "limit": batch_size
        }
        
        if cursor:
            body["cursor"] = cursor
        
        result = catalog.client.catalog.search_catalog_items(body=body)
        
        if not result.is_success():
            logger.error("Failed to fetch items from Square API")
            logger.error(pformat(result.errors))
            break
        
        # Process this batch
        batch_items = catalog.process_catalog_items(result.body)
        all_items.extend(batch_items)
        
        # Get cursor for next batch
        cursor = result.body.get('cursor')
        logger.info(f"Fetched batch of {len(batch_items)} items. Total so far: {len(all_items)}")
        
        # If no cursor, we've got all items
        if not cursor:
            break
    
    logger.info(f"\nFetched {len(all_items)} total items")
    
    # Filter for items that need images
    items_needing_images = []
    for item in all_items:
        needs_images = False
        if item['needs_primary_image']:
            needs_images = True
        for var in item['variations']:
            if var['needs_image']:
                needs_images = True
        if needs_images:
            items_needing_images.append(item)
    
    # Print results
    logger.info(f"Found {len(items_needing_images)} items needing images")
    
    # Print detailed breakdown of items needing images
    for item in items_needing_images:
        logger.info(f"\n{'='*80}")
        logger.info(f"Item: {item['name']}")
        
        if item['description']:
            logger.info(f"\nDescription: {item['description']}")
        
        if item['needs_primary_image']:
            logger.info("\n*** Needs Primary Image ***")
        
        for var in item['variations']:
            if item['is_single_variation']:
                logger.info("\nSingle Variation Item")
            else:
                logger.info(f"\nVariation: {var['name']}")
                if var['needs_image']:
                    logger.info("*** Needs Variation Image ***")
            
            logger.info("\nIdentifiers:")
            logger.info(f"  Square SKU: {var['square_sku']}")
            logger.info(f"  Vendor SKU: {var['vendor_sku']}")
            
            logger.info("\nVendor Information:")
            logger.info(f"  Vendor: {var['vendor_name']}")
            logger.info(f"  Vendor ID: {var['vendor_id']}")
            
            logger.info("\nPricing:")
            logger.info(f"  Vendor Price: ${var['vendor_price']:.2f}")
            logger.info(f"  Retail Price: ${var['retail_price']:.2f}")
            logger.info(f"  Unit Cost: ${var['unit_cost']:.2f}")
        
        logger.info(f"\n{'='*80}")
    
    # Generate summary by vendor
    if items_needing_images:
        logger.info("\nSUMMARY BY VENDOR")
        logger.info("=" * 40)
        
        vendor_summary = {}
        for item in items_needing_images:
            # Group variations by vendor
            for var in item['variations']:
                vendor = var['vendor_name']
                if vendor not in vendor_summary:
                    vendor_summary[vendor] = {
                        'primary_images_needed': 0,
                        'variations_needing_images': 0,
                        'items': set()  # Use set to avoid counting items twice
                    }
                
                # Track unique items needing primary images
                if item['needs_primary_image']:
                    vendor_summary[vendor]['items'].add(item['id'])
                    vendor_summary[vendor]['primary_images_needed'] += 1
                
                # Track variations needing images
                if var['needs_image']:
                    vendor_summary[vendor]['variations_needing_images'] += 1
        
        # Print summary
        for vendor, stats in sorted(vendor_summary.items()):
            logger.info(f"\n{vendor}:")
            logger.info(f"  Items needing primary image: {stats['primary_images_needed']}")
            logger.info(f"  Variations needing images: {stats['variations_needing_images']}")
        
        logger.info("\n" + "=" * 40)