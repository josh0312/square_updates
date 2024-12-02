from app.services.image_matcher import ImageMatcher

def test_image_matcher():
    matcher = ImageMatcher()
    
    # Test vendor directory lookup
    vendor_dir = matcher.get_vendor_directory("Red Rhino")
    print(f"Vendor directory: {vendor_dir}")
    
    # Test image file listing
    images = matcher.get_image_files(vendor_dir)
    print(f"Found {len(images)} images in {vendor_dir}")
    
    # Test matches
    matches = matcher.find_matches()
    print(f"Found {len(matches)} matches")

if __name__ == "__main__":
    test_image_matcher() 