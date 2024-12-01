from typing import List
from pydantic_settings import BaseSettings
from pydantic import AnyHttpUrl
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    # API Settings
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "NyTex Fireworks API"
    
    # CORS Settings
    ALLOWED_ORIGINS: List[AnyHttpUrl] = [
        "http://localhost:3000",  # React frontend
        "http://localhost:8000",  # FastAPI backend
    ]
    
    # Square API Settings
    SQUARE_ACCESS_TOKEN: str
    SQUARE_ENVIRONMENT: str = "sandbox"  # or "production"
    
    # Database Settings
    SQLALCHEMY_DATABASE_URL: str = "sqlite:///fireworks.db"
    
    # AWS Settings (if you're using S3 for image storage)
    AWS_ACCESS_KEY_ID: str | None = None
    AWS_SECRET_ACCESS_KEY: str | None = None
    AWS_BUCKET_NAME: str | None = None
    
    # Image Processing Settings
    MAX_IMAGE_SIZE: int = 10_000_000  # 10MB
    ALLOWED_IMAGE_TYPES: List[str] = ["image/jpeg", "image/png", "image/webp"]
    
    class Config:
        case_sensitive = True
        env_file = ".env"

# Create global settings object
settings = Settings() 