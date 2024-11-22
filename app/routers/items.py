from fastapi import APIRouter, Depends
from app.services.square_image_uploader import SquareImageUploader
from app.config import image_download_configs

router = APIRouter()

@router.post("/items/{item_id}/upload-images")
async def upload_item_images(item_id: str, uploader: SquareImageUploader = Depends()):
    image_paths = await uploader.download_images(item_id)
    for image_path in image_paths:
        with open(image_path, "rb") as file:
            image_data = file.read()
            await uploader.upload_image_to_square(item_id, image_data)
    return {"message": "Images uploaded successfully"} 