import logging
import sys
import os

def setup_logger(name):
    """
    Set up a logger with standardized configuration
    
    Args:
        name: Name of the logger (usually __name__ from the calling module)
        
    Returns:
        logging.Logger: Configured logger instance
    """
    # Create logs directory if it doesn't exist
    os.makedirs('logs', exist_ok=True)
    
    # Get logger
    logger = logging.getLogger(name)
    
    # Only add handlers if they haven't been added already
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)
        
        # Create formatters
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        
        # File handler
        file_handler = logging.FileHandler('logs/scraper.log')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(file_formatter)
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(console_formatter)
        
        # Add handlers to logger
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
    
    return logger

# Define standard log messages
def log_product_found(logger, product_name, product_url):
    logger.info(f"\n📦 Found product: {product_name}")
    logger.debug(f"Product URL: {product_url}")

def log_image_download(logger, status, filename):
    if status == "success":
        logger.info(f"✅ Successfully downloaded image: {filename}")
    elif status == "exists":
        logger.info(f"⏩ Image already exists: {filename}")
    elif status == "error":
        logger.error(f"❌ Failed to download image: {filename}")

def log_database_update(logger, status, product_name, changes=None):
    if status == "new":
        logger.info(f"✅ Added new product to database: {product_name}")
    elif status == "updated":
        logger.info(f"🔄 Updated product in database: {product_name}")
        if changes:
            for change in changes:
                logger.debug(f"  - {change}")
    elif status == "unchanged":
        logger.info(f"⏩ No database updates needed for: {product_name}")

def log_metadata(logger, metadata):
    logger.info("📋 Metadata found:")
    for key, value in metadata.items():
        logger.info(f"  - {key}: {value}") 