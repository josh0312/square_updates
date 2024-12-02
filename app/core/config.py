from pydantic_settings import BaseSettings
from pathlib import Path
from dotenv import load_dotenv

# Update the path to look for .env in the app directory
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

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
        env_file = str(env_path)

# Create settings instance
settings = Settings() 