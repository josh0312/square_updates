import os
from datetime import datetime
from pathlib import Path
from pathspec import PathSpec
from pathspec.patterns import GitWildMatchPattern

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
    'tree_view.py': 'Utility to generate project structure documentation',
    'setup.py': 'Python package configuration and dependencies',
    'requirements.txt': 'Project dependencies and versions'
}

def get_gitignore_spec(root_dir):
    """Create a PathSpec object from .gitignore patterns"""
    patterns = []
    gitignore_path = os.path.join(root_dir, '.gitignore')
    
    # Add default patterns - make patterns more comprehensive
    default_patterns = [
        # Version Control
        '.git/',
        
        # Python specific
        '__pycache__/',
        '*.py[cod]',
        '*$py.class',
        '*.so',
        '.Python',
        'develop-eggs/',
        'dist/',
        'downloads/',
        'eggs/',
        '.eggs/',
        'lib/',
        'lib64/',
        'parts/',
        'sdist/',
        'var/',
        'wheels/',
        '*.egg-info/',
        '.installed.cfg',
        '*.egg',
        
        # Virtual environments
        '.env/',
        '.venv/',
        'env/',
        'venv/',
        'ENV/',
        'env.bak/',
        'venv.bak/',
        
        # Testing
        '.tox/',
        '.coverage',
        '.coverage.*',
        '.cache/',
        '.pytest_cache/',
        'htmlcov/',
        
        # IDE specific
        '.idea/',
        '.vscode/',
        '*.swp',
        '*.swo',
        
        # OS specific
        '.DS_Store',
        'Thumbs.db',
        '*~',
        '._*',
        '.*.sw?',
        
        # Project specific
        'data/',
        '__init__.py',
        'logs/',
        '*.log',
    ]
    patterns.extend(default_patterns)
    
    # Add patterns from .gitignore if it exists
    if os.path.exists(gitignore_path):
        with open(gitignore_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    patterns.append(line)
    
    return PathSpec.from_lines(GitWildMatchPattern, patterns)

def should_include(path, name, gitignore_spec, root_parent):
    """Check if file/directory should be included based on .gitignore patterns"""
    # Get relative path from project root
    full_path = os.path.join(path, name)
    rel_path = os.path.relpath(full_path, root_parent)
    
    # Check if path matches any gitignore pattern
    return not gitignore_spec.match_file(rel_path)

def create_tree_view(root_dir=None):
    """Create a simple tree view of the project structure"""
    
    # If no root_dir specified, use the project root (parent of app directory)
    if root_dir is None:
        current_dir = os.path.dirname(os.path.abspath(__file__))  # utils directory
        app_dir = os.path.dirname(current_dir)  # app directory
        root_dir = os.path.dirname(app_dir)  # project root
    
    root_parent = os.path.dirname(root_dir)
    gitignore_spec = get_gitignore_spec(root_dir)
    
    def print_tree(dir_path, prefix=''):
        """Recursively print directory tree"""
        if not os.path.exists(dir_path):
            return []

        entries = sorted(os.listdir(dir_path))
        entries = [e for e in entries if should_include(dir_path, e, gitignore_spec, root_parent)]
        
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

    # Generate tree view starting with root directory name
    root_name = os.path.basename(root_dir)
    tree_lines = [f'{root_name}/'] + print_tree(root_dir)
    
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