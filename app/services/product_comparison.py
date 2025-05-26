from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from app.models.product import BaseProduct, VendorProduct, SquareProduct, NytexProduct
from difflib import SequenceMatcher

class ProductComparison:
    def __init__(self, db: Session):
        self.db = db
        
    def compare_descriptions(self, base_product_id: int) -> Dict:
        """Compare descriptions across different sources"""
        base_product = self.db.query(BaseProduct).get(base_product_id)
        if not base_product:
            return {"error": "Base product not found"}
            
        descriptions = {
            "vendor": [],
            "square": None,
            "nytex": None,
            "similarity_scores": {}
        }
        
        # Get vendor descriptions
        for vendor_product in base_product.vendor_products:
            if vendor_product.vendor_description:
                descriptions["vendor"].append({
                    "vendor": vendor_product.vendor_name,
                    "description": vendor_product.vendor_description
                })
                
        # Get Square description
        if base_product.square_product and base_product.square_product.description:
            descriptions["square"] = base_product.square_product.description
            
        # Get NyTex description
        if base_product.nytex_product and base_product.nytex_product.description:
            descriptions["nytex"] = base_product.nytex_product.description
            
        # Calculate similarity scores
        if descriptions["nytex"]:
            for vendor_desc in descriptions["vendor"]:
                score = SequenceMatcher(
                    None, 
                    vendor_desc["description"], 
                    descriptions["nytex"]
                ).ratio()
                descriptions["similarity_scores"][f"nytex_vs_{vendor_desc['vendor']}"] = score
                
        if descriptions["square"]:
            for vendor_desc in descriptions["vendor"]:
                score = SequenceMatcher(
                    None, 
                    vendor_desc["description"], 
                    descriptions["square"]
                ).ratio()
                descriptions["similarity_scores"][f"square_vs_{vendor_desc['vendor']}"] = score
                
        return descriptions
        
    def compare_videos(self, base_product_id: int) -> Dict:
        """Compare video availability across sources"""
        base_product = self.db.query(BaseProduct).get(base_product_id)
        if not base_product:
            return {"error": "Base product not found"}
            
        videos = {
            "vendor": [],
            "nytex": None,
            "missing_from_nytex": []
        }
        
        # Get vendor videos
        for vendor_product in base_product.vendor_products:
            if vendor_product.vendor_video_url:
                videos["vendor"].append({
                    "vendor": vendor_product.vendor_name,
                    "url": vendor_product.vendor_video_url
                })
                
        # Get NyTex video
        if base_product.nytex_product:
            if base_product.nytex_product.has_video:
                videos["nytex"] = {
                    "url": base_product.nytex_product.video_url,
                    "type": base_product.nytex_product.video_type
                }
            else:
                # If NyTex doesn't have the video but vendors do
                videos["missing_from_nytex"] = [
                    v["vendor"] for v in videos["vendor"]
                ]
                
        return videos 