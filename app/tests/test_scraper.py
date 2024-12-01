import pytest
from app.utils.logger import setup_logger
from app.services.scraper import ScraperService
from app.utils.paths import paths

logger = setup_logger('test_scraper')

class TestScraperService:
    @pytest.fixture
    def scraper(self):
        return ScraperService()
    
    def test_load_websites(self, scraper):
        """Test website configuration loading"""
        websites = scraper.load_websites()
        assert isinstance(websites, list), "Should return a list of websites"
        
        if websites:
            first_site = websites[0]
            assert 'name' in first_site, "Website should have a name"
            assert 'scraper' in first_site, "Website should have a scraper"
            logger.info(f"Found {len(websites)} configured websites")
    
    def test_scraping_status(self, scraper):
        """Test scraping status tracking"""
        status = scraper.get_status()
        assert isinstance(status, dict), "Status should be a dictionary"
        assert 'is_running' in status, "Status should track if scraping is running"
        assert 'items_processed' in status, "Status should track processed items" 