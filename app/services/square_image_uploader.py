import os
import uuid
from typing import List
import requests
from bs4 import BeautifulSoup
from fastapi import HTTPException
from square.client import Client
from app.config import ImageDownloadConfig

class SquareImageUploader:
    def __init__(self, image_download_configs: List[ImageDownloadConfig], square_access_token: str):
        self.image_download_configs = image_download_configs
        self.client = Client(access_token=square_access_token)

    async def download_images(self, item_id: str) -> List[str]:
        image_paths = []
        for config in self.image_download_configs:
            try:
                url = f"{config.base_url}{item_id}"
                response = requests.get(url)
                response.raise_for_status()

                soup = BeautifulSoup(response.text, "html.parser")
                image_element = soup.select_one(config.image_selector)

                if image_element:
                    image_url = image_element["src"]
                    image_name = f"{item_id}_{image_element[config.name_attribute]}.jpg"
                    image_path = os.path.join(config.output_directory, image_name)

                    # Download the image
                    image_response = requests.get(image_url)
                    image_response.raise_for_status()

                    # Save the image to the specified directory
                    os.makedirs(config.output_directory, exist_ok=True)
                    with open(image_path, "wb") as file:
                        file.write(image_response.content)

                    image_paths.append(image_path)

            except requests.exceptions.RequestException as e:
                raise HTTPException(status_code=400, detail=f"Failed to download image: {str(e)}")

        return image_paths

    async def upload_image_to_square(self, item_id: str, image_data: bytes) -> None:
        try:
            result = self.client.catalog.create_catalog_image(
                request={
                    "idempotency_key": str(uuid.uuid4()),
                    "object_id": item_id,
                    "image": {
                        "type": "IMAGE",
                        "id": "#TEMP_ID",
                        "image_data": {
                            "caption": "Item Image",
                            "name": "item_image.jpg",
                        },
                    },
                },
                image_file=image_data,
            )

            if result.is_success():
                print(f"Image uploaded successfully for item: {item_id}")
            else:
                raise HTTPException(status_code=400, detail=f"Failed to upload image for item: {item_id}")

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error uploading image to Square: {str(e)}") 