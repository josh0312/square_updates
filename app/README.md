# NyTex Fireworks Square Updates

This project manages the Square catalog for NyTex Fireworks, including image management, vendor data synchronization, and web scraping capabilities.

## Features

- 🔄 Multi-site support with configurable scraping rules
- 📦 Product metadata extraction (names, SKUs, prices, descriptions, etc.)
- 🖼️ High-resolution image downloading with duplicate prevention
- 📊 SQLite database integration for product data storage
- 🚦 Rate limiting and polite scraping practices
- 📝 **Improved logging system with automatic rotation**
- ⚙️ YAML-based website configuration
- 🔍 Support for various website structures (WooCommerce, Shopify, etc.)
- 🎯 **Square API integration for catalog management**
- 🔗 **Advanced image matching and upload capabilities**

## Prerequisites

- Python 3.11+
- pip (Python package installer)
- Square Developer Account (for API access)

## Installation

1. Clone the repository:
   ```bash
   git clone [your-repository-url]
   cd square_updates
   ```

2. Create and activate virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   ```bash
   export SQUARE_ACCESS_TOKEN=your_access_token
   export SQUARE_ENVIRONMENT=sandbox  # or production
   ```

## Project Structure

```
square_updates/
├── app/                          # Main application directory
│   ├── api/                      # API endpoints
│   ├── config/                   # Configuration files
│   ├── core/                     # Core application logic
│   ├── data/                     # Data storage (images, etc.)
│   │   └── images/              # Downloaded product images
│   │       ├── pyrobuy.com/
│   │       ├── raccoonfireworksusa.com/
│   │       ├── redrhinofireworks.com/
│   │       ├── spfireworks.com/
│   │       ├── wincofireworks.com/
│   │       └── worldclassfireworks.com/
│   ├── db/                      # Database utilities
│   ├── logs/                    # **Rotating log files**
│   ├── models/                  # Data models
│   ├── schemas/                 # Pydantic schemas
│   ├── scrapers/                # Website scrapers
│   ├── scripts/                 # Utility scripts
│   ├── services/                # Business logic services
│   ├── utils/                   # Utility functions
│   ├── main.py                  # FastAPI application entry point
│   └── fireworks.db            # SQLite database
├── scripts/                     # Project-level scripts
│   └── cleanup_logs.py         # **Log maintenance utility**
├── data/                        # Project data directory
├── requirements.txt
└── setup.py
```

## Supported Websites

Currently supports:
- **Winco Fireworks Texas** (WooCommerce-based)
- **Red Rhino Fireworks** (WordPress/Elementor-based)
- **World Class Fireworks** (Shopify-based)
- **Pyro Buy Fireworks** (Classic ASP-based)
- **Raccoon Fireworks**
- **Supreme Fireworks**

## Core Components

### 1. Web Scraping
Scrapes product images and metadata from vendor websites with:
- Rate limiting to respect server resources
- Automatic file naming and organization
- Duplicate detection and prevention
- Error handling and retry logic
- **Rotating log files with automatic size management**

### 2. Image Matching System
Advanced matching between Square catalog items and vendor images:
- Intelligent product name cleaning and normalization
- Fuzzy string matching with configurable thresholds
- Support for multiple image formats (PNG, JPG, JPEG, GIF, WEBP)
- Vendor code resolution (WN → Winco, RR → Red Rhino, etc.)
- **Enhanced logging with detailed match scoring**

### 3. Square Catalog Management
Full integration with Square API for:
- Fetching and updating catalog items
- Managing vendor relationships and mappings
- Handling product variations and SKUs
- Image upload and association
- Active item filtering (excludes archived items)

### 4. **Improved Logging System**
Comprehensive logging with:
- **Automatic log rotation** (10MB max file size, 5 backup files)
- **No more duplicate console messages**
- Service-specific log files with meaningful names:
  - `scraper.log`: Main scraping operations
  - `all_scrapers.log`: Combined scraper output
  - `[vendor]_scraper.log`: Individual vendor scrapers
  - `image_matcher_unmatched.log`: Unmatched items tracking
  - `verify_paths.log`: Path verification operations

## Usage

### Running the FastAPI Application
```bash
# From project root directory
source venv/bin/activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Access the application
# • API Root: http://127.0.0.1:8000/
# • Interactive Docs: http://127.0.0.1:8000/docs
# • Catalog API: http://127.0.0.1:8000/api/catalog/items
```

### Web Scraping
```bash
python scrape_fireworks.py
```

### Image Matching and Upload
```bash
python image_matcher.py
```

### Log Cleanup
```bash
python scripts/cleanup_logs.py --live --keep-days 7
```

## Configuration

### Website Configuration
The project uses YAML files for website configurations. Each website entry includes:
```yaml
name: Website Name
url: https://website-url.com
scraper: scraper_file.py
enabled: true
limit: 5  # Number of images to download (-1 for unlimited)
note: "Website-specific notes and structure information"
```

### Environment Variables
Required environment variables:
- `SQUARE_ACCESS_TOKEN`: Your Square API access token
- `SQUARE_ENVIRONMENT`: `sandbox` or `production`

## Database Schema

Products are stored with comprehensive information:
- Site name and vendor details
- Product name, SKU, and pricing
- Detailed descriptions and categories
- Stock status and effects
- Product and image URLs
- Local image paths
- **Timestamp tracking for all operations**

## Recent Improvements (December 2024)

### Logging System Overhaul
- ✅ **Fixed double message problem** - no more duplicate console output
- ✅ **Implemented automatic log rotation** - prevents huge log files
- ✅ **Added proper logger deduplication** - prevents handler conflicts
- ✅ **Enhanced .gitignore patterns** - better temporary file handling

### Image Matching Enhancements
- Enhanced product name cleaning and matching algorithms
- Intelligent removal of product codes and descriptive terms
- Improved matching accuracy for vendor-specific naming conventions
- Better handling of variations vs parent items
- Detailed match scoring and reporting

### Square Integration Improvements
- Selective image upload system (only uploads when needed)
- Better vendor code resolution and mapping
- Enhanced item status tracking (active vs archived)
- Improved error handling and logging

## Testing

### Image Upload Testing
```bash
python square_image_uploader_test.py
```

### Limited Testing Mode
For development, you can limit operations:
```bash
python image_matcher.py  # Processes first 3 successful uploads
```

## Maintenance

### Log Management
Automatic log rotation is now enabled, but you can manually clean logs:
```bash
# Dry run (shows what would be removed)
python scripts/cleanup_logs.py

# Remove logs older than 3 days
python scripts/cleanup_logs.py --live --keep-days 3
```

### Database Maintenance
The SQLite database is located at `app/fireworks.db` and includes comprehensive product data with full audit trails.

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## Error Handling

The system includes comprehensive error handling:
- **Network error recovery** with exponential backoff
- **File system error handling** with detailed logging
- **Database transaction management** with rollback capabilities
- **API rate limit handling** with automatic retry logic
- **Detailed error logging** with context information

## Notes

- Ensure you have proper permissions to scrape target websites
- Monitor the rotating log files for detailed operation information
- Use the sandbox environment for testing before production
- The system respects rate limits and implements polite scraping practices
- All operations are logged with timestamps and detailed context

## License

[Your chosen license]

## Support

For issues or questions:
1. Check the relevant log files in `app/logs/`
2. Review the error handling documentation
3. Use the testing modes for development
4. Monitor the log rotation system for historical data
