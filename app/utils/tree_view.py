import os
from datetime import datetime

# File descriptions as a separate dictionary
FILE_DESCRIPTIONS = {
    'vendor_directories.yaml': 'Configuration mapping vendors to their directories and aliases',
    'websites.yaml': 'Configuration for web scraping targets and rules',
    'square_catalog.py': 'Square API integration for catalog management',
    'scrape_fireworks.py': 'Main web scraping orchestration script',
    'catalog.py': 'FastAPI endpoints for catalog operations',
    'scraper.py': 'Service for handling web scraping operations',
    'square_responses.py': 'Test fixtures for Square API responses',
    'test_square_catalog.py': 'Tests for Square catalog functionality',
    'project_structure.txt': 'Generated project structure documentation',
    'tree_view.py': 'Utility to generate project structure documentation'
}

def create_tree_view(root_dir='app'):
    """Create a simple tree view of the project structure"""
    
    def should_include(name):
        """Check if file/directory should be included"""
        excludes = {
            '__pycache__', '.git', '.env', 'venv', '.pytest_cache',
            '.pyc', '.pyo', '.pyd', '.DS_Store', '.coverage',
            'egg-info', '__init__.py'
        }
        return not any(ex in name for ex in excludes)
    
    def print_tree(dir_path, prefix=''):
        """Recursively print directory tree"""
        if not os.path.exists(dir_path):
            return []

        entries = sorted(os.listdir(dir_path))
        entries = [e for e in entries if should_include(e)]
        
        tree = []
        for i, entry in enumerate(entries):
            is_last = i == len(entries) - 1
            entry_path = os.path.join(dir_path, entry)
            
            # Add current entry
            marker = '└── ' if is_last else '├── '
            tree.append(f"{prefix}{marker}{entry}")
            
            # Recursively add subdirectories
            if os.path.isdir(entry_path):
                extension = '    ' if is_last else '│   '
                tree.extend(print_tree(entry_path, prefix + extension))
                
        return tree

    # Generate tree view
    tree_lines = ['app/'] + print_tree(root_dir)
    
    # Add descriptions section
    tree_lines.extend([
        '',
        'File Descriptions',
        '=' * 80,
        ''
    ])
    
    # Add descriptions for files that exist in the project
    for root, _, files in os.walk(root_dir):
        for file in files:
            if file in FILE_DESCRIPTIONS:
                desc = FILE_DESCRIPTIONS[file]
                tree_lines.append(f"{file:.<40} {desc}")
    
    return '\n'.join(tree_lines)

if __name__ == "__main__":
    # Generate tree with timestamp header
    header = f"""Project Structure - Generated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'='*80}

"""
    
    # Generate and save tree view
    tree = create_tree_view()
    output_path = 'app/utils/project_structure.txt'
    
    with open(output_path, 'w') as f:
        f.write(header + tree)
    
    print(header + tree)
    print(f"\nProject structure written to: {output_path}") 