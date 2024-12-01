import pytest
from app.utils.logger import setup_logger

logger = setup_logger('test_image_matcher')

@pytest.mark.skip(reason="Image matcher service not implemented yet")
class TestImageMatcher:
    def test_image_matching(self):
        """Test image matching functionality"""
        # Add tests once image matcher is implemented
        pass