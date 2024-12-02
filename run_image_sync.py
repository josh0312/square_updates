import logging
import os
from app.services.image_matcher import ImageMatcher
from datetime import datetime

def setup_logging():
    # Use the existing app/logs directory
    log_dir = "app/logs"
    
    # Generate timestamp for log files
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Clear any existing handlers
    root_logger.handlers = []
    
    # Console handler - only show INFO and above, with minimal formatting
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter('%(message)s')  # Even more minimal
    console_handler.setFormatter(console_format)
    root_logger.addHandler(console_handler)
    
    # File handler for detailed logs - single file per run
    detailed_log = os.path.join(log_dir, f'sync_detailed_{timestamp}.log')
    file_handler = logging.FileHandler(detailed_log, mode='w')
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_format)
    root_logger.addHandler(file_handler)
    
    # File handler for summary log - single file per run
    summary_log = os.path.join(log_dir, f'sync_summary_{timestamp}.log')
    summary_handler = logging.FileHandler(summary_log, mode='w')
    summary_handler.setLevel(logging.INFO)
    summary_handler.setFormatter(file_format)
    root_logger.addHandler(summary_handler)
    
    return detailed_log, summary_log

def main():
    # Setup logging and get log file paths
    detailed_log, summary_log = setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("\n=== Starting Image Sync Process ===")
    logger.info(f"Detailed log: {os.path.basename(detailed_log)}")
    logger.info(f"Summary log: {os.path.basename(summary_log)}")
    
    try:
        # Initialize the image matcher
        matcher = ImageMatcher()
        
        # Step 1: Find matches between Square items and local images
        logger.info("\nFinding matches between Square items and local images...")
        matches = matcher.find_matches()
        
        # Step 2: Process matches and upload images
        if matches:
            logger.info(f"\nFound {len(matches)} potential matches. Processing uploads...")
            successful_uploads, failed_uploads = matcher.process_matches(matches)
            logger.info("\n=== Final Results ===")
            logger.info(f"Total matches found: {len(matches)}")
            logger.info(f"Successful uploads: {successful_uploads}")
            logger.info(f"Failed uploads: {failed_uploads}")
        else:
            logger.info("\nNo matches found between Square items and local images.")
            
    except Exception as e:
        logger.error(f"\nError during image sync: {str(e)}", exc_info=True)
    
    logger.info("\n=== Image Sync Process Complete ===")
    logger.info(f"Detailed log: {detailed_log}")
    logger.info(f"Summary log: {summary_log}")

if __name__ == "__main__":
    main() 