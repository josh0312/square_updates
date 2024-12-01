import os
import yaml

def load_yaml_config(filename: str) -> dict:
    """Load YAML configuration file"""
    config_dir = os.path.dirname(__file__)
    config_path = os.path.join(config_dir, filename)
    
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

# Load configs at module level
vendor_directories = load_yaml_config('vendor_directories.yaml')
websites = load_yaml_config('websites.yaml') 