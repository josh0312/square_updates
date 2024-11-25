# NyTex Fireworks Square Updates

This project manages the Square catalog for NyTex Fireworks, including image management, vendor data synchronization, and web scraping capabilities.

## Features

- 🔄 Multi-site support with configurable scraping rules
- 📦 Product metadata extraction (names, SKUs, prices, descriptions, etc.)
- 🖼️ High-resolution image downloading with duplicate prevention
- 📊 SQLite database integration for product data storage
- 🚦 Rate limiting and polite scraping practices
- 📝 Comprehensive logging system
- ⚙️ YAML-based website configuration
- 🔍 Support for various website structures (WooCommerce, Shopify, etc.)

## Prerequisites

- Python 3.7+
- pip (Python package installer)

## Installation

1. Clone the repository:
   git clone [your-repository-url]
   cd [repository-name]

2. Install required dependencies:
   pip install -r requirements.txt

3. Configure your database path in `scrape_fireworks.py`:
   engine = create_engine('sqlite:///fireworks.db')

## Configuration

The project uses `websites.yaml` for website configurations. Each website entry includes:

    name: Website Name
    url: https://website-url.com
    scraper: scraper_file.py
    enabled: true
    limit: 5  # Number of images to download (-1 for unlimited)
    note: "Website-specific notes and structure information"

## Usage

Run the scraper:
    python scrape_fireworks.py

The scraper will:
1. Load configurations from `websites.yaml`
2. Process each enabled website
3. Download images to site-specific folders
4. Store product metadata in the database
5. Generate detailed logs in `scraper.log`

## Project Structure

    ├── models/
    │   └── product.py
    ├── scrapers/
    │   ├── __init__.py
    │   ├── winco_scraper.py
    │   ├── redrhino_scraper.py
    │   ├── worldclass_scraper.py
    │   ├── pyrobuy_scraper.py
    │   └── raccoon_scraper.py
    ├── scrape_fireworks.py
    ├── websites.yaml
    ├── requirements.txt
    ├── scraper.log
    └── README.md

## Supported Websites

Currently supports:
- Winco Fireworks Texas
- Red Rhino Fireworks
- World Class Fireworks
- Pyro Buy Fireworks
- Raccoon Fireworks

## Image Storage

Images are stored in the following structure:

    /Users/joshgoble/Downloads/firework_pics/
    └── [domain-name]/
        └── [product-images].jpg

## Database Schema

Products are stored with the following information:
- Site name
- Product name
- SKU
- Price
- Description
- Category
- Stock status
- Effects
- Product URL
- Image URL
- Local image path
- Timestamps

## Error Handling

The scraper includes:
- Comprehensive error logging
- Network error recovery
- File system error handling
- Database transaction management

## Adding New Websites

To add a new website to the scraper:

1. Create a new scraper file in the `scrapers` directory (e.g., `new_website_scraper.py`).
2. Implement the website-specific scraping logic in the new scraper file, following the existing scraper structure.
3. Update the `websites.yaml` file with the new website's configuration, including the scraper file name.
4. Run the `scrape_fireworks.py` script to start scraping the new website.

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

[Your chosen license]

## Acknowledgments

- Winco Fireworks (WooCommerce-based)
- Red Rhino Fireworks (WordPress/Elementor-based)
  - Supports year-based image folders
  - Handles multiple image locations
  - Filters out common site images
- World Class Fireworks (Shopify-based)
- Pyro Buy Fireworks (Classic ASP-based)

## Notes

- Ensure you have proper permissions to scrape target websites
- Adjust rate limiting as needed to be respectful to servers
- Monitor scraper.log for detailed operation information

### Image Matcher
- Automatically matches Square catalog items with vendor product images
- Uses fuzzy string matching to handle naming variations
- Supports multiple image formats (PNG, JPG, JPEG, GIF, WEBP)
- Generates detailed logs and reports:
  - `matcher.log`: Detailed matching process logs
  - `unmatched.txt`: List of items without image matches
- Provides match statistics and success rates
- Handles vendor aliases and directory mappings

### Square Catalog Management
- Fetches and updates catalog items
- Manages vendor relationships
- Handles product variations and SKUs
- Supports image assignments
- Supports both exact and fuzzy matching with configurable thresholds
- Generates detailed matching statistics and reports

### Web Scraping
- Scrapes product images from vendor websites
- Handles pagination and rate limiting
- Supports multiple vendor sites
- Organizes images by vendor
- Features:
  - Rate limiting to respect server resources
  - Automatic file naming and organization
  - Duplicate detection
  - Error handling and retry logic
- Generates scraping logs:
  - `scraper.log`: Detailed scraping progress
  - `logs/scraper.log`: Additional debug information


### Square Catalog Management
- Fetches and updates catalog items through Square API
- Manages vendor relationships and mappings
- Handles product variations and SKUs
- Supports image assignments
- Features:
  - Vendor mapping and ID resolution
  - Item variation tracking
  - SKU management
  - Image status tracking
  - Bulk operations support
- Generates detailed logs:
  - `square_catalog.log`: API interactions and operations
  - `square.log`: Testing and debugging information

### Square Image Upload
- Uploads matched images directly to Square catalog
- Associates images with catalog items and variations
- Features:
  - Single image upload testing
  - Idempotent operations
  - Error handling and logging
  - Image-to-item association
- Generates detailed logs:
  - `square_image_upload.log`: Image upload operations and results

## Testing Image Upload
To test image uploads to Square:

1. Set up environment variables:
   ```
   SQUARE_ACCESS_TOKEN=your_access_token
   SQUARE_ENVIRONMENT=sandbox  # or production
   ```

2. Run the test script:
   ```
   python square_image_uploader_test.py
   ```

3. Check `square_image_upload.log` for results

## Setup

1. Clone the repository
2. Install dependencies:

## Square Image Management System

## Recent Updates (Nov 25, 2024)

### Image Matching and Upload Improvements
- Added selective image upload system:
  - Checks if items/variations already have images before uploading
  - Only uploads to items/variations that need images
  - Properly associates images with both parent items and variations
  - Supports primary image designation for items

### Square Catalog Integration
- Added active item filtering:
  - Only processes non-archived items
  - Checks image status at both item and variation level
  - Improved vendor code resolution (WN -> Winco, RR -> Red Rhino, etc.)
  - Better logging of item/variation status

### Testing Features
- Added test limiting:
  - Can limit to first 3 successful uploads for testing
  - Detailed logging of match attempts and results
  - Shows which items were processed and why
  - Logs successful uploads with match scores

### Usage
To test with limited uploads:
```bash
python image_matcher.py
```
This will:
1. Process items until 3 successful uploads
2. Show detailed matching process
3. Log results to matcher.log
4. Write unmatched items to unmatched.txt
