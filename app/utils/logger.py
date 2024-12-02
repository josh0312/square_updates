import logging
import os
from datetime import datetime
from app.utils.paths import paths

def setup_logger(name):
    """Set up logger with file and console handlers"""
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)  # Set to DEBUG level
    
    # Create logs directory if it doesn't exist
    os.makedirs(paths.LOGS_DIR, exist_ok=True)
    
    # Create a unique log file for this run
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = os.path.join(paths.LOGS_DIR, f'{name}_{timestamp}.log')
    
    # File handler - include debug level
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)
    
    # Console handler - keep at INFO level
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(message)s')
    console_handler.setFormatter(console_formatter)
    
    # Add handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# Define standard log messages
def log_product_found(logger, product_name, product_url):
    """Log when a product is found during scraping"""
    logger.info(f"\n📦 Found product: {product_name}")
    logger.debug(f"Product URL: {product_url}")

def log_image_download(logger, status, filename):
    """Log image download status with emoji indicators"""
    if status == "success":
        logger.info(f"✅ Successfully downloaded image: {filename}")
    elif status == "exists":
        logger.info(f"⏩ Image already exists: {filename}")
    elif status == "error":
        logger.error(f"❌ Failed to download image: {filename}")

def log_database_update(logger, status, product_name, changes=None):
    """Log database update status with emoji indicators"""
    if status == "new":
        logger.info(f"✅ Added new product to database: {product_name}")
    elif status == "updated":
        logger.info(f"🔄 Updated product in database: {product_name}")
        if changes:
            for key, value in changes.items():
                logger.debug(f"  - {key}: {value}")
    elif status == "unchanged":
        logger.info(f"⏩ No database updates needed for: {product_name}")

def log_metadata(logger, metadata):
    """Log metadata with structured format"""
    logger.info("📋 Metadata found:")
    for key, value in metadata.items():
        if value is not None:  # Only log non-None values
            logger.info(f"  - {key}: {value}") 