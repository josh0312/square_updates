import os
import yaml
from fuzzywuzzy import fuzz
from fuzzywuzzy import process
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('matcher_test.log', mode='w'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def clean_name(name):
    """Clean product name for better matching"""
    logger.info(f"\nCleaning name: '{name}'")
    
    if not name:
        logger.warning("Received empty name for cleaning")
        return ""
    
    # Convert to string and lowercase
    name = str(name).lower().strip()
    logger.info(f"After lowercase: '{name}'")
    
    # Replace specific characters with spaces
    name = name.replace('-', ' ').replace('_', ' ').replace('.', ' ')
    logger.info(f"After replacing chars: '{name}'")
    
    # Keep alphanumeric characters and spaces
    cleaned = ''.join(c for c in name if c.isalnum() or c.isspace())
    logger.info(f"After keeping alphanumeric: '{cleaned}'")
    
    # Remove extra spaces
    cleaned = ' '.join(cleaned.split())
    logger.info(f"Final cleaned name: '{cleaned}'")
    
    return cleaned

def test_match():
    # Test item from Square
    square_name = "What Girl Wants Backpack"
    logger.info(f"\nTesting Square item: '{square_name}'")
    
    # Test image filename
    image_name = "What A Girl Wants Backpack.png"
    logger.info(f"Against image: '{image_name}'")
    
    # Clean both names
    cleaned_square = clean_name(square_name)
    cleaned_image = clean_name(os.path.splitext(image_name)[0])
    
    logger.info("\nComparison:")
    logger.info(f"Cleaned Square name: '{cleaned_square}'")
    logger.info(f"Cleaned image name: '{cleaned_image}'")
    
    # Try different fuzzy matching methods
    ratio = fuzz.ratio(cleaned_square, cleaned_image)
    partial_ratio = fuzz.partial_ratio(cleaned_square, cleaned_image)
    token_sort_ratio = fuzz.token_sort_ratio(cleaned_square, cleaned_image)
    token_set_ratio = fuzz.token_set_ratio(cleaned_square, cleaned_image)
    
    logger.info("\nMatching Scores:")
    logger.info(f"Simple Ratio: {ratio}")
    logger.info(f"Partial Ratio: {partial_ratio}")
    logger.info(f"Token Sort Ratio: {token_sort_ratio}")
    logger.info(f"Token Set Ratio: {token_set_ratio}")
    
    # Check for exact match
    if cleaned_square == cleaned_image:
        logger.info("\nEXACT MATCH!")
    else:
        logger.info("\nNot an exact match. Differences:")
        logger.info(f"Length: {len(cleaned_square)} vs {len(cleaned_image)}")
        logger.info(f"Characters: {list(cleaned_square)} vs {list(cleaned_image)}")

if __name__ == "__main__":
    test_match() 