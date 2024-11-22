from fastapi import FastAPI
from app.routers import items
from app.services.square_image_uploader import SquareImageUploader
from app.config import image_download_configs

app = FastAPI()

app.include_router(items.router)

@app.on_event("startup")
async def startup_event():
    square_access_token = "your_square_access_token"  # Replace with your actual access token
    app.state.square_uploader = SquareImageUploader(image_download_configs, square_access_token)