from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from typing import List

from app.services.image_matcher import ImageMatcher
from app.services.square_client import SquareClient
from app.utils.logger import setup_logger

logger = setup_logger(__name__)

router = APIRouter()
square_client = SquareClient()

@router.post("/match")
async def match_images(background_tasks: BackgroundTasks):
    """Match local images with Square catalog items"""
    try:
        matcher = ImageMatcher()
        background_tasks.add_task(matcher.match_and_upload_images)
        return {"message": "Image matching process started"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/upload")
async def upload_image(file: UploadFile = File(...)):
    """Upload an image to Square"""
    if not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File must be an image")
        
    try:
        # Implementation for image upload to Square
        # This will depend on your specific requirements
        pass
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 