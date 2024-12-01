from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.product import Product, ProductCreate
from app.services.square_catalog import SquareCatalog
from app.utils.logger import setup_logger

logger = setup_logger(__name__)

router = APIRouter()
square_client = SquareCatalog()

@router.get("/items", response_model=List[Product])
async def get_catalog_items(
    cursor: Optional[str] = Query(None, description="Pagination cursor"),
    db: Session = Depends(get_db)
):
    """Get all catalog items"""
    try:
        items = await square_client.get_catalog_items(cursor)
        return [
            Product(
                id=item['id'],
                name=item['item_data']['name'],
                sku=item['item_data'].get('variations', [{}])[0].get('item_variation_data', {}).get('sku'),
                description=item['item_data'].get('description'),
                price=float(item['item_data'].get('variations', [{}])[0].get('item_variation_data', {}).get('price_money', {}).get('amount', 0)) / 100,
                category=item['item_data'].get('category', {}).get('name'),
                image_url=item['item_data'].get('image_url'),
                created_at=item['created_at'],
                updated_at=item['updated_at']
            ) for item in items
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/items/{item_id}", response_model=Product)
async def get_catalog_item(item_id: str, db: Session = Depends(get_db)):
    """Get a specific catalog item"""
    try:
        item = await square_client.get_catalog_item(item_id)
        return Product(
            id=item['id'],
            name=item['item_data']['name'],
            sku=item['item_data'].get('variations', [{}])[0].get('item_variation_data', {}).get('sku'),
            description=item['item_data'].get('description'),
            price=float(item['item_data'].get('variations', [{}])[0].get('item_variation_data', {}).get('price_money', {}).get('amount', 0)) / 100,
            category=item['item_data'].get('category', {}).get('name'),
            image_url=item['item_data'].get('image_url'),
            created_at=item['created_at'],
            updated_at=item['updated_at']
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
  