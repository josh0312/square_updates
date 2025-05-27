import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler
from app.utils.paths import paths

# Track initialized loggers to prevent duplicate handlers
_initialized_loggers = set()

def setup_logger(name, max_file_size_mb=10, backup_count=5):
    """Set up logger with file and console handlers, with rotation and no duplicates"""
    logger = logging.getLogger(name)
    
    # Prevent duplicate handler setup
    if name in _initialized_loggers:
        return logger
    
    logger.setLevel(logging.DEBUG)
    
    # Clear any existing handlers to prevent duplicates
    logger.handlers.clear()
    
    # Create logs directory if it doesn't exist
    os.makedirs(paths.LOGS_DIR, exist_ok=True)
    
    # Use simple filename without timestamp for rotation
    log_file = os.path.join(paths.LOGS_DIR, f'{name}.log')
    
    # Rotating file handler - prevents huge files
    max_bytes = max_file_size_mb * 1024 * 1024  # Convert MB to bytes
    file_handler = RotatingFileHandler(
        log_file, 
        maxBytes=max_bytes, 
        backupCount=backup_count
    )
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(file_formatter)
    
    # Console handler - keep at INFO level
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(levelname)s: %(message)s')
    console_handler.setFormatter(console_formatter)
    
    # Add handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    # Prevent propagation to root logger (prevents duplicate console output)
    logger.propagate = False
    
    # Mark this logger as initialized
    _initialized_loggers.add(name)
    
    return logger

def get_logger(name):
    """Get an existing logger or create new one with setup"""
    return setup_logger(name)

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

def cleanup_old_logs(days_to_keep=30):
    """Clean up log files older than specified days"""
    import time
    from pathlib import Path
    
    logs_dir = Path(paths.LOGS_DIR)
    current_time = time.time()
    days_in_seconds = days_to_keep * 24 * 60 * 60
    
    cleaned_count = 0
    for log_file in logs_dir.glob('*.log*'):
        if log_file.stat().st_mtime < (current_time - days_in_seconds):
            try:
                log_file.unlink()
                cleaned_count += 1
            except Exception as e:
                print(f"Could not delete {log_file}: {e}")
    
    print(f"Cleaned up {cleaned_count} old log files")
    return cleaned_count 