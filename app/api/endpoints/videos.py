from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.scrapers.nytex_scraper import NytexFireworksScraper
from typing import List, Dict

router = APIRouter()

@router.get("/scan-videos")
async def scan_videos(db: Session = Depends(get_db)):
    """Scan NyTex website for product videos"""
    scraper = NytexFireworksScraper()
    scraper.scan_for_videos("https://shop.nytexfireworks.com")
    return {"message": "Video scan completed"}

@router.get("/video-status")
async def get_video_status(db: Session = Depends(get_db)) -> Dict:
    """Get summary of products with/without videos"""
    products_with_video = db.query(Product).filter_by(has_video=True).count()
    products_without_video = db.query(Product).filter_by(has_video=False).count()
    
    return {
        "products_with_video": products_with_video,
        "products_without_video": products_without_video,
        "total_products": products_with_video + products_without_video
    } 