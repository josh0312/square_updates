#!/usr/bin/env python3
"""
Log Cleanup Script
Removes old timestamped log files and keeps only essential rotating logs
"""

import os
import sys
import time
from pathlib import Path
from datetime import datetime, timedelta

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

from utils.paths import paths

def analyze_log_directory():
    """Analyze the current state of log directory"""
    logs_dir = Path(paths.LOGS_DIR)
    
    if not logs_dir.exists():
        print("❌ Logs directory does not exist")
        return {}
    
    all_files = list(logs_dir.glob('*'))
    log_files = [f for f in all_files if f.suffix in ['.log', ''] and f.name.endswith('.log')]
    
    # Categorize files
    timestamped_files = []
    rotating_files = []
    empty_files = []
    large_files = []
    
    total_size = 0
    
    for log_file in log_files:
        size = log_file.stat().st_size
        total_size += size
        
        # Check if file is empty
        if size == 0:
            empty_files.append(log_file)
        
        # Check if file is large (>10MB)
        if size > 10 * 1024 * 1024:
            large_files.append((log_file, size))
        
        # Check if filename contains timestamp pattern
        if any(pattern in log_file.name for pattern in ['_20', '_19']) and len(log_file.name) > 20:
            timestamped_files.append(log_file)
        else:
            rotating_files.append(log_file)
    
    return {
        'total_files': len(log_files),
        'total_size_mb': total_size / (1024 * 1024),
        'timestamped_files': timestamped_files,
        'rotating_files': rotating_files,
        'empty_files': empty_files,
        'large_files': large_files
    }

def cleanup_logs(dry_run=True, keep_days=7):
    """Clean up log files based on rules"""
    print(f"🧹 Log Cleanup {'(DRY RUN)' if dry_run else '(LIVE MODE)'}")
    print("="*60)
    
    analysis = analyze_log_directory()
    
    if analysis['total_files'] == 0:
        print("No log files found.")
        return
    
    print(f"📊 Current state:")
    print(f"  Total log files: {analysis['total_files']}")
    print(f"  Total size: {analysis['total_size_mb']:.1f} MB")
    print(f"  Timestamped files: {len(analysis['timestamped_files'])}")
    print(f"  Empty files: {len(analysis['empty_files'])}")
    print(f"  Large files (>10MB): {len(analysis['large_files'])}")
    print()
    
    files_to_remove = []
    size_to_save = 0
    
    # Rule 1: Remove all empty files
    for empty_file in analysis['empty_files']:
        files_to_remove.append(('empty', empty_file))
    
    # Rule 2: Remove timestamped files older than keep_days
    cutoff_time = time.time() - (keep_days * 24 * 60 * 60)
    for ts_file in analysis['timestamped_files']:
        if ts_file.stat().st_mtime < cutoff_time:
            files_to_remove.append(('old_timestamped', ts_file))
            size_to_save += ts_file.stat().st_size
    
    # Rule 3: For very large files, ask for confirmation
    for large_file, size in analysis['large_files']:
        size_mb = size / (1024 * 1024)
        print(f"⚠️  Large file found: {large_file.name} ({size_mb:.1f} MB)")
        if not dry_run:
            response = input(f"Remove {large_file.name}? [y/N]: ")
            if response.lower() == 'y':
                files_to_remove.append(('large', large_file))
                size_to_save += size
    
    print(f"\n🗑️  Files to remove: {len(files_to_remove)}")
    print(f"💾 Space to save: {size_to_save / (1024 * 1024):.1f} MB")
    
    if dry_run:
        print("\n📋 Files that would be removed:")
        for reason, file_path in files_to_remove:
            size_mb = file_path.stat().st_size / (1024 * 1024)
            print(f"  [{reason}] {file_path.name} ({size_mb:.1f} MB)")
        print(f"\n🔄 Run with --live to actually remove files")
        return
    
    # Actually remove files
    removed_count = 0
    removed_size = 0
    
    for reason, file_path in files_to_remove:
        try:
            size = file_path.stat().st_size
            file_path.unlink()
            removed_count += 1
            removed_size += size
            print(f"✅ Removed: {file_path.name}")
        except Exception as e:
            print(f"❌ Failed to remove {file_path.name}: {e}")
    
    print(f"\n🎉 Cleanup complete!")
    print(f"  Files removed: {removed_count}")
    print(f"  Space saved: {removed_size / (1024 * 1024):.1f} MB")

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Clean up log files')
    parser.add_argument('--live', action='store_true', help='Actually remove files (default is dry run)')
    parser.add_argument('--keep-days', type=int, default=7, help='Keep timestamped files newer than N days (default: 7)')
    
    args = parser.parse_args()
    
    cleanup_logs(dry_run=not args.live, keep_days=args.keep_days)

if __name__ == "__main__":
    main() 