#!/usr/bin/env python3
import re
from pathlib import Path

def parse_requirements(req_file):
    """Parse requirements.txt and return a dict of package names and versions."""
    requirements = {}
    current_section = "main"
    
    with open(req_file) as f:
        for line in f:
            line = line.strip()
            
            # Skip empty lines
            if not line:
                continue
                
            # Track sections (comments starting with #)
            if line.startswith("#"):
                current_section = line[1:].strip()
                continue
                
            # Skip other comments
            if line.startswith("#"):
                continue
                
            # Parse package requirements
            match = re.match(r'^([^<>=]+)([<>=]+.+)?$', line)
            if match:
                package = match.group(1).strip()
                version = match.group(2).strip() if match.group(2) else ""
                requirements[package] = {
                    "version": version,
                    "section": current_section
                }
    
    return requirements

def update_setup_py(setup_file, requirements):
    """Update setup.py with requirements."""
    with open(setup_file) as f:
        content = f.read()
    
    # Find the install_requires section
    install_requires_pattern = r'install_requires=\[(.*?)\]'
    current_requires = re.search(install_requires_pattern, content, re.DOTALL)
    
    if not current_requires:
        print("Could not find install_requires in setup.py")
        return False
    
    # Format new requirements
    new_requires = []
    for package, info in requirements.items():
        if info["version"]:
            new_requires.append(f'        "{package}{info["version"]}"')
        else:
            new_requires.append(f'        "{package}"')
    
    # Replace the old requirements
    new_content = re.sub(
        install_requires_pattern,
        'install_requires=[\n' + ',\n'.join(new_requires) + '\n    ]',
        content,
        flags=re.DOTALL
    )
    
    with open(setup_file, 'w') as f:
        f.write(new_content)
    
    return True

def main():
    # Get project root directory
    root_dir = Path(__file__).parent.parent
    
    # Define file paths
    requirements_file = root_dir / "requirements.txt"
    setup_file = root_dir / "setup.py"
    
    if not requirements_file.exists():
        print(f"Error: {requirements_file} not found")
        return
    
    if not setup_file.exists():
        print(f"Error: {setup_file} not found")
        return
    
    # Parse requirements.txt
    requirements = parse_requirements(requirements_file)
    
    # Update setup.py
    if update_setup_py(setup_file, requirements):
        print("Successfully synchronized dependencies!")
        print(f"\nUpdated {len(requirements)} packages in setup.py")
    else:
        print("Failed to update setup.py")

if __name__ == "__main__":
    main() 