import logging
from logging.handlers import RotatingFileHandler
import sys
import os

def setup_logger(name):
    """
    Set up a logger with standardized configuration and rotation
    
    Args:
        name: Name of the logger (usually __name__ from the calling module)
        
    Returns:
        logging.Logger: Configured logger instance
    """
    # Create logs directory relative to the current file
    logs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
    os.makedirs(logs_dir, exist_ok=True)
    
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
        
        # Individual log file with rotation
        file_handler = RotatingFileHandler(
            os.path.join(logs_dir, f'{name}.log'),
            maxBytes=1024*1024,  # 1MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(file_formatter)
        
        # Common scraper log file with rotation (for scrapers only)
        if 'scraper' in name.lower():
            common_handler = RotatingFileHandler(
                os.path.join(logs_dir, 'all_scrapers.log'),
                maxBytes=1024*1024,  # 1MB
                backupCount=5,
                encoding='utf-8'
            )
            common_handler.setLevel(logging.DEBUG)
            common_handler.setFormatter(file_formatter)
            logger.addHandler(common_handler)
        
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