from pathlib import Path
from typing import Dict
import os
import logging

logger = logging.getLogger(__name__)

class ProjectPaths:
    """Central configuration and verification for project paths"""
    
    def __init__(self):
        # Base directories
        self.APP_DIR = Path(__file__).parent.parent
        self.CONFIG_DIR = self.APP_DIR / 'config'
        self.LOGS_DIR = self.APP_DIR / 'logs'
        self.SERVICES_DIR = self.APP_DIR / 'services'
        self.DATA_DIR = self.APP_DIR / 'data'
        
        # Config files
        self.VENDOR_CONFIG = self.CONFIG_DIR / 'vendor_directories.yaml'
        self.WEBSITES_CONFIG = self.CONFIG_DIR / 'websites.yaml'
        
        # Database
        self.DB_FILE = self.APP_DIR / 'fireworks.db'
        
        # Required directories
        self.REQUIRED_DIRS = {
            'config': self.CONFIG_DIR,
            'logs': self.LOGS_DIR,
            'services': self.SERVICES_DIR,
            'data': self.DATA_DIR
        }
        
        # Required files
        self.REQUIRED_FILES = {
            'vendor_config': self.VENDOR_CONFIG,
            'websites_config': self.WEBSITES_CONFIG
        }
        
        # Initialize
        self.verify_paths()
    
    def verify_paths(self) -> Dict[str, bool]:
        """Verify all required paths exist and create directories if needed"""
        status = {}
        
        # Create required directories
        for name, path in self.REQUIRED_DIRS.items():
            try:
                path.mkdir(exist_ok=True)
                status[f'dir_{name}'] = True
                logger.debug(f"Directory verified: {path}")
            except Exception as e:
                status[f'dir_{name}'] = False
                logger.error(f"Failed to create directory {path}: {e}")
        
        # Verify required files
        for name, path in self.REQUIRED_FILES.items():
            exists = path.is_file()
            status[f'file_{name}'] = exists
            if not exists:
                logger.warning(f"Required file missing: {path}")
        
        return status
    
    def get_log_file(self, name: str) -> Path:
        """Get path for a log file, ensuring logs directory exists"""
        self.LOGS_DIR.mkdir(exist_ok=True)
        return self.LOGS_DIR / f"{name}.log"
    
    def get_config_file(self, name: str) -> Path:
        """Get path for a config file"""
        return self.CONFIG_DIR / name
    
    def __str__(self) -> str:
        """String representation showing all paths"""
        return "\n".join([
            "Project Paths:",
            f"  APP_DIR: {self.APP_DIR}",
            f"  CONFIG_DIR: {self.CONFIG_DIR}",
            f"  LOGS_DIR: {self.LOGS_DIR}",
            f"  SERVICES_DIR: {self.SERVICES_DIR}",
            f"  DATA_DIR: {self.DATA_DIR}",
            f"  DB_FILE: {self.DB_FILE}",
            "Config Files:",
            f"  VENDOR_CONFIG: {self.VENDOR_CONFIG}",
            f"  WEBSITES_CONFIG: {self.WEBSITES_CONFIG}"
        ])

# Create singleton instance
paths = ProjectPaths() 