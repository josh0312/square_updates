from pydantic_settings import BaseSettings
from pydantic import BaseModel
from typing import List
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    # API Settings
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "NyTex Fireworks API"
    
    # Square API Settings
    SQUARE_ACCESS_TOKEN: str
    SQUARE_ENVIRONMENT: str = "production"  # or "sandbox"
    
    # Database Settings
    SQLALCHEMY_DATABASE_URL: str = "sqlite:///fireworks.db"
    
    class Config:
        case_sensitive = True
        env_file = ".env"

# Create settings instance
settings = Settings()

# Image download configs can stay at the bottom
class ImageDownloadConfig(BaseModel):
    website: str
    base_url: str
    image_selector: str
    name_attribute: str
    output_directory: str

image_download_configs = [
    ImageDownloadConfig(
        website="Example Website 1",
        base_url="https://example1.com/",
        image_selector="img.product-image",
        name_attribute="data-product-id",
        output_directory="images/example1",
    ),
    ImageDownloadConfig(
        website="Example Website 2",
        base_url="https://example2.com/",
        image_selector="div.item-image > img",
        name_attribute="alt",
        output_directory="images/example2",
    ),
] 