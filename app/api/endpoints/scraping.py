from fastapi import APIRouter, BackgroundTasks, HTTPException
from typing import Dict
from app.services.scraper import ScraperService

router = APIRouter()
scraper_service = ScraperService()

@router.post("/start")
async def start_scraping(background_tasks: BackgroundTasks):
    """Start the scraping process"""
    try:
        background_tasks.add_task(scraper_service.start_scraping)
        return {"message": "Scraping process started"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status")
async def get_scraping_status() -> Dict[str, any]:
    """Get the current scraping status"""
    return scraper_service.get_status() 