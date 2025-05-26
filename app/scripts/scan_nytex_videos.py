from app.scrapers.nytex_video_scanner import NytexVideoScanner
import os

def main():
    # Create results directory if it doesn't exist
    os.makedirs('video_scan_results', exist_ok=True)
    
    # Run the scanner
    scanner = NytexVideoScanner()
    with_videos, without_videos = scanner.scan_videos()
    
    # Print summary
    print("\nScan Complete!")
    print("=============")
    print(f"Products with videos: {len(with_videos)}")
    print(f"Products without videos: {len(without_videos)}")
    
    # Print products with videos
    print("\nProducts with videos:")
    print("====================")
    for product in with_videos:
        print(f"- {product['product_name']}")
        print(f"  URL: {product['url']}")
        print(f"  Video Type: {product['video_type']}")
        print()
        
    # Print products without videos
    print("\nProducts without videos:")
    print("=======================")
    for product in without_videos:
        print(f"- {product['product_name']}")
        print(f"  URL: {product['url']}")
        print()

if __name__ == "__main__":
    main() 