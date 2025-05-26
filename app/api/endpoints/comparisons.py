from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.services.product_comparison import ProductComparison
from typing import Dict, List

router = APIRouter()

@router.get("/products/{base_product_id}/compare-descriptions")
async def compare_descriptions(
    base_product_id: int,
    db: Session = Depends(get_db)
) -> Dict:
    """Compare product descriptions across different sources"""
    comparison = ProductComparison(db)
    result = comparison.compare_descriptions(base_product_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result

@router.get("/products/{base_product_id}/compare-videos")
async def compare_videos(
    base_product_id: int,
    db: Session = Depends(get_db)
) -> Dict:
    """Compare video availability across different sources"""
    comparison = ProductComparison(db)
    result = comparison.compare_videos(base_product_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result

@router.get("/products/missing-videos")
async def get_products_missing_videos(
    db: Session = Depends(get_db)
) -> List[Dict]:
    """Get products that have vendor videos but are missing from NyTex"""
    query = (
        db.query(BaseProduct)
        .join(VendorProduct)
        .join(NytexProduct)
        .filter(VendorProduct.vendor_video_url.isnot(None))
        .filter(NytexProduct.has_video.is_(False))
    )
    
    products = []
    for base_product in query:
        products.append({
            "id": base_product.id,
            "name": base_product.name,
            "vendors_with_video": [
                {
                    "vendor": vp.vendor_name,
                    "video_url": vp.vendor_video_url
                }
                for vp in base_product.vendor_products
                if vp.vendor_video_url
            ]
        })
        
    return products 