from pathlib import Path
from typing import Dict, List
import yaml
import sys
import os
from app.utils.paths import paths
from app.utils.logger import setup_logger

logger = setup_logger('verify_paths')

class PathVerifier:
    def __init__(self):
        self.paths = paths
        self.issues = []
        
    def verify_all(self) -> bool:
        """Run all verifications and return True if everything is OK"""
        status = {
            'directories': self.verify_directories(),
            'configs': self.verify_config_files(),
            'permissions': self.verify_permissions(),
            'logs': self.verify_logs_directory()
        }
        
        # Print report
        self._print_report(status)
        
        return all(status.values())
    
    def verify_directories(self) -> bool:
        """Verify all required directories exist"""
        for name, path in self.paths.REQUIRED_DIRS.items():
            if not path.exists():
                self.issues.append(f"Missing directory: {path}")
                try:
                    path.mkdir(parents=True, exist_ok=True)
                    logger.info(f"Created directory: {path}")
                except Exception as e:
                    self.issues.append(f"Failed to create directory {path}: {e}")
                    return False
        return True
    
    def verify_config_files(self) -> bool:
        """Verify config files exist and are valid YAML"""
        for name, path in self.paths.REQUIRED_FILES.items():
            if not path.exists():
                self.issues.append(f"Missing config file: {path}")
                return False
            
            # Try to load YAML files
            if path.suffix == '.yaml':
                try:
                    with open(path) as f:
                        yaml.safe_load(f)
                except Exception as e:
                    self.issues.append(f"Invalid YAML in {path}: {e}")
                    return False
        return True
    
    def verify_permissions(self) -> bool:
        """Verify read/write permissions on key directories"""
        for name, path in self.paths.REQUIRED_DIRS.items():
            if not os.access(path, os.R_OK | os.W_OK):
                self.issues.append(f"Insufficient permissions on {path}")
                return False
        return True
    
    def verify_logs_directory(self) -> bool:
        """Verify logs directory is writable"""
        test_file = self.paths.LOGS_DIR / 'test_write.tmp'
        try:
            test_file.touch()
            test_file.unlink()
            return True
        except Exception as e:
            self.issues.append(f"Cannot write to logs directory: {e}")
            return False
    
    def _print_report(self, status: Dict[str, bool]) -> None:
        """Print verification report"""
        logger.info("\n=== Path Verification Report ===")
        
        # Print status
        for check, passed in status.items():
            status_str = "✅ PASS" if passed else "❌ FAIL"
            logger.info(f"{check:15} {status_str}")
        
        # Print issues if any
        if self.issues:
            logger.info("\nIssues Found:")
            for issue in self.issues:
                logger.error(f"  - {issue}")
        else:
            logger.info("\nNo issues found! 🎉")

def main():
    verifier = PathVerifier()
    if not verifier.verify_all():
        logger.error("Path verification failed!")
        sys.exit(1)
    logger.info("All paths verified successfully!")

if __name__ == "__main__":
    main() 