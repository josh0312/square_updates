from square.client import Client
from fastapi import HTTPException
from typing import List, Optional
from app.core.config import settings
from app.utils.logger import setup_logger

logger = setup_logger(__name__)

class SquareClient:
    def __init__(self):
        self.client = Client(
            access_token=settings.SQUARE_ACCESS_TOKEN,
            environment=settings.SQUARE_ENVIRONMENT
        )
        
    async def get_catalog_items(self, cursor: Optional[str] = None) -> List[dict]:
        """Get catalog items from Square"""
        try:
            result = self.client.catalog.list_catalog(
                types="ITEM",
                cursor=cursor
            )
            
            if result.is_success():
                return result.body.get('objects', [])
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Square API Error: {result.errors}"
                )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to fetch catalog items: {str(e)}"
            )
            
    async def get_catalog_item(self, item_id: str) -> dict:
        """Get a specific catalog item from Square"""
        try:
            result = self.client.catalog.retrieve_catalog_object(
                object_id=item_id
            )
            
            if result.is_success():
                return result.body.get('object')
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Square API Error: {result.errors}"
                )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to fetch catalog item: {str(e)}"
            )
            
    async def upload_image(self, image_data: bytes, filename: str) -> dict:
        """Upload an image to Square"""
        try:
            result = self.client.catalog.create_catalog_image(
                request={
                    "idempotency_key": filename,
                    "image": {
                        "name": filename,
                        "type": "IMAGE",
                        "image_data": {
                            "name": filename,
                            "data": image_data
                        }
                    }
                }
            )
            
            if result.is_success():
                logger.info(f"Successfully uploaded image: {filename}")
                return result.body
            else:
                logger.error(f"Failed to upload image: {result.errors}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Square API Error: {result.errors}"
                )
        except Exception as e:
            logger.error(f"Error uploading image: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to upload image: {str(e)}"
            ) 