import pytest
import os
import sys
from dotenv import load_dotenv

# Get the absolute path to the app directory
APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Add app directory to Python path for imports
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

# Load environment variables for tests
load_dotenv(os.path.join(APP_DIR, '.env'))

@pytest.fixture(scope="session")
def test_env():
    """Ensure test environment is properly configured"""
    required_vars = [
        'SQUARE_ACCESS_TOKEN',
        'SQUARE_ENVIRONMENT',
        'SQLALCHEMY_DATABASE_URL'
    ]
    
    missing = [var for var in required_vars if not os.getenv(var)]
    if missing:
        pytest.fail(f"Missing required environment variables: {', '.join(missing)}")

@pytest.fixture(scope="session")
def app_dir():
    """Provide the application directory path"""
    return APP_DIR