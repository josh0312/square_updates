import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.utils.logger import setup_logger

logger = setup_logger('test_endpoints')
client = TestClient(app)

@pytest.mark.skip(reason="Endpoints not fully implemented yet")
class TestEndpoints:
    def test_catalog_endpoints(self):
        """Test catalog API endpoints"""
        response = client.get("/api/catalog/items")
        assert response.status_code == 200
        logger.info("Tested catalog items endpoint")
        
        # Test single item endpoint
        if response.json():
            first_item_id = response.json()[0]['id']
            item_response = client.get(f"/api/catalog/items/{first_item_id}")
            assert item_response.status_code == 200
    
    def test_image_endpoints(self):
        """Test image API endpoints"""
        response = client.get("/api/images/status")
        assert response.status_code == 200
        logger.info("Tested image status endpoint") 